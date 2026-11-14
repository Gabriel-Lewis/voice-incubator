"""What training a wake word needs, installed from the Wake words page
(voice_incubator/wake_training_setup.py): the trainer's Python from uv's
cache, the kit downloaded -- and what installing would mend, said."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from aiohttp import web

from voice_incubator import downloads, wake_training_setup
from voice_incubator.downloads import File, Model
from voice_incubator.wake_training import Kit, TrainingError, WakeTraining
from voice_incubator.wake_training_setup import SERIES, TrainingSetup, find_uv

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("publish_kit", ROOT / "scripts/publish_wake_training_kit.py")
publish = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(publish)


def make_kit(directory: Path) -> Path:
    (directory / "negatives/speech/training/speech_mmap").mkdir(parents=True)
    (directory / "negatives/speech/training/speech_mmap/data.ninja").write_bytes(b"\0" * 4000)
    (directory / "background/noise").mkdir(parents=True)
    (directory / "background/noise/a.wav").write_bytes(b"RIFF")
    (directory / "kit.yaml").write_text(
        "version: 1\nnegatives:\n- {name: speech, sampling_weight: 25.0, penalty_weight: 50.0}\nbackground: background\n"
    )
    return directory


async def serve(files: dict[str, bytes], broken: set[str]) -> tuple[web.AppRunner, str]:
    async def one(request: web.Request) -> web.Response:
        name = request.match_info["name"]
        if name not in files:
            raise web.HTTPNotFound()
        return web.Response(body=b"corrupt" if name in broken else files[name])

    application = web.Application()
    application.router.add_get("/{name:.*}", one)
    runner = web.AppRunner(application)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]  # pylint: disable=protected-access
    return runner, f"http://127.0.0.1:{port}"


def test_the_kit_as_published(tmp_path, monkeypatch):
    """Not offered until it has a revision; kit.yaml last; what the app has
    in its manifest is the working copy's kit."""
    manifest = tmp_path / "kit.json"
    spec = {"repo": "rhasspy/models", "path": "wake-training", "revision": None, "unpacked": 2000,
            "files": [{"name": "negatives/speech.tar.gz", "sha256": "ab", "size": 10, "unpack": "negatives/speech"},
                      {"name": "kit.yaml", "sha256": "cd", "size": 1}]}
    manifest.write_text(json.dumps(spec))
    monkeypatch.setattr(downloads, "KIT_MANIFEST", manifest)
    assert downloads.kit() is None and downloads.kit_missing(tmp_path) == []
    manifest.write_text(json.dumps({**spec, "revision": "abc123"}))
    kit = downloads.kit()
    assert kit is not None and kit.folder == "wake-training" and downloads.kit_unpacked() == 2000
    assert kit.files[0].url == "https://huggingface.co/rhasspy/models/resolve/abc123/wake-training/negatives/speech.tar.gz"
    assert kit.files[0].unpack == "negatives/speech" and kit.files[-1].name == "kit.yaml"
    assert [path.relative_to(tmp_path / "wake-training").as_posix() for path, _ in downloads.kit_missing(tmp_path)] == [
        "negatives/speech", "kit.yaml"]

    monkeypatch.undo()
    real = json.loads(downloads.KIT_MANIFEST.read_text())
    assert real["files"][-1]["name"] == "kit.yaml" and real["path"] == downloads.KIT_FOLDER
    local = ROOT / "models/wake-training/kit.yaml"
    if local.is_file():
        assert real["files"][-1]["sha256"] == hashlib.sha256(local.read_bytes()).hexdigest()


def test_the_kit_is_packed_the_same_each_time(tmp_path):
    kit = make_kit(tmp_path / "kit")
    units = publish._units(kit, set())  # pylint: disable=protected-access
    assert units == [("background/noise", "background/noise"), ("negatives/speech", "negatives/speech"), ("kit.yaml", None)]
    assert publish._units(kit, {"background"})[0] == ("negatives/speech", "negatives/speech")  # pylint: disable=protected-access
    first, second = tmp_path / "a.tar.gz", tmp_path / "b.tar.gz"
    publish._pack(kit, "negatives/speech", first)  # pylint: disable=protected-access
    (kit / "negatives/speech/training/speech_mmap/data.ninja").touch()  # a new date: the same archive
    publish._pack(kit, "negatives/speech", second)  # pylint: disable=protected-access
    assert first.read_bytes() == second.read_bytes()


def test_a_kit_downloaded_and_removed(tmp_path, monkeypatch):
    asyncio.run(_kit_downloaded(tmp_path, monkeypatch))


async def _kit_downloaded(tmp_path: Path, monkeypatch) -> None:
    source = make_kit(tmp_path / "source")
    packed = tmp_path / "packed"
    served = {}
    for name, unpack in publish._units(source, set()):  # pylint: disable=protected-access
        if unpack:
            publish._pack(source, unpack, packed / f"{name}.tar.gz")  # pylint: disable=protected-access
            served[f"{name}.tar.gz"] = ((packed / f"{name}.tar.gz").read_bytes(), unpack)
        else:
            served[name] = ((source / name).read_bytes(), None)
    broken = {"negatives/speech.tar.gz"}
    runner, base = await serve({name: body for name, (body, _) in served.items()}, broken)
    files = tuple(File(name, f"{base}/{name}", hashlib.sha256(body).hexdigest(), len(body), unpack=unpack)
                  for name, (body, unpack) in served.items())
    monkeypatch.setattr(downloads, "kit", lambda: Model("wake-training", files))
    monkeypatch.setattr(downloads, "RETRY_SECONDS", 0.05)
    models, data = tmp_path / "models", tmp_path / "data"
    models.mkdir()
    (models / "wake-training").symlink_to(data / "models/wake-training")  # as the image links it
    setup = TrainingSetup(data, tmp_path / "venv", models, uv="")
    assert setup.can_install("kit") and not setup.installed
    try:
        setup.install(["kit"])
        assert setup.running and setup.status(["kit"])["installing"] == "kit"
        for _ in range(200):
            if setup.kit_download is not None and setup.kit_download.error:
                break
            await asyncio.sleep(0.02)
        # Not as published: said, tried again, and no kit meanwhile.
        status = setup.status(["kit"])
        assert "speech.tar.gz" in status["download_error"] and 0 < status["progress"] < 1
        assert not (data / "models/wake-training/kit.yaml").exists()
        broken.clear()
        await asyncio.wait_for(setup._task, 10)  # pylint: disable=protected-access
    finally:
        await runner.cleanup()
    assert setup.error is None and setup.installed and not downloads.kit_missing(models)
    kit = Kit.load(models / "wake-training")
    assert [n["name"] for n in kit.negatives] == ["speech"] and kit.background == models / "wake-training/background"
    assert (data / "models/wake-training/negatives/speech/training/speech_mmap/data.ninja").stat().st_size == 4000
    assert setup.disk_bytes and setup.disk_bytes >= 4000
    assert not [p for p in (data / "models/wake-training").rglob("*") if p.name.startswith(".") and p.name != downloads.KIT_MARKER]

    await setup.remove()
    assert list((data / "models/wake-training").iterdir()) == [] and not setup.installed

    # A kit made by hand is never removed.
    hand = make_kit(tmp_path / "hand")
    setup = TrainingSetup(data, tmp_path / "venv", tmp_path, uv="")
    (tmp_path / "wake-training").symlink_to(hand)
    await setup.remove()
    assert (hand / "kit.yaml").is_file()


@pytest.mark.skipif(find_uv() is None, reason="no uv")
def test_the_trainers_python_from_its_cache(tmp_path):
    asyncio.run(_trainer(tmp_path))


async def _trainer(tmp_path: Path) -> None:
    lock = tmp_path / "lock.txt"
    lock.write_text("# nothing pinned\n")
    data = tmp_path / "data"
    setup = TrainingSetup(data, tmp_path / "venv", tmp_path / "models", lock=lock)
    assert setup.can_install("trainer") and setup.python is None
    before = setup.generation
    setup.install(["trainer"])
    await asyncio.wait_for(setup._task, 60)  # pylint: disable=protected-access
    assert setup.error is None and setup.ready and setup.generation > before
    python = Path(setup.python)
    assert python.parent.parent == tmp_path / "venv" and python.exists()
    assert (data / "uv-cache" / SERIES).read_text().strip() == setup.series()
    assert "uv venv" in setup.log() and "--offline" not in setup.log()  # nothing cached to try

    # The next start: made again from the cache, offline.
    (tmp_path / "venv").rename(tmp_path / "old-venv")
    setup = TrainingSetup(data, tmp_path / "venv", tmp_path / "models", lock=lock)
    assert setup.installed and not setup.ready
    setup.restore()
    await asyncio.wait_for(setup._task, 60)  # pylint: disable=protected-access
    assert setup.ready and Path(setup.python).exists() and setup.error is None

    # New pins: the cache emptied first.
    (data / "uv-cache" / "stale").write_text("old wheels")
    lock.write_text("# nothing pinned, again\n")
    setup.restore()
    await asyncio.wait_for(setup._task, 60)  # pylint: disable=protected-access
    assert not (data / "uv-cache" / "stale").exists() and setup.ready
    assert (data / "uv-cache" / SERIES).read_text().strip() == setup.series()

    await setup.remove()
    assert not (tmp_path / "venv").exists() and not (data / "uv-cache").exists()
    assert setup.python is None and not setup.installed


def test_what_uv_said_when_it_fails(tmp_path):
    fake = tmp_path / "uv"
    fake.write_text("#!/bin/sh\necho 'Resolved 3 packages'\necho 'error: No solution found when resolving dependencies'\n"
                    "echo '  Because tensorflow has no wheels for this platform'\nexit 2\n")
    fake.chmod(0o755)
    lock = tmp_path / "lock.txt"
    lock.write_text("tensorflow==2.21.0\n")

    async def run() -> TrainingSetup:
        setup = TrainingSetup(tmp_path / "data", tmp_path / "venv", tmp_path / "models", lock=lock, uv=str(fake))
        setup.install(["trainer"])
        await asyncio.wait_for(setup._task, 10)  # pylint: disable=protected-access
        return setup

    setup = asyncio.run(run())
    assert setup.error == "No solution found when resolving dependencies" and not setup.ready
    assert setup.trainer_wanted  # tried again at the next start
    assert "Because tensorflow" in setup.log()


def test_what_installing_mends(tmp_path, monkeypatch):
    async def run() -> None:
        monkeypatch.setattr(downloads, "kit", lambda: Model("wake-training", (File("kit.yaml", "http://x/kit.yaml", "ab", 10),)))
        monkeypatch.setattr(wake_training_setup, "TRAINER_DOWNLOAD_MB", {"amd64": 640, "aarch64": 350})

        async def fetch_voice() -> None:
            return None

        setup = TrainingSetup(tmp_path / "data", tmp_path / "venv", tmp_path / "models", lock=Path(sys.executable), uv="uv")
        training = WakeTraining(tmp_path / "data/wake_training", tmp_path / "wake_words", [tmp_path / "nowhere"],
                                tmp_path / "voice.onnx", "en", fetch_voice=fetch_voice, setup=setup)
        lacks: list[str | None] = ["tensorflow,microwakeword"]

        async def trainer_missing() -> str | None:
            return lacks[0]

        training.trainer_missing = trainer_missing
        assert await training.blockers() == ("Training isn't installed.", ["trainer", "kit"])
        status = await training.status()
        assert status["setup"]["needs"] == ["trainer", "kit"] and status["setup"]["installing"] is None
        assert status["setup"]["download_mb"] in (640, 350) and status["unavailable"] == "Training isn't installed."

        # A Python given to train with is used as it is: nothing to install for it.
        training.trainer_python = sys.executable
        assert await training.blockers() == ("The trainer's Python lacks tensorflow, microwakeword.", [])
        training.trainer_python = None
        lacks[0] = None
        assert await training.blockers() == ("Training isn't installed.", ["kit"])
        monkeypatch.setattr(downloads, "kit", lambda: None)  # not published: put it there by hand
        why, needs = await training.blockers()
        assert why.startswith("No training kit") and needs == []
        with pytest.raises(TrainingError, match="No training kit"):
            await training.install()

        # The setup's Python, once installed, is the trainer's.
        assert training.trainer_python == sys.executable
        setup.ready = True
        assert training.trainer_python == str(tmp_path / "venv/bin/python")

    asyncio.run(run())
