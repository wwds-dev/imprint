"""Background worker threads.

Moved verbatim out of main.py (see docs/refactor_plan.md, phase 1). These are
standalone QThread subclasses: they take everything they need as constructor
arguments and touch no application state, which is why they move first.
"""
import re
import subprocess
import time
from pathlib import Path

import threading

from PySide6.QtCore import QObject, QThread, Signal

from services.openai_client import DEFAULT_IMAGE_MODEL
from services.chat_projects import with_project_instructions
from services.output_limits import stop_kind


class ChatWorker(QThread):
    token_signal = Signal(str)
    status_signal = Signal(str)
    finished_signal = Signal(str)
    error_signal = Signal(str)
    usage_signal = Signal(dict)

    def __init__(self, run_backend_func, backend: str, model: str, messages: list,
                 prompt: str, project_instructions: str = ""):
        super().__init__()
        self.run_backend_func = run_backend_func
        self.backend = backend
        self.model = model
        self.messages = with_project_instructions(messages, project_instructions)
        self.prompt = prompt
        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True

    def _emit_as_tokens(self, text: str):
        for part in re.split(r"(\s+)", text):
            if self._cancel_requested:
                return
            self.token_signal.emit(part)
            time.sleep(0.006)

    def run(self):
        try:
            self.status_signal.emit("Model processing started...")
            result = self.run_backend_func(
                self.backend,
                self.model,
                self.messages,
                self.prompt,
            )

            usage = None
            response_parts = []

            # ===== STREAMING CASE =====
            if hasattr(result, "__iter__") and not isinstance(result, (str, tuple, dict)):
                self.status_signal.emit("Streaming response...")

                for token in result:
                    if self._cancel_requested:
                        # Close the abandoned stream so the provider
                        # connection drops now — a cancelled local
                        # generation otherwise keeps the daemon busy
                        # until a cyclic-GC pass finalizes the cycle.
                        getattr(result, "close", lambda: None)()
                        self.error_signal.emit("Request cancelled by user.")
                        return

                    response_parts.append(token)
                    self.token_signal.emit(token)

                response = "".join(response_parts)

                # The clients wrap their streams in UsageStream and fill
                # .usage from the provider's final frame — real token counts,
                # so cached-input billing works and cost_type is "exact".
                # Only when a provider sent nothing does billing fall back to
                # the chars/4 estimate.
                usage = getattr(result, "usage", None) or {
                    "cost_type_override": "stream-estimated"
                }
                stop = stop_kind(getattr(result, "stop_reason", None))

            # ===== TUPLE (response, usage) =====
            elif isinstance(result, tuple):
                response, usage = result
                stop = stop_kind((usage or {}).get("stop_reason"))
                self._emit_as_tokens(response)

            # ===== NORMAL STRING RESPONSE =====
            else:
                response = result
                stop = None
                self._emit_as_tokens(response)

            # A reply cut at the output cap must never look complete: the
            # stop reason rides on the usage signal, which is emitted before
            # finished_signal from this thread and so reaches the GUI first.
            # A reply without a usage frame keeps its estimated cost type.
            if stop:
                usage = {**(usage or {"cost_type_override": "estimated"}),
                         "stop_reason": stop}

            # Same outcome for a cancel whichever path served the request:
            # the streaming loop above already routes a cancel to
            # error_signal, but the non-streaming paths used to fall through
            # and emit finished_signal — billing and saving a chat the user
            # had stopped.
            if self._cancel_requested:
                self.error_signal.emit("Request cancelled by user.")
                return

            if usage:
                self.usage_signal.emit(usage)

            self.finished_signal.emit(response)

        except Exception as e:
            self.error_signal.emit(str(e))


# SubprocessWorker was deleted here: imported by main.py but instantiated
# nowhere since the security verticals were stripped.


class DaemonWorker(QObject):
    """Network work on a Python daemon thread, behind QThread's surface.

    A model-list request can take two minutes (the client timeout, plus a
    retry), and these start by themselves at launch. A QThread still running
    when the app quits is destroyed under it, and Qt aborts the process
    (SIGABRT) — closeEvent waits two seconds, not two minutes. A daemon thread
    is simply abandoned at interpreter exit. Only for work that holds no Qt
    objects and writes nothing: a model list qualifies, a paid render does not.

    start / isRunning / wait / finished behave like QThread's, so callers and
    tests did not change. Signals emitted from the thread reach slots on the
    GUI thread by queued connection, as QThread's did.
    """

    finished = Signal()

    def __init__(self):
        super().__init__()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self.isRunning():
            return
        self._thread = threading.Thread(
            target=self._run_guarded, name=type(self).__name__, daemon=True)
        self._thread.start()

    def _run_guarded(self) -> None:
        try:
            self.run()
        finally:
            self._emit(self.finished)

    @staticmethod
    def _emit(signal, *args) -> None:
        try:
            signal.emit(*args)
        except RuntimeError:
            pass            # the receiving window was destroyed during quit

    def isRunning(self) -> bool:  # noqa: N802 - QThread's name
        return self._thread is not None and self._thread.is_alive()

    def wait(self, msecs: int | None = None) -> bool:
        if self._thread is not None:
            self._thread.join(None if msecs is None else msecs / 1000.0)
        return not self.isRunning()

    def run(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError


class ModelListWorker(DaemonWorker):
    """Fetch a provider's live model list off the GUI thread.

    list_models() can block for two REQUEST_TIMEOUT_SECONDS windows on a
    configured cloud provider — the exact freeze AgentPanel.load_models
    used to cause on startup and every provider switch. One worker per
    provider is shared by every panel; the host caches the result for
    the session.
    """

    models_signal = Signal(str, list, str)   # provider, models, error

    def __init__(self, client, provider: str):
        super().__init__()
        self.client = client
        self.provider = provider

    def run(self):
        try:
            # The raising variant where a client offers one: the worker must
            # be able to tell a live answer from a swallowed failure, or the
            # host caches KNOWN_MODELS as live for the whole session.
            fetch = getattr(self.client, "list_models_live", None) \
                or self.client.list_models
            models = list(fetch() or [])
            self._emit(self.models_signal, self.provider, models, "")
        except Exception as exc:
            self._emit(self.models_signal, self.provider, [], str(exc))


class ModelPullWorker(QThread):
    """Downloads an Ollama model off the UI thread.

    progress_signal carries (status, completed_bytes, total_bytes); total is 0
    until Ollama has resolved the manifest.

    The byte counts go as `object`, not `int`: Qt's int is 32-bit, so a
    16.8 GB layer arrived as -423188128 and the panel, seeing no positive
    total, showed a bare "pulling 71b5c9c9abbc" for the whole download.
    """
    progress_signal = Signal(str, object, object)
    finished_signal = Signal(str)
    error_signal = Signal(str)

    def __init__(self, client, model: str):
        super().__init__()
        self._client = client
        self._model = model

    def run(self):
        try:
            self._client.pull_model(
                self._model,
                on_progress=lambda status, done, total: self.progress_signal.emit(
                    status, int(done or 0), int(total or 0)
                ),
            )
            self.finished_signal.emit(self._model)
        except Exception as e:
            self.error_signal.emit(str(e))


class FiverrImageWorker(QThread):
    """Generates and saves logo images, one concept at a time."""
    image_ready_signal = Signal(str, int)   # local_path, index
    all_done_signal = Signal(list)           # all local paths
    error_signal = Signal(str)
    status_signal = Signal(str)

    def __init__(self, openai_client, image_prompt: str, count: int,
                 save_dir: Path, image_model: str = DEFAULT_IMAGE_MODEL):
        super().__init__()
        self.openai_client = openai_client
        self.image_prompt = image_prompt
        self.count = count
        self.save_dir = save_dir
        self.image_model = image_model
        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True

    def run(self):
        # Every run ends in all_done_signal or error_signal: the panel's Stop
        # closes the paid request only from that last signal.
        try:
            self.save_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.error_signal.emit(f"Could not create {self.save_dir}: {e}")
            return
        paths = []
        for i in range(self.count):
            if self._cancel_requested:
                self.error_signal.emit("Cancelled.")
                return
            try:
                self.status_signal.emit(f"Generating concept {i + 1} of {self.count}...")
                # One call for every image route (OpenAI, Gemini, Qwen); each
                # normalises its response to bytes before the worker writes it.
                from services.image_generation import generate_image
                data = generate_image(self.image_model, self.image_prompt,
                                      aspect="1:1",
                                      openai_client=self.openai_client)
                local_path = self.save_dir / f"logo_{i + 1}.png"
                local_path.write_bytes(data)
                paths.append(str(local_path))
                self.image_ready_signal.emit(str(local_path), i)
            except Exception as e:
                self.error_signal.emit(f"Concept {i + 1} failed: {e}")
                return
        self.all_done_signal.emit(paths)


class HiggsfieldEstimateWorker(QThread):
    """Upload any reference image and price the exact request off the UI thread."""

    status_signal = Signal(str)
    done_signal = Signal(object, object)  # PreparedVideoRequest, VideoEstimate
    error_signal = Signal(str)

    def __init__(self, client, prompt: str, *, duration: int = 5,
                 reference_image: str | None = None,
                 aspect_ratio: str | None = None,
                 resolution: str | None = None,
                 model: str | None = None):
        super().__init__()
        self.client = client
        self.model = model
        self.prompt = prompt
        self.duration = duration
        self.reference_image = reference_image
        self.aspect_ratio = aspect_ratio
        self.resolution = resolution
        self._cancel_requested = False

    def cancel(self):
        # Preparation contains short network operations rather than a remote
        # render, so cancellation is observed between upload and estimate.
        self._cancel_requested = True

    def run(self):
        try:
            self.status_signal.emit(
                "Uploading reference image…" if self.reference_image
                else "Preparing render estimate…")
            kwargs = dict(duration=self.duration,
                          reference_image=self.reference_image,
                          aspect_ratio=self.aspect_ratio,
                          resolution=self.resolution)
            if self.model:
                kwargs["model"] = self.model
            request = self.client.prepare_video(self.prompt, **kwargs)
            if self._cancel_requested:
                self.error_signal.emit("Cancelled.")
                return
            self.status_signal.emit("Checking Higgsfield price…")
            estimate = self.client.estimate(request)
            if self._cancel_requested:
                self.error_signal.emit("Cancelled.")
                return
            self.done_signal.emit(request, estimate)
        except Exception as exc:
            self.error_signal.emit(str(exc))


# OpenAIVideoWorker (Sora) was removed ahead of the scheduled 2026-09-24
# Videos API shutdown; no successor exists.


class VideoGenerationWorker(QThread):
    """Run a non-cancellable Gemini or Wan video task and save it locally."""

    status_signal = Signal(str)
    progress_signal = Signal(int, str)
    job_signal = Signal(object)
    done_signal = Signal(str)
    error_signal = Signal(str)

    def __init__(self, client, prompt: str, output_path, *, provider: str,
                 model: str, seconds: int, aspect_ratio: str,
                 timeout: int = 900, reference_images=()):
        super().__init__()
        self.client = client
        self.prompt = prompt
        self.reference_images = list(reference_images or ())
        self.output_path = Path(output_path)
        self.provider = provider
        self.model = model
        self.seconds = seconds
        self.aspect_ratio = aspect_ratio
        self.timeout = timeout
        # Neither a local poll deadline nor a local exception is a provider
        # verdict; the panel keeps the durable job row pending when either
        # flag is set.
        self.timed_out = False
        self.retryable = False
        self._cancelled = False

    def cancel(self):
        """Shutdown-only: the panel's Stop deliberately refuses mid-render
        for these providers. The durable row stays pending, so the next
        launch resumes watching; nothing is emitted for a closing window."""
        self._cancelled = True

    def run(self):
        try:
            self.status_signal.emit(f"Submitting to {self.provider}…")
            kwargs = ({"reference_images": self.reference_images}
                      if self.reference_images else {})
            job = self.client.create_video(
                self.prompt, model=self.model, seconds=self.seconds,
                aspect_ratio=self.aspect_ratio, **kwargs)
            self.job_signal.emit(job)

            def progress(current):
                self.job_signal.emit(current)
                self.progress_signal.emit(
                    int(getattr(current, "progress", 0) or 0),
                    f"{self.provider} rendering… ({current.status})")

            job = self.client.wait_video(
                job, timeout=self.timeout, on_progress=progress,
                should_cancel=lambda: self._cancelled)
            if self._cancelled:
                return
            if job.status != "completed":
                self.timed_out = (job.error or "").startswith("Timed out after")
                if not self.timed_out:
                    # A provider verdict is worth persisting; a local
                    # deadline is not — the render may still finish.
                    self.job_signal.emit(job)
                self.error_signal.emit(
                    job.error or f"{self.provider} render {job.status}")
                return
            self.job_signal.emit(job)

            self.status_signal.emit(f"Downloading {self.provider} video…")
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            self.output_path.write_bytes(self.client.download_video(job))
            self.done_signal.emit(str(self.output_path))
        except Exception as exc:
            # Provider verdicts exit through the status branch above; only
            # local failures (network, disk, key) reach here, and the
            # provider may still finish the submitted render.
            self.retryable = True
            self.error_signal.emit(str(exc))


class HiggsfieldWorker(QThread):
    """Submits a Higgsfield render, waits for it, and downloads the result.

    On a thread because a render takes minutes. The panel used to submit and
    then tell the user to go and look on Higgsfield's site, which is not a
    feature so much as a note apologising for the absence of one.

    Emits `status_signal` on every poll so the wait is legible rather than a
    frozen button.
    """
    status_signal = Signal(str)
    job_signal = Signal(object)   # latest VideoJob, for durable tracking
    done_signal = Signal(str)     # local path of the downloaded video
    error_signal = Signal(str)

    def __init__(self, client, prompt: str, output_path,
                 *, duration: int = 5, reference_image: str | None = None,
                 seed: int | None = None, timeout: int = 900,
                 prepared_request=None):
        super().__init__()
        self.client = client
        self.prompt = prompt
        self.output_path = Path(output_path)
        self.duration = duration
        self.reference_image = reference_image
        self.seed = seed
        self.timeout = timeout
        self.prepared_request = prepared_request
        # Neither a local poll deadline nor a local exception is a provider
        # verdict; the panel keeps the durable job row pending when either
        # flag is set.
        self.timed_out = False
        self.retryable = False
        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True

    def run(self):
        try:
            self.status_signal.emit("Submitting to Higgsfield…")
            if self.prepared_request is not None:
                job = self.client.generate_prepared(self.prepared_request)
            else:
                job = self.client.generate_video(
                    self.prompt, duration=self.duration,
                    reference_image=self.reference_image, seed=self.seed)
            self.job_signal.emit(job)

            def progress(current):
                self.job_signal.emit(current)
                self.status_signal.emit(f"Rendering… ({current.status})")

            job = self.client.wait(job, timeout=self.timeout,
                                   on_progress=progress,
                                   should_cancel=lambda: self._cancel_requested)
            if job.status != "completed" or not job.video_url:
                self.timed_out = (job.error or "").startswith("Timed out after")
                if not self.timed_out:
                    # A provider verdict is worth persisting; a local
                    # deadline is not — the render may still finish.
                    self.job_signal.emit(job)
                self.error_signal.emit(job.error or f"Render {job.status}")
                return
            self.job_signal.emit(job)

            self.status_signal.emit("Downloading…")
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            import requests
            with requests.get(job.video_url, stream=True, timeout=120) as response:
                response.raise_for_status()
                with open(self.output_path, "wb") as handle:
                    for chunk in response.iter_content(chunk_size=1 << 16):
                        if chunk:
                            handle.write(chunk)
            self.done_signal.emit(str(self.output_path))
        except Exception as exc:
            # Provider verdicts exit through the status branch above; only
            # local failures (network, disk, key) reach here, and the
            # provider may still finish the submitted render.
            self.retryable = True
            self.error_signal.emit(str(exc))


class VideoWorker(QThread):
    """Runs one vidforge render on a thread, reporting progress to Qt.

    vidforge's pipeline talks to a `Reporter` rather than printing, which is
    the seam that lets the same code drive the CLI and a progress bar. The
    reporter is created inside `run()` because it is the thread's own object:
    building it on the GUI thread and emitting from the worker is the usual way
    this goes wrong.

    Cancellation is cooperative and goes through the reporter — the pipeline
    calls `raise_if_cancelled()` between stages and inside the per-scene loops,
    so a cancelled render stops at the next checkpoint rather than being
    killed mid-ffmpeg with a half-written file.

    What a failed or stopped render already paid for crosses to the GUI as
    `trace_signal`, sent once just before done or error: the stages that
    began and the scene images saved (agents/video/studio.py
    partial_render_cost_usd prices it). The panel never receives the build on
    a failure, and Video and Social clips can render at once, so the trace is
    taken here rather than read back from the manifest or the image folder.
    """

    stage_signal = Signal(str, str)        # stage key, human label
    progress_signal = Signal(int, str)     # 0-100 overall, detail
    log_signal = Signal(str)
    done_signal = Signal(str, str)         # slug, video path
    error_signal = Signal(str)
    trace_signal = Signal(dict)            # {"stages": [...], "images": n}

    def __init__(self, topic: str = "", overrides: dict | None = None,
                 resume_slug: str = ""):
        super().__init__()
        self.topic = topic.strip()
        self.overrides = overrides or {}
        self.resume_slug = resume_slug.strip()
        self._reporter = None
        self._cancel_requested = False
        # Written on the worker thread only; handed over as a copy.
        self._stages: list[str] = []
        self._images = 0
        self._image_total = 0

    def _note_stage(self, stage_key: str) -> None:
        if stage_key not in self._stages:
            self._stages.append(stage_key)
        # Any stage after visuals means every scene image was saved.
        if stage_key != "visuals" and "visuals" in self._stages:
            self._images = max(self._images, self._image_total)

    def _note_scene(self, done: int, total: int) -> None:
        # vidforge reports scene k before illustrating it, so reaching it
        # proves scenes 0..k-1 have their images.
        self._images = max(self._images, int(done))
        self._image_total = max(self._image_total, int(total))

    def _note_visuals_left(self) -> None:
        # Asking for the next stage proves the last scene image was saved,
        # even when a Stop raises before that stage starts.
        self._images = max(self._images, self._image_total)

    def trace(self) -> dict:
        return {"stages": list(self._stages), "images": self._images}

    def cancel(self):
        self._cancel_requested = True
        if self._reporter is not None:
            self._reporter.cancel()

    def run(self):
        from agents.video import video_studio

        try:
            base = video_studio.reporter_base()

            worker = self

            class QtReporter(base):
                def begin(self, stage_key, detail=""):
                    # Before super(): a Stop pressed during the last scene
                    # image raises inside it, before on_stage records the
                    # next stage, and that image is saved and paid for.
                    if (getattr(self, "stage_key", None) == "visuals"
                            and stage_key != "visuals"):
                        worker._note_visuals_left()
                    super().begin(stage_key, detail)

                def substep(self, done, total, detail=""):
                    # Before super(): a Stop raises inside it, and the
                    # images up to this scene are already paid for.
                    if getattr(self, "stage_key", None) == "visuals":
                        worker._note_scene(done, total)
                    super().substep(done, total, detail)

                def on_stage(self, stage_key, detail):
                    from agents.video.studio import overall_fraction
                    worker._note_stage(stage_key)
                    label = dict((k, l) for k, l, _ in video_studio.stages()).get(
                        stage_key, stage_key)
                    worker.stage_signal.emit(stage_key, label)
                    worker.progress_signal.emit(
                        int(overall_fraction(stage_key) * 100), detail)

                def on_progress(self, stage_key, fraction, detail):
                    from agents.video.studio import overall_fraction
                    worker.progress_signal.emit(
                        int(overall_fraction(stage_key, fraction) * 100), detail)

                def on_log(self, message):
                    worker.log_signal.emit(message)

            self._reporter = QtReporter()
            if self._cancel_requested:      # cancelled before the thread started
                self._reporter.cancel()

            cfg = video_studio.load_config(self.overrides)
            build = video_studio.produce(
                cfg,
                topic=self.topic or None,
                resume_slug=self.resume_slug or None,
                reporter=self._reporter,
            )
            self.progress_signal.emit(100, "")
            self.trace_signal.emit(self.trace())
            self.done_signal.emit(build.slug, str(build.video_path))

        except Exception as exc:
            # Same thread, queued in order: the panel has the trace before
            # it handles the error.
            self.trace_signal.emit(self.trace())
            if type(exc).__name__ == "Cancelled":
                self.error_signal.emit("Cancelled.")
            else:
                self.error_signal.emit(f"{type(exc).__name__}: {exc}")


class ModelScanWorker(DaemonWorker):
    """Ask every configured cloud provider for its live model list.

    The Model updates check. One GET per provider to the same `/models`
    endpoint the dropdowns already use — free, and nothing is billed. Runs
    the providers one after another so a slow one delays the rest rather
    than racing them; each answer is emitted as it arrives.

    Then the image and video lane, on its own signals so nothing it finds
    can reach a chat menu: each media client's `list_media_models_live()`,
    and last the Higgsfield path probes, strictly one after another (a probe
    is slow and capped at its own timeout, so chat and media results are
    already painted by then). Media errors are "unsupported" for a list the
    provider does not serve here, else the message.
    """

    provider_listed = Signal(str, list, str)   # provider, models, error
    media_listed = Signal(str, list, str)      # provider, models, error
    path_probed = Signal(str, str, str)        # model, path, status

    def __init__(self, clients: dict, media_clients: dict | None = None,
                 probe=None, probe_paths=()):
        super().__init__()
        self.clients = dict(clients)
        self.media_clients = dict(media_clients or {})
        self.probe = probe                     # path -> status, or None
        self.probe_paths = tuple(probe_paths)  # ((model, path), ...)
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self):
        for provider, client in self.clients.items():
            if self._cancelled:
                return
            try:
                fetch = getattr(client, "list_models_live", None) \
                    or client.list_models
                self._emit(self.provider_listed, provider,
                           list(fetch() or []), "")
            except Exception as exc:
                self._emit(self.provider_listed, provider, [], str(exc))
        from services.model_watch import MEDIA_LIST_UNSUPPORTED, MediaListUnsupported
        for provider, client in self.media_clients.items():
            if self._cancelled:
                return
            try:
                self._emit(self.media_listed, provider,
                           list(client.list_media_models_live() or []), "")
            except MediaListUnsupported:
                self._emit(self.media_listed, provider, [], MEDIA_LIST_UNSUPPORTED)
            except Exception as exc:
                self._emit(self.media_listed, provider, [],
                           str(exc) or type(exc).__name__)
        if self.probe is None:
            return
        for model, path in self.probe_paths:
            if self._cancelled:
                return
            try:
                status = self.probe(path)
            except Exception:
                status = "unreachable"
            self._emit(self.path_probed, model, path, status)


class RatingsWorker(DaemonWorker):
    """Refresh the public per-task model ratings (LMArena), at most daily.

    Started beside the Model updates check. It pages through a Hugging Face
    dataset a second apart — about a minute — and is never waited on: the
    ranker keeps the cached or shipped ratings until this answers. It writes
    one file, the cache, by write-then-rename, so a quit that abandons the
    daemon thread mid-fetch leaves the previous cache intact; closeEvent
    therefore does not wait for it.
    """

    ratings_ready = Signal(object, str)   # RatingTable or None, error

    def run(self):
        from services.recommendations import ratings
        try:
            table = ratings.refresh()
        except Exception as exc:          # the service is often "loading"
            # Stamp the try: offline, the fetch used to repeat on every launch.
            ratings.note_attempt()
            self._emit(self.ratings_ready, None, str(exc))
            return
        self._emit(self.ratings_ready, table, "")


class VoiceListWorker(DaemonWorker):
    """List a speech provider's voices off the GUI thread (a network call)."""

    voices_signal = Signal(str, list, str)   # provider, [(name, id)], error

    def __init__(self, provider: str, lister):
        super().__init__()
        self.provider = provider
        self.lister = lister

    def run(self):
        try:
            voices = [(v["name"], v["id"]) for v in self.lister()]
            self._emit(self.voices_signal, self.provider, voices, "")
        except Exception as exc:
            self._emit(self.voices_signal, self.provider, [], str(exc))


class KeyProbeWorker(QThread):
    """Settings → API keys, the Test button: one metadata call off the UI thread.

    The client is built on the main thread by `services.api_keys.prepare_probe`
    (that is where the typed key is swapped into the environment for a
    moment); this thread only makes the call, so no environment mutation ever
    happens off the main thread. result_signal carries (kind, ok, note); the
    note never contains the key.
    """
    result_signal = Signal(str, bool, str)

    def __init__(self, kind: str, client):
        super().__init__()
        self._kind = kind
        self._client = client

    def run(self):
        from services.api_keys import run_probe
        ok, note = run_probe(self._kind, self._client)
        self.result_signal.emit(self._kind, ok, note)


class LocalDiscoveryWorker(DaemonWorker):
    """Read LM Studio, Ollama and free memory off the GUI thread.

    Reads and caches only; nothing here holds a Qt object or writes a file, so
    it is a daemon thread like the model lists.
    """

    result_signal = Signal(object)

    def __init__(self, lmstudio, ollama, inventory):
        super().__init__()
        self._lmstudio, self._ollama, self._inventory = lmstudio, ollama, inventory

    def run(self):
        self._emit(self.result_signal,
                   self._inventory.refresh(self._lmstudio, self._ollama))


class StartLMStudioWorker(DaemonWorker):
    """Run `lms server start` off the GUI thread (it can take a minute)."""

    result_signal = Signal(bool, str)

    def run(self):
        from services.lmstudio_client import LMStudioClient
        started, message = LMStudioClient.start_server()
        self._emit(self.result_signal, started, message)


class LocalMeasureWorker(QThread):
    """Measure one local model against the best cloud model (routing phase 3).

    The whole run — local answers, reference answers, judge calls — happens
    here, never on the GUI thread. A QThread rather than a DaemonWorker
    because the run is paid: closeEvent cancels it and waits, so a quit
    does not abandon a call that has been made but not billed. Every cloud
    call is reported through `usage_signal` and billed on the GUI thread;
    progress goes through `progress_signal`. `cancel()` stops it between
    prompts.
    """
    progress_signal = Signal(int, int)
    usage_signal = Signal(str, str, str, str)
    finished_signal = Signal(object)

    def __init__(self, model, plan, prompts, ask, store, cost, budget_eur):
        super().__init__()
        self.model, self.plan, self.prompts = model, plan, prompts
        self._ask, self._store, self._cost = ask, store, cost
        self.budget_eur = budget_eur
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        from services import local_ratings
        result = local_ratings.measure(
            self.model, self.plan, self.prompts, self._ask, store=self._store,
            on_progress=self.progress_signal.emit,
            on_usage=self.usage_signal.emit, cost=self._cost,
            budget_eur=self.budget_eur, cancelled=lambda: self._cancelled)
        self.finished_signal.emit(result)
