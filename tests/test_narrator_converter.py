"""
Imprint — narrator converter
============================
Type: Unit tests for EPUB reading order, resume safety, and the output format.

Three behaviours that are invisible when they break. A shuffled EPUB still
produces perfectly good audio, just in the wrong order. A resume onto edited
text still produces a file. A chapter mark at the wrong offset still opens.
None of them announce themselves, so they are pinned here.

Run with:  pytest tests/test_narrator_converter.py -v
"""

import os
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.narrator import converter


def _epub(path, sections, spine_order):
    """A minimal EPUB whose spine order differs from its file order."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr("META-INF/container.xml",
                    '<?xml version="1.0"?><container version="1.0" '
                    'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                    '<rootfiles><rootfile full-path="OEBPS/content.opf" '
                    'media-type="application/oebps-package+xml"/></rootfiles>'
                    '</container>')
        manifest, spine = [], []
        for item_id, filename, heading, body in sections:
            zf.writestr(f"OEBPS/{filename}",
                        f"<html><body><h1>{heading}</h1><p>{body}</p></body></html>")
            manifest.append(
                f'<item id="{item_id}" href="{filename}" '
                f'media-type="application/xhtml+xml"/>')
        for item_id in spine_order:
            spine.append(f'<itemref idref="{item_id}"/>')
        zf.writestr("OEBPS/content.opf",
                    '<?xml version="1.0"?>'
                    '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
                    'unique-identifier="id">'
                    '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
                    '<dc:identifier id="id">test</dc:identifier>'
                    '<dc:title>Test</dc:title><dc:language>en</dc:language>'
                    '</metadata>'
                    f'<manifest>{"".join(manifest)}</manifest>'
                    f'<spine>{"".join(spine)}</spine></package>')
    return path


# ── Reading order ────────────────────────────────────────────────────────────
def test_chapters_follow_the_spine_not_the_file_order(tmp_path):
    """`get_items()` returns manifest order. A book whose files are not named
    in reading order was narrated shuffled, and the audio sounded fine."""
    path = _epub(tmp_path / "b.epub", [
        ("c3", "zeta.xhtml", "Third", "gamma text"),
        ("c1", "alpha.xhtml", "First", "alpha text"),
        ("c2", "mid.xhtml", "Second", "beta text"),
    ], spine_order=["c1", "c2", "c3"])

    chapters = converter.extract_epub_chapters(path)
    assert [title for title, _ in chapters] == ["First", "Second", "Third"]
    assert "alpha text" in converter.load_text(path).split("beta text")[0]


def test_a_section_without_a_heading_still_gets_a_name(tmp_path):
    path = _epub(tmp_path / "b.epub",
                 [("c1", "a.xhtml", "", "body")], spine_order=["c1"])
    titles = [title for title, _ in converter.extract_epub_chapters(path)]
    assert titles and all(titles)


# ── Resume safety ────────────────────────────────────────────────────────────
def test_manifest_records_the_text_it_was_built_from(tmp_path):
    a = converter.build_manifest("Book", tmp_path / "b.epub", ["one", "two"])
    b = converter.build_manifest("Book", tmp_path / "b.epub", ["one", "three"])
    assert a["text_sha256"] != b["text_sha256"]


def test_edited_text_does_not_resume_onto_the_old_audio(tmp_path):
    """Same filename, same voice, same chunk size — only the text changed.
    That used to look 'compatible', so the run continued onto audio generated
    from text that no longer existed."""
    manifest_path = tmp_path / "manifest.json"
    temp_dir = tmp_path / "temp_audio"
    temp_dir.mkdir()
    source = tmp_path / "b.epub"

    converter.json_dump(manifest_path, converter.build_manifest(
        "Book", source, ["original one", "original two"]))
    stale = temp_dir / "chunk_0.mp3"
    stale.write_bytes(b"old audio")

    converter.load_or_create_manifest(
        manifest_path, "Book", source, ["edited one", "edited two"],
        temp_dir=temp_dir)

    assert not stale.exists(), "stale chunk survived a text change"


def test_an_unchanged_run_still_resumes(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    temp_dir = tmp_path / "temp_audio"
    temp_dir.mkdir()
    source = tmp_path / "b.epub"
    chunks = ["one", "two"]

    converter.json_dump(manifest_path,
                        converter.build_manifest("Book", source, chunks))
    kept = temp_dir / "chunk_0.mp3"
    kept.write_bytes(b"audio")

    converter.load_or_create_manifest(
        manifest_path, "Book", source, chunks, temp_dir=temp_dir)

    assert kept.exists(), "a resumable run threw away paid audio"


def test_the_refuse_policy_stops_instead_of_clearing(tmp_path, monkeypatch):
    """The refuse policy is for a CLI-only copy with an operator present: it
    asks rather than deciding. No shipped copy uses it since the standalone
    Audiobook Studio was merged into Imprint, but the branch stays covered."""
    monkeypatch.setattr(converter, "ON_SETTINGS_CHANGE",
                        converter.REFUSE_ON_CHANGE)
    manifest_path = tmp_path / "manifest.json"
    temp_dir = tmp_path / "temp_audio"
    temp_dir.mkdir()
    source = tmp_path / "b.epub"
    converter.json_dump(manifest_path,
                        converter.build_manifest("Book", source, ["old"]))
    kept = temp_dir / "chunk_0.mp3"
    kept.write_bytes(b"audio")

    with pytest.raises(RuntimeError, match="force-rebuild"):
        converter.load_or_create_manifest(
            manifest_path, "Book", source, ["new"], temp_dir=temp_dir)
    assert kept.exists(), "refusing should not delete anything either"


# ── Output format ────────────────────────────────────────────────────────────
def test_both_formats_are_offered_and_mp3_is_the_default():
    assert converter.AUDIO_FORMATS == ("mp3", "m4b")
    assert converter.DEFAULT_FORMAT == "mp3"


def test_chapter_metadata_places_each_chapter_at_a_measured_offset(
        tmp_path, monkeypatch):
    monkeypatch.setattr(converter, "get_audio_duration_seconds", lambda p: 2.0)
    chunks = [tmp_path / f"chunk_{i}.mp3" for i in range(4)]
    for path in chunks:
        path.write_bytes(b"x")

    written = converter.write_chapter_metadata(
        tmp_path, "Book", chunks, [("One", 0), ("Two", 2)])
    text = written.read_text()

    assert "START=0" in text and "END=4000" in text     # chunks 0–1
    assert "START=4000" in text and "END=8000" in text  # chunks 2–3
    assert "title=One" in text and "title=Two" in text


def test_m4b_really_carries_the_chapters(tmp_path):
    """End to end through real ffmpeg. The metadata file can be perfect and
    still not reach the container if the mapping flags are wrong, which is not
    visible from anything short of probing the output."""
    import json
    import shutil as _shutil
    import subprocess as _subprocess

    if not _shutil.which("ffmpeg") or not _shutil.which("ffprobe"):
        pytest.skip("ffmpeg/ffprobe not installed")

    for index in range(2):
        _subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
             f"sine=frequency={440 + index * 220}:duration=0.5", "-q:a", "6",
             str(tmp_path / f"chunk_{index}.mp3")], check=True)

    output = tmp_path / "Book.m4b"
    converter.merge_chunks_with_ffmpeg(
        tmp_path, output, 2, [("First", 0), ("Second", 1)], converter.FORMAT_M4B)

    probe = _subprocess.run(
        ["ffprobe", "-v", "error", "-show_chapters", "-of", "json", str(output)],
        capture_output=True, text=True, check=True)
    chapters = json.loads(probe.stdout)["chapters"]

    assert [c["tags"]["title"] for c in chapters] == ["First", "Second"]
    assert output.stat().st_size > 0


def test_mp3_is_a_stream_copy_with_no_chapter_file(tmp_path):
    import shutil as _shutil
    import subprocess as _subprocess

    if not _shutil.which("ffmpeg"):
        pytest.skip("ffmpeg not installed")

    for index in range(2):
        _subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
             f"sine=frequency=440:duration=0.5", "-q:a", "6",
             str(tmp_path / f"chunk_{index}.mp3")], check=True)

    output = tmp_path / "Book.mp3"
    converter.merge_chunks_with_ffmpeg(
        tmp_path, output, 2, [("First", 0)], converter.FORMAT_MP3)

    assert output.is_file() and output.stat().st_size > 0
    assert not (tmp_path / converter.CHAPTER_METADATA_FILENAME).exists()


def test_a_chapter_title_cannot_break_the_metadata_file(tmp_path, monkeypatch):
    """ffmetadata is key=value; an unescaped '=' or ';' in a title truncates
    or comments out the rest of the file."""
    monkeypatch.setattr(converter, "get_audio_duration_seconds", lambda p: 1.0)
    chunk = tmp_path / "chunk_0.mp3"
    chunk.write_bytes(b"x")

    written = converter.write_chapter_metadata(
        tmp_path, "Book", [chunk], [("Chapter 1 = the start; really # honestly", 0)])
    line = [l for l in written.read_text().splitlines()
            if l.startswith("title=Chapter")][0]

    assert r"\=" in line and r"\;" in line and r"\#" in line


def test_a_line_break_in_a_title_does_not_end_the_chapter_entry():
    """ffmetadata ends a value at a carriage return as well as a newline, so a
    CRLF heading used to keep only the words before the break."""
    assert (converter.ffmetadata_escape("Chapter One\r\nThe Beginning")
            == "Chapter One The Beginning")


def test_the_merge_refuses_a_format_it_does_not_know(tmp_path, monkeypatch):
    """Anything that was not "mp3" used to take the M4B branch and be renamed
    onto whatever suffix the caller asked for."""
    monkeypatch.setattr(converter, "ensure_ffmpeg_available", lambda: "ffmpeg")
    (tmp_path / "chunk_0.mp3").write_bytes(b"x")

    with pytest.raises(ValueError, match="wav"):
        converter.merge_chunks_with_ffmpeg(tmp_path, tmp_path / "Book.wav", 1, [], "wav")


# ── Chunking per format ──────────────────────────────────────────────────────
class _WordEncoder:
    """Counts words, so a chunk limit reads as a word limit."""

    def encode(self, text):
        return text.split()


def test_mp3_keeps_whole_book_chunk_boundaries(tmp_path, monkeypatch):
    """MP3 carries no chapter marks, so it chunks the whole book in one pass —
    the boundaries every earlier version drew. Chunking it per chapter moved
    all of them, and a run paused before that change met a 'settings changed'
    rebuild on resume that threw its paid chunks away. M4B needs each chapter
    on a chunk boundary and so chunks per chapter."""
    monkeypatch.setattr(converter, "get_token_encoder", _WordEncoder)
    monkeypatch.setattr(converter, "MAX_INPUT_TOKENS_PER_CHUNK", 4)

    def fake_tts(text, path, retries=2):
        path.write_bytes(b"x")
        return True

    monkeypatch.setattr(converter, "generate_tts_chunk", fake_tts)
    monkeypatch.setattr(converter, "merge_chunks_with_ffmpeg", lambda *a, **k: None)
    chapters = [("One", "a b c"), ("Two", "d e f g h")]      # 3 + 5 words
    source = tmp_path / "b.epub"
    manifest_path = tmp_path / "manifest.json"

    def run(audio_format):
        manifest_path.unlink(missing_ok=True)
        assert converter.text_to_audio(
            chapters, source, "Book", tmp_path / f"Book.{audio_format}",
            tmp_path / "temp_audio", manifest_path, audio_format=audio_format)
        return converter.json_load(manifest_path)

    whole_book = converter.chunk_text("\n\n".join(text for _, text in chapters), 4)
    mp3 = run("mp3")
    assert mp3["total_chunks"] == len(whole_book) == 2          # eight words in fours
    assert mp3["text_sha256"] == converter.build_manifest(
        "Book", source, whole_book)["text_sha256"]             # so an old manifest still matches

    assert run("m4b")["total_chunks"] == 3                      # One: 1 chunk; Two: 2


# ── Resume safety: a chunk stopped mid-stream ────────────────────────────────
class _Stream:
    """A stand-in for the OpenAI streaming response: writes some audio, then
    does as told."""

    def __init__(self, then):
        self.then = then

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def stream_to_file(self, path):
        Path(path).write_bytes(b"\xff\xfb" * 64)
        if self.then is not None:
            raise self.then


def _client(then):
    class Speech:
        class with_streaming_response:
            @staticmethod
            def create(**kwargs):
                return _Stream(then)

    class Audio:
        speech = Speech()

    class Client:
        audio = Audio()

    return Client()


def test_a_chunk_stopped_mid_stream_is_not_resumed_as_done(tmp_path, monkeypatch):
    """Stop in the audiobook panel kills the worker. The bytes already streamed
    used to sit under the chunk's final name, and the next run took that short
    file for a finished chunk and stitched a mid-sentence cut into the book."""
    final = tmp_path / "chunk_57.mp3"
    monkeypatch.setattr(converter, "get_client", lambda: _client(KeyboardInterrupt()))

    with pytest.raises(KeyboardInterrupt):
        converter.generate_tts_chunk("text", final, retries=1)

    assert not final.exists()
    manifest = {"chunks": [{"index": 57, "filename": final.name, "status": "done"}]}
    converter.sync_manifest_with_files(manifest, tmp_path)
    assert manifest["chunks"][0]["status"] == "pending"


def test_a_finished_chunk_lands_under_its_final_name_only(tmp_path, monkeypatch):
    final = tmp_path / "chunk_0.mp3"
    monkeypatch.setattr(converter, "get_client", lambda: _client(None))

    assert converter.generate_tts_chunk("text", final, retries=1)
    assert final.stat().st_size > 0
    assert list(tmp_path.glob("*" + converter.CHUNK_PARTIAL_SUFFIX)) == []


def test_a_failed_attempt_leaves_no_partial_behind(tmp_path, monkeypatch):
    final = tmp_path / "chunk_0.mp3"
    monkeypatch.setattr(converter, "get_client", lambda: _client(RuntimeError("dropped")))
    monkeypatch.setattr(converter.time, "sleep", lambda seconds: None)

    assert not converter.generate_tts_chunk("text", final, retries=2)
    assert not final.exists()
    assert list(tmp_path.glob("*" + converter.CHUNK_PARTIAL_SUFFIX)) == []


def test_cleanup_sweeps_partial_chunks_too(tmp_path):
    temp_dir = tmp_path / "temp_audio"
    temp_dir.mkdir()
    (temp_dir / "chunk_0.mp3").write_bytes(b"x")
    (temp_dir / ("chunk_1.mp3" + converter.CHUNK_PARTIAL_SUFFIX)).write_bytes(b"x")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}")

    converter.cleanup_after_success(temp_dir, manifest_path)

    assert not temp_dir.exists() and not manifest_path.exists()


def test_a_resume_sweeps_the_partial_a_stop_left_behind(tmp_path):
    """A kill skips the cleanup a caught failure gets, so the partial stays on
    disk; the next run should not carry it around."""
    partial = tmp_path / ("chunk_3.mp3" + converter.CHUNK_PARTIAL_SUFFIX)
    partial.write_bytes(b"x")
    manifest = converter.build_manifest("Book", tmp_path / "b.epub", ["one"])

    converter.sync_manifest_with_files(manifest, tmp_path)

    assert not partial.exists()


def test_a_manifest_from_before_partial_files_trusts_only_recorded_chunks(tmp_path):
    """Before partial files, a stop could leave a cut-short chunk under its
    final name. Such a manifest recorded a chunk as done only after its
    stream finished, so a present chunk it never recorded is the suspect one
    and is redone; the recorded ones stay."""
    (tmp_path / "chunk_0.mp3").write_bytes(b"complete")
    (tmp_path / "chunk_1.mp3").write_bytes(b"cut short")
    manifest = {"chunks": [
        {"index": 0, "filename": "chunk_0.mp3", "status": "done"},
        {"index": 1, "filename": "chunk_1.mp3", "status": "pending"},
    ]}                                                  # no "format": the old layout

    converter.sync_manifest_with_files(manifest, tmp_path)

    assert [c["status"] for c in manifest["chunks"]] == ["done", "pending"]
    assert (tmp_path / "chunk_0.mp3").exists()
    assert not (tmp_path / "chunk_1.mp3").exists()
    assert manifest["format"] == converter.MANIFEST_FORMAT

    # Under the new layout a present chunk is complete even if the manifest,
    # saved every few chunks, had not recorded it yet.
    (tmp_path / "chunk_1.mp3").write_bytes(b"complete by rename")
    manifest["chunks"][1]["status"] = "pending"
    converter.sync_manifest_with_files(manifest, tmp_path)
    assert manifest["chunks"][1]["status"] == "done"


# ── External tools ───────────────────────────────────────────────────────────
def test_calibres_epub_goes_into_the_temp_dir_and_leaves_with_it(tmp_path, monkeypatch):
    """`ebook-convert` wrote `<stem>.converted.epub` beside the audiobook, where
    nothing ever removed it. In the temp dir the usual cleanup takes it."""
    monkeypatch.setattr(converter, "ensure_ebook_convert_available", lambda: "ebook-convert")

    def fake_calibre(cmd, what):
        Path(cmd[2]).write_bytes(b"epub")
    monkeypatch.setattr(converter, "run_checked", fake_calibre)

    temp_dir = tmp_path / "temp_audio"                   # not there yet: a first run
    converted = converter.convert_mobi_to_epub(tmp_path / "Book.mobi", temp_dir)
    assert converted.parent == temp_dir and converted.exists()

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}")
    converter.cleanup_after_success(temp_dir, manifest_path)
    assert not temp_dir.exists()


def test_tools_run_in_the_launch_environment_not_the_bundles(monkeypatch):
    """PyInstaller points the linker at the bundle's libraries and stashes the
    launch-time value as <VAR>_ORIG; a tool must get the latter back. Checked
    on a real child process, not the helper's dictionary, so `run_checked`
    forgetting to pass the environment on would fail here."""
    monkeypatch.setenv("DYLD_LIBRARY_PATH", "/Bundle/Frameworks")
    monkeypatch.setenv("DYLD_LIBRARY_PATH_ORIG", "/launch/Frameworks")
    monkeypatch.setenv("LD_LIBRARY_PATH", "/Bundle/lib")
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG", raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")

    # LD_LIBRARY_PATH rather than DYLD_*: macOS strips the latter from any
    # child of a system binary, which the test's Python may be.
    probe = [sys.executable, "-c",
             "import os; print(os.environ.get('LD_LIBRARY_PATH'), os.environ['PATH'])"]

    seen = converter.run_checked(probe, "probe").stdout.split()
    assert seen[0] == "/Bundle/lib"                     # from source: nothing to undo
    assert seen[1].split(os.pathsep) == [
        "/usr/bin", "/bin", "/opt/homebrew/bin", "/usr/local/bin"]
    env = converter.subprocess_env()
    assert env["DYLD_LIBRARY_PATH"] == "/launch/Frameworks"
    assert "DYLD_LIBRARY_PATH_ORIG" not in env

    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/launch/lib")
    assert converter.run_checked(probe, "probe").stdout.split()[0] == "/launch/lib"

    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert converter.run_checked(probe, "probe").stdout.split()[0] == "None"


def test_a_tool_finders_bare_path_hides_is_still_found(tmp_path, monkeypatch):
    """An app launched from Finder gets a PATH without Homebrew, so a tool that
    works in Terminal is invisible to `shutil.which` alone."""
    homebrew = tmp_path / "homebrew"
    homebrew.mkdir()
    ffmpeg = homebrew / "ffmpeg"
    ffmpeg.write_text("#!/bin/sh\n")
    ffmpeg.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path / "nowhere"))
    monkeypatch.setattr(converter, "EXTRA_PATH_ENTRIES", (str(homebrew),))

    assert converter.ensure_ffmpeg_available() == str(ffmpeg)
    with pytest.raises(RuntimeError, match="ffprobe was not found"):
        converter.ensure_ffprobe_available()


def test_calibres_app_bundle_is_a_fallback_for_ebook_convert(tmp_path, monkeypatch):
    """Calibre's installer ships an app bundle and no PATH entry."""
    in_app = tmp_path / "calibre.app" / "ebook-convert"
    in_app.parent.mkdir()
    in_app.write_text("#!/bin/sh\n")
    monkeypatch.setenv("PATH", str(tmp_path / "nowhere"))
    monkeypatch.setattr(converter, "EXTRA_PATH_ENTRIES", ())
    monkeypatch.setattr(converter, "EBOOK_CONVERT_IN_APP",
                        str(in_app.relative_to(in_app.anchor)))

    with pytest.raises(RuntimeError, match="ebook-convert was not found"):
        converter.ensure_ebook_convert_available()       # present, not executable
    in_app.chmod(0o755)
    assert converter.ensure_ebook_convert_available() == str(in_app)


def test_a_failing_tool_reports_what_it_said(tmp_path):
    with pytest.raises(RuntimeError, match="ffprobe failed .*exit code 3") as info:
        converter.run_checked(
            [sys.executable, "-c", "import sys; sys.stderr.write('no such stream'); sys.exit(3)"],
            "ffprobe")
    assert "no such stream" in str(info.value)

    with pytest.raises(RuntimeError, match="ffmpeg could not be started"):
        converter.run_checked([str(tmp_path / "missing-ffmpeg")], "ffmpeg")


# ── One run per book ─────────────────────────────────────────────────────────
def test_a_second_run_on_the_same_book_is_refused(tmp_path):
    """Two runs share the manifest and the chunk names, so each could publish
    or delete the other's work."""
    lock = tmp_path / converter.LOCK_FILENAME
    with converter.BookLock(tmp_path):
        assert lock.read_text() == str(os.getpid())
        with pytest.raises(converter.BookLocked, match=f"pid {os.getpid()}"):
            with converter.BookLock(tmp_path):
                pass
        assert lock.read_text() == str(os.getpid())      # the loser touched nothing
    assert not lock.exists()


def test_the_lock_goes_with_the_run_even_when_it_fails(tmp_path):
    with pytest.raises(RuntimeError, match="boom"):
        with converter.BookLock(tmp_path):
            raise RuntimeError("boom")
    assert not (tmp_path / converter.LOCK_FILENAME).exists()


def test_a_lock_left_by_a_killed_run_is_taken_over(tmp_path):
    """Stop in the tab kills the worker, which never releases. Its pid is gone,
    so the next run takes the folder."""
    import subprocess as _subprocess
    gone = _subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait()
    assert converter.pid_is_alive(os.getpid())
    assert not converter.pid_is_alive(gone.pid)

    lock = tmp_path / converter.LOCK_FILENAME
    lock.write_text(str(gone.pid))
    with converter.BookLock(tmp_path):
        assert lock.read_text() == str(os.getpid())
    assert not lock.exists()


def test_a_lock_that_names_no_pid_is_left_for_a_human(tmp_path):
    """Nothing can tell an empty lock from one a run is still writing, so it
    is refused with the way out spelled out rather than deleted."""
    lock = tmp_path / converter.LOCK_FILENAME
    lock.write_text("")
    with pytest.raises(converter.BookLocked, match="delete"):
        with converter.BookLock(tmp_path):
            pass
    assert lock.exists()


def test_a_run_refuses_a_book_another_run_holds(tmp_path, monkeypatch, capsys):
    """Through convert(): the refusal comes before the text is read, and the
    run reports failure so the tab shows it."""
    monkeypatch.setattr(converter, "ensure_ffmpeg_available", lambda: "ffmpeg")
    monkeypatch.setattr(converter, "load_chapters",
                        lambda *a, **k: pytest.fail("the text was read"))
    book = tmp_path / "Book.txt"
    book.write_text("Some text.")
    out = tmp_path / "out"
    lock = out / "Book" / converter.LOCK_FILENAME
    lock.parent.mkdir(parents=True)
    lock.write_text(str(os.getpid()))

    assert converter.convert(input=str(book), output=str(out)) is False
    assert "Another conversion of Book is running" in capsys.readouterr().out
    assert lock.read_text() == str(os.getpid())


def test_a_finished_book_leaves_no_lock_behind(tmp_path, monkeypatch):
    monkeypatch.setattr(converter, "ensure_ffmpeg_available", lambda: "ffmpeg")
    monkeypatch.setattr(converter, "load_chapters", lambda *a, **k: [("Book", "Some text.")])
    monkeypatch.setattr(converter, "count_text_tokens", lambda text: 3)   # no tiktoken fetch
    monkeypatch.setattr(converter, "text_to_audio", lambda **k: True)
    monkeypatch.setattr(converter, "get_audio_duration_seconds", lambda p: 1.0)
    book = tmp_path / "Book.txt"
    book.write_text("Some text.")
    out = tmp_path / "out"

    assert converter.convert(input=str(book), output=str(out)) is True
    assert not (out / "Book" / converter.LOCK_FILENAME).exists()


# ── Narration routes ─────────────────────────────────────────────────────────
# OpenAI removes gpt-4o-mini-tts on 2027-01-06, so Booth gained a second route.
# The rules below are the ones that protect money already spent: a book paused
# before routes existed must resume, and a change of route must not stitch two
# voices together.

@pytest.fixture
def route(monkeypatch):
    """Set the module's route the way convert() does, undone afterwards."""
    def use(provider, voice=None):
        spec = converter.TTS_PROVIDERS[provider]
        monkeypatch.setattr(converter, "TTS_PROVIDER", provider)
        monkeypatch.setattr(converter, "TTS_MODEL", spec["model"])
        monkeypatch.setattr(converter, "TTS_VOICE", voice or spec["voice"])
    use("openai")
    return use


def test_a_manifest_from_before_routes_still_resumes(tmp_path, route):
    manifest_path = tmp_path / "manifest.json"
    temp_dir = tmp_path / "temp_audio"
    temp_dir.mkdir()
    source = tmp_path / "b.epub"
    chunks = ["one", "two"]
    old = converter.build_manifest("Book", source, chunks)
    del old["tts_provider"], old["max_chars_per_chunk"]        # written pre-routes
    converter.json_dump(manifest_path, old)
    kept = temp_dir / "chunk_0.mp3"
    kept.write_bytes(b"paid audio")

    converter.load_or_create_manifest(
        manifest_path, "Book", source, chunks, temp_dir=temp_dir)
    assert kept.exists(), "a paused OpenAI book lost its paid chunks to the upgrade"


def test_a_change_of_route_does_not_resume_onto_the_other_voice(tmp_path, route):
    manifest_path = tmp_path / "manifest.json"
    temp_dir = tmp_path / "temp_audio"
    temp_dir.mkdir()
    source = tmp_path / "b.epub"
    chunks = ["one", "two"]
    converter.json_dump(manifest_path, converter.build_manifest("Book", source, chunks))
    stale = temp_dir / "chunk_0.mp3"
    stale.write_bytes(b"openai audio")
    route("elevenlabs")
    converter.load_or_create_manifest(
        manifest_path, "Book", source, chunks, temp_dir=temp_dir)
    assert not stale.exists()


def test_a_character_cap_applies_only_to_routes_that_have_one(monkeypatch):
    monkeypatch.setattr(converter, "get_token_encoder", _WordEncoder)
    text = " ".join(["abcdefghij"] * 20)                       # 20 words, 219 chars
    assert len(converter.chunk_text(text, 1000)) == 1          # no cap: one chunk
    capped = converter.chunk_text(text, 1000, max_chars=50)
    assert all(len(chunk) <= 50 for chunk in capped) and len(capped) == 5


class _Response:
    def __init__(self, payload=b"ID3 mp3 bytes"):
        self._payload = payload
        self._read = False

    def read(self, size=-1):
        if self._read:
            return b""
        self._read = True
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_elevenlabs_receives_the_documented_request(tmp_path, monkeypatch, route):
    import urllib.request
    route("elevenlabs", voice="voice id/1")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-not-a-real-key")
    seen = {}

    def fake_urlopen(request, timeout=None):
        seen["url"] = request.full_url
        seen["headers"] = dict(request.header_items())
        seen["body"] = __import__("json").loads(request.data)
        return _Response()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    target = tmp_path / "chunk_3.mp3"
    assert converter.generate_tts_chunk("Middle.", target, retries=1,
                                        previous_text="Before.", next_text="After.")
    assert target.read_bytes() == b"ID3 mp3 bytes"
    assert seen["url"] == ("https://api.elevenlabs.io/v1/text-to-speech/voice%20id%2F1"
                           "?output_format=mp3_44100_128")
    assert seen["body"] == {"text": "Middle.", "model_id": "eleven_multilingual_v2",
                            "previous_text": "Before.", "next_text": "After."}
    assert seen["headers"]["Xi-api-key"] == "test-not-a-real-key"


def test_a_refused_key_stops_without_retrying(tmp_path, monkeypatch, route):
    import io
    import urllib.error
    import urllib.request
    route("elevenlabs")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-not-a-real-key")
    calls = []

    def refuse(request, timeout=None):
        calls.append(1)
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {},
                                     io.BytesIO(b'{"detail":"invalid api key"}'))

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(converter.time, "sleep", lambda s: None)
    target = tmp_path / "chunk_0.mp3"
    assert converter.generate_tts_chunk("Text.", target, retries=3) is False
    assert len(calls) == 1
    assert not target.exists()
    assert not list(tmp_path.glob("*.part"))


def test_the_worker_gives_elevenlabs_its_neighbours(tmp_path, monkeypatch, route):
    route("elevenlabs")
    monkeypatch.setattr(converter, "get_token_encoder", _WordEncoder)
    monkeypatch.setattr(converter, "MAX_INPUT_TOKENS_PER_CHUNK", 2)
    monkeypatch.setattr(converter, "MAX_WORKERS", 1)
    calls = []

    def fake_tts(text, path, retries=2, previous_text=None, next_text=None):
        calls.append((text, previous_text, next_text))
        path.write_bytes(b"x")
        return True

    monkeypatch.setattr(converter, "generate_tts_chunk", fake_tts)
    monkeypatch.setattr(converter, "merge_chunks_with_ffmpeg", lambda *a, **k: None)
    assert converter.text_to_audio(
        [("Book", "a b c d e f")], tmp_path / "b.epub", "Book",
        tmp_path / "Book.mp3", tmp_path / "temp_audio", tmp_path / "m.json")
    assert sorted(calls) == [("a b", None, "c d"), ("c d", "a b", "e f"),
                             ("e f", "c d", None)]


def test_a_failed_chunk_stops_the_queue_instead_of_paying_for_the_rest(
        tmp_path, monkeypatch, route):
    monkeypatch.setattr(converter, "get_token_encoder", _WordEncoder)
    monkeypatch.setattr(converter, "MAX_INPUT_TOKENS_PER_CHUNK", 1)
    monkeypatch.setattr(converter, "MAX_WORKERS", 1)
    attempted = []

    def fake_tts(text, path, retries=2):
        attempted.append(text)
        return False                                     # first chunk fails

    monkeypatch.setattr(converter, "generate_tts_chunk", fake_tts)
    words = " ".join(f"w{i}" for i in range(30))
    assert converter.text_to_audio(
        [("Book", words)], tmp_path / "b.epub", "Book", tmp_path / "Book.mp3",
        tmp_path / "temp_audio", tmp_path / "m.json") is False
    assert len(attempted) < 5, f"kept generating after the failure: {len(attempted)}"


def test_a_route_without_its_key_sends_nothing(tmp_path, monkeypatch, route, capsys):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setattr(converter, "load_dotenv", lambda *a, **k: False)
    monkeypatch.setattr(converter, "generate_tts_chunk",
                        lambda *a, **k: pytest.fail("a request was sent"))
    book = tmp_path / "b.txt"
    book.write_text("Some text to narrate.")
    assert converter.convert(input=str(book), output=str(tmp_path / "out"),
                             provider="elevenlabs") is False
    assert "needs ELEVENLABS_API_KEY" in capsys.readouterr().out


def _wav(seconds=0.2, rate=24000):
    import io
    import wave
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(b"\0\0" * int(rate * seconds))
    return buffer.getvalue()


def test_gemini_narrates_a_chunk_as_mp3_with_one_request(tmp_path, monkeypatch, route):
    """Through the real google-genai SDK against a mock transport: the request
    carries the documented fields, a 5xx is not retried (the Interactions
    layer retried once by default — a second bill), and the WAV it returns
    lands as MP3 under the chunk's final name."""
    import base64
    import json
    import shutil as _shutil
    import httpx
    if not _shutil.which("ffmpeg"):
        pytest.skip("ffmpeg is not installed")
    route("gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    monkeypatch.setattr(converter, "_GEMINI_CLIENT", None)
    sent = []
    replies = [httpx.Response(503, json={"error": {"code": 503, "message": "busy",
                                                   "status": "UNAVAILABLE"}}),
               httpx.Response(200, json={
                   "id": "i1", "status": "completed",
                   "steps": [{"type": "model_output", "content": [
                       {"type": "audio", "mime_type": "audio/wav",
                        "data": base64.b64encode(_wav()).decode()}]}]})]

    def handler(request):
        sent.append(json.loads(request.content))
        return replies.pop(0)

    build = converter.gemini_client
    mock = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(converter, "gemini_client",
                        lambda httpx_client=None: build(httpx_client=mock))
    monkeypatch.setattr(converter.time, "sleep", lambda s: None)
    target = tmp_path / "chunk_0.mp3"
    assert converter.generate_tts_chunk("Call me Ishmael.", target, retries=2)
    assert len(sent) == 2               # one per attempt: the SDK added none
    body = sent[0]
    assert body["model"] == "gemini-3.8-flash-tts"
    assert body["response_format"] == {"type": "audio", "mime_type": "audio/wav",
                                       "sample_rate": 24000}
    assert body["generation_config"] == {"speech_config": [{"voice": "Kore"}]}
    data = target.read_bytes()
    assert data[:3] == b"ID3" or data[:2] == b"\xff\xfb" or data[:2] == b"\xff\xf3"
    assert not list(tmp_path.glob("*.wav")) and not list(tmp_path.glob("*.part*"))


def test_gemini_quota_stops_the_run(tmp_path, monkeypatch, route):
    import httpx
    route("gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429, json={"error": {"code": "quota_exceeded",
                                                   "message": "daily quota"}})

    build = converter.gemini_client
    mock = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(converter, "gemini_client",
                        lambda httpx_client=None: build(httpx_client=mock))
    assert converter.generate_tts_chunk("Text.", tmp_path / "chunk_0.mp3",
                                        retries=3) is False
    assert len(calls) == 1
