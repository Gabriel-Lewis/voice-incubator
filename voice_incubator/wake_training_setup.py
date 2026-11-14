"""What training a wake word needs that the image doesn't carry, installed
when the Wake words page asks: TensorFlow, in a Python of its own (about 2 GB
installed, which most homes never use), and the training kit (downloaded:
voice_incubator/downloads.py, ``kit``).

TensorFlow is installed as Home Assistant's Piper and Whisper apps install
their packs: uv downloads the pinned wheels (wake_trainer_requirements.txt,
from requirements-training.txt) into a cache in the data folder
(``<data>/uv-cache``: kept across updates, left out of backups), and the
Python it installs into is made of links into that cache (symlinks: the
data folder is another mount). That Python is outside the data folder and
goes with the container, so it is made again from the cache at every start
-- offline, in under a second. A new Python (its minor version) or new pins
empty the cache first, and the next start downloads again.

Unlike those apps it is a venv of its own, not the app's Python: the trainer
is a process of its own already (voice_incubator/wake_training.py) and
imports nothing of the app, so TensorFlow's numpy can't move the app's, and
nothing needs a restart. Installed is wanted: the cache's ``SERIES`` file and
the kit's marker (downloads.KIT_MARKER) say so at the next start.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import os
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from . import downloads

_LOGGER = logging.getLogger(__name__)

LOCK = Path(__file__).with_name("wake_trainer_requirements.txt")
SERIES = ".series"
"""In the cache: the Python and pins it holds wheels for (``series``)."""
TRAINER_DOWNLOAD_MB = {"amd64": 640, "aarch64": 350}
"""What the pinned wheels download, by architecture (TensorFlow is most of it)."""
TRAINER_DISK_MB = {"amd64": 2000, "aarch64": 1500}
"""What they take in the cache, unpacked."""


class SetupError(Exception):
    """Why what training needs couldn't be installed."""


def find_uv() -> str | None:
    """uv: the image's, or the one pip installed with the app."""
    found = shutil.which("uv")
    if found:
        return found
    with contextlib.suppress(ImportError, FileNotFoundError):
        from uv import find_uv_bin  # pylint: disable=import-outside-toplevel

        return find_uv_bin()
    return None


def _size(path: Path) -> int:
    """Bytes under ``path``, its links not followed."""
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            with contextlib.suppress(OSError):
                total += os.lstat(os.path.join(root, name)).st_size
    return total


class TrainingSetup:
    """Installs, keeps and removes the trainer's Python and the kit."""

    def __init__(self, data_dir: Path, venv: Path, models: Path, lock: Path = LOCK, uv: str | None = None) -> None:
        self.cache = data_dir / "uv-cache"
        self.venv = venv
        """Outside the data folder: made again at every start."""
        self.models = models
        self.lock = lock
        self.log_path = data_dir / "wake_training" / "install.log"
        self.uv = uv if uv is not None else find_uv()
        self.ready = False
        """The venv is made, from the cache."""
        self.generation = 0
        """Counts what changed the trainer's Python (installs, removals)."""
        self.stage: str | None = None
        """What it is installing: trainer or kit."""
        self.error: str | None = None
        self.kit_download: downloads.Downloader | None = None
        self.disk_bytes: int | None = None
        """What it installed takes on disk, when known."""
        self._task: asyncio.Task | None = None
        self._measuring: asyncio.Task | None = None

    # -------------------------------------------------------------- state

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def python(self) -> str | None:
        """The trainer's Python, when it is installed."""
        return str(self.venv / "bin" / "python") if self.ready else None

    def series(self) -> str:
        digest = hashlib.sha256(self.lock.read_bytes()).hexdigest()[:16]
        return f"python={sys.version_info[0]}.{sys.version_info[1]} pins={digest}"

    @property
    def trainer_wanted(self) -> bool:
        return (self.cache / SERIES).is_file()

    @property
    def kit_folder(self) -> Path:
        return (self.models / downloads.KIT_FOLDER).resolve()

    @property
    def kit_wanted(self) -> bool:
        return (self.kit_folder / downloads.KIT_MARKER).is_file()

    @property
    def installed(self) -> bool:
        """Something it installed is here (which Remove takes away)."""
        return self.trainer_wanted or self.kit_wanted

    def can_install(self, part: str) -> bool:
        """Whether it can install ``part`` (trainer, kit) here."""
        if part == "trainer":
            return self.uv is not None and self.lock.is_file()
        return downloads.kit() is not None

    def download_mb(self, parts: list[str]) -> int:
        """About how much installing ``parts`` downloads."""
        arch = downloads.ARCHES.get(platform.machine(), "amd64")
        total = TRAINER_DOWNLOAD_MB.get(arch, 640) if "trainer" in parts else 0
        if "kit" in parts:
            total += round(sum(f.size for _, f in downloads.kit_missing(self.models)) / 1e6)
        return total

    def disk_mb(self, parts: list[str]) -> int:
        """About how much installing ``parts`` takes on disk."""
        arch = downloads.ARCHES.get(platform.machine(), "amd64")
        total = TRAINER_DISK_MB.get(arch, 2000) if "trainer" in parts else 0
        if "kit" in parts:
            total += round(downloads.kit_unpacked() / 1e6)
        return total

    def status(self, needs: list[str]) -> dict[str, Any]:
        out: dict[str, Any] = {
            "needs": needs,
            "installing": self.stage if self.running else None,
            "error": self.error,
            "installed": self.installed,
            "download_mb": self.download_mb(needs),
            "disk_mb": self.disk_mb(needs),
            "used_mb": None if self.disk_bytes is None else round(self.disk_bytes / 1e6),
        }
        if self.running and self.stage == "kit" and self.kit_download is not None:
            download = self.kit_download
            out["progress"] = round(download.done / download.total, 4) if download.total else 0.0
            out["download_error"] = download.error
        return out

    def log(self) -> str:
        try:
            return self.log_path.read_text("utf-8", errors="replace")
        except OSError:
            return ""

    # ---------------------------------------------------------------- run

    def install(self, parts: list[str]) -> None:
        """Install ``parts`` (trainer, kit) in the background."""
        if self.running:
            raise SetupError("Training is being installed already.")
        for part in parts:
            if not self.can_install(part):
                raise SetupError("uv isn't installed." if part == "trainer" else "The training kit isn't published.")
        self.error = None
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("", "utf-8")
        self.stage = parts[0]  # said from now, not once the task runs
        self._task = asyncio.ensure_future(self._run(parts))

    def restore(self) -> None:
        """At start: what was installed before, made again (the trainer's
        Python from the cache; the rest of a kit whose download stopped)."""
        parts = []
        if self.trainer_wanted and self.can_install("trainer"):
            parts.append("trainer")
        if self.kit_wanted and downloads.kit_missing(self.models):
            parts.append("kit")
        if parts:
            self.stage = parts[0]
            self._task = asyncio.ensure_future(self._run(parts))
        elif self.installed:
            self._measuring = asyncio.ensure_future(self._measure())

    async def remove(self) -> None:
        """What it installed taken away -- and an install stopped."""
        await self.stop()
        self.ready = False
        self.generation += 1
        self.error = None
        await asyncio.to_thread(self._remove)
        self.disk_bytes = None
        _LOGGER.info("Removed what training a wake word needs")

    def _remove(self) -> None:
        shutil.rmtree(self.venv, ignore_errors=True)
        shutil.rmtree(self.cache, ignore_errors=True)
        folder = self.kit_folder
        if (folder / downloads.KIT_MARKER).is_file():  # downloaded, not made by hand
            for child in folder.iterdir():
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)

    async def stop(self) -> None:
        if self.running:
            assert self._task is not None
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    async def _run(self, parts: list[str]) -> None:
        try:
            if "trainer" in parts:
                self.stage = "trainer"
                await self._trainer()
            if "kit" in parts:
                self.stage = "kit"
                await self._kit()
            _LOGGER.info("Wake word training is ready (%s)", ", ".join(parts))
        except asyncio.CancelledError:
            raise
        except (SetupError, OSError) as err:
            self.error = str(err)
            _LOGGER.error("Couldn't install what training a wake word needs: %s", err)
        finally:
            self.stage = None
            self.kit_download = None
        await self._measure()

    async def _measure(self) -> None:
        def measure() -> int:
            total = _size(self.cache) if self.cache.is_dir() else 0
            if self.kit_wanted:
                total += _size(self.kit_folder)
            return total

        self.disk_bytes = await asyncio.to_thread(measure)

    async def _trainer(self) -> None:
        """The venv, from the cache: offline when the cache is of these pins
        (at a start it is all there), else downloading what isn't."""
        series = self.series()
        marker = self.cache / SERIES
        try:
            cached = marker.read_text("utf-8").strip()
        except OSError:
            cached = None
        if cached is not None and cached != series:
            _LOGGER.info("Emptying the trainer's cache: %s -> %s", cached, series)
            await asyncio.to_thread(shutil.rmtree, self.cache, True)
        self.cache.mkdir(parents=True, exist_ok=True)
        marker.write_text(series + "\n", "utf-8")
        self.ready = False
        self.generation += 1
        started = time.monotonic()
        await self._uv("venv", "--clear", "--python", sys.executable, str(self.venv))
        install = ["pip", "install", "--python", str(self.venv / "bin" / "python"), "--require-hashes", "-r", str(self.lock)]
        try:
            if cached != series:
                raise SetupError("nothing cached")
            await self._uv(*install, "--offline")
            _LOGGER.info("Made the wake word trainer's Python from its cache in %.1f s", time.monotonic() - started)
        except SetupError:
            _LOGGER.info("Downloading TensorFlow for the wake word trainer")
            await self._uv(*install)
        self.ready = True
        self.generation += 1

    async def _uv(self, *args: str) -> None:
        assert self.uv is not None
        env = {
            **os.environ,
            "UV_CACHE_DIR": str(self.cache),
            "UV_LINK_MODE": "symlink",
            "UV_PYTHON_DOWNLOADS": "never",
            "UV_NO_PROGRESS": "1",
            "NO_COLOR": "1",
        }
        for name in ("VIRTUAL_ENV", "UV_SYSTEM_PYTHON", "UV_PYTHON", "PYTHONPATH"):
            env.pop(name, None)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as log:
            log.write(f"$ uv {' '.join(args)}\n")
            log.flush()
            process = await asyncio.create_subprocess_exec(
                self.uv, args[0], "--no-config", "--color", "never", *args[1:], env=env,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
            )
            lines: list[str] = []
            try:
                assert process.stdout is not None
                async for raw in process.stdout:
                    line = raw.decode(errors="replace").rstrip()
                    log.write(line + "\n")
                    if line:
                        lines.append(line)
                code = await process.wait()
            except asyncio.CancelledError:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                await process.wait()
                raise
        if code != 0:
            # uv says what went wrong last ("error: ..."), its causes after.
            said = next((line for line in lines if line.startswith("error:")), lines[-1] if lines else f"exit {code}")
            raise SetupError(said.removeprefix("error: ").strip())

    async def _kit(self) -> None:
        todo = downloads.kit_missing(self.models)
        if not todo:
            return
        folder = self.kit_folder
        folder.mkdir(parents=True, exist_ok=True)
        (folder / downloads.KIT_MARKER).write_text("", "utf-8")
        self.kit_download = downloads.Downloader(todo)
        await self.kit_download.run()
