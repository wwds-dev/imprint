"""Herald's background delivery (audit 2026-11-23, code-review P1-2).

Post Now used to call ``publisher.publish`` in the click handler: the whole
upload, and for YouTube Google's consent wait, ran on the UI thread, so
closing the consent tab froze the window until force-quit.
"""

from PySide6.QtCore import Signal

from ui.workers import DaemonWorker


class PublishWorker(DaemonWorker):
    """Runs one ``publisher.publish(...)`` off the UI thread.

    A DaemonWorker (ADR 0006, point 4): network only, it holds no Qt objects
    and writes nothing; the delivery queue is updated by the panel's slots on
    the GUI thread. Quitting mid-upload abandons the thread; the job stays
    ``publishing`` and ``queue.recover_interrupted`` marks it for review at
    the next launch, as after a crash.

    Connect the signals to bound methods of a QObject (the panel), so they
    are delivered on the GUI thread by queued connection.
    """

    posted = Signal(object, object)   # job id, PublishResult
    failed = Signal(object, object)   # job id, the exception

    def __init__(self, publisher, job_id, body: str, media_path: str,
                 **kwargs):
        super().__init__()
        self._publisher = publisher
        self.job_id = job_id
        self._body = body
        self._media_path = media_path
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._publisher.publish(
                self._body, self._media_path, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 - every failure is reported
            self._emit(self.failed, self.job_id, exc)
            return
        self._emit(self.posted, self.job_id, result)
