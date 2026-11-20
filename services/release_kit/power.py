"""Keep the Mac awake while a kit runs (owner decision 8, spec A6).

`caffeinate -i -w <app pid>` prevents idle system sleep only: the display may
sleep, and a closed lid still sleeps the Mac. `-w` ends the assertion if
Imprint exits or crashes, so a crash never leaves the Mac held awake.
No native calls in-process (see ui/appkit_guard.py for why).
"""

from __future__ import annotations

import os
import shutil
import subprocess


class KeepAwake:
    def __init__(self, *, popen=subprocess.Popen, which=shutil.which,
                 pid: int | None = None):
        self._popen = popen
        self._which = which
        self._pid = pid or os.getpid()
        self._proc = None

    @property
    def held(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def acquire(self) -> bool:
        """Start holding; False when `caffeinate` is not available."""
        if self.held:
            return True
        exe = self._which("caffeinate")
        if not exe:
            return False
        self._proc = self._popen(
            [exe, "-i", "-w", str(self._pid)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True

    def release(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        except OSError:
            pass
