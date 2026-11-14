"""Pack the wake word training kit (scripts/make_wake_training_kit.py) for
the app to download when the Wake words page installs training
(voice_incubator/downloads.py, ``kit``).

Each negative set and each folder of background recordings becomes an
archive of its own (gzip: the features shrink to a quarter), so a download
that stops loses one of them at most, and unpacking needs little more room
than the kit; kit.yaml and the backbone stay as they are, kit.yaml last. The
archives are the same bytes each time they are made from the same kit (no
dates, owners or modes of the machine that made them), and the manifest
(voice_incubator/wake_training_kit.json) lists each with its SHA-256::

    python scripts/publish_wake_training_kit.py models/wake-training /tmp/kit
    hf upload rhasspy/voice-incubator-models /tmp/kit wake-training
    python scripts/publish_wake_training_kit.py models/wake-training /tmp/kit --revision <that commit>

Until the manifest has a revision the app doesn't offer the kit.
``--without background`` leaves a part out (the positives then get
synthetic noise behind them, as a kit without background recordings does).
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import tarfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "voice_incubator/wake_training_kit.json"
REPO = "rhasspy/voice-incubator-models"
PATH = "wake-training"
SPLIT = ("negatives", "background")
"""Folders packed one archive per folder in them."""


def _units(kit: Path, without: set[str]) -> list[tuple[str, str | None]]:
    """What is published: (its path in the kit, what it unpacks to or None
    for a file as it is), kit.yaml last."""
    units: list[tuple[str, str | None]] = []
    for entry in sorted(kit.iterdir()):
        if entry.name in without or entry.name.startswith(".") or entry.name == "kit.yaml":
            continue
        if entry.is_file():
            units.append((entry.name, None))
        elif entry.name in SPLIT:
            units.extend((f"{entry.name}/{sub.name}", f"{entry.name}/{sub.name}")
                         for sub in sorted(entry.iterdir()) if sub.is_dir())
        elif entry.is_dir():
            units.append((entry.name, entry.name))
    units.append(("kit.yaml", None))
    return units


def _pack(kit: Path, unpack: str, out: Path) -> None:
    """``kit/unpack`` as a .tar.gz at ``out``, the same bytes every time."""
    out.parent.mkdir(parents=True, exist_ok=True)
    source = kit / unpack
    paths = [source, *sorted(source.rglob("*"))]
    with out.open("wb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0, compresslevel=6) as gz, \
            tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tar:
        for path in paths:
            info = tar.gettarinfo(str(path), arcname=str(path.relative_to(kit)))
            info.mtime, info.uid, info.gid, info.uname, info.gname = 0, 0, 0, "", ""
            info.mode = 0o755 if info.isdir() else 0o644
            if info.isfile():
                with path.open("rb") as data:
                    tar.addfile(info, data)
            elif info.isdir():
                tar.addfile(info)


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as data:
        while chunk := data.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _unpacked(path: Path) -> int:
    return path.stat().st_size if path.is_file() else sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("kit", type=Path, help="the kit (models/wake-training)")
    parser.add_argument("out", type=Path, help="where the files to upload go")
    parser.add_argument("--revision", help="the commit of the repository they were uploaded in")
    parser.add_argument("--without", action="append", default=[], metavar="NAME", help="leave out a part of the kit (repeatable)")
    args = parser.parse_args()
    if not (args.kit / "kit.yaml").is_file():
        raise SystemExit(f"No kit.yaml in {args.kit}")
    units = _units(args.kit, set(args.without))
    archives = [(unpack, args.out / f"{name}.tar.gz") for name, unpack in units if unpack]
    with ProcessPoolExecutor() as pool:
        for future in [pool.submit(_pack, args.kit, unpack, out) for unpack, out in archives]:
            future.result()
    files = []
    for name, unpack in units:
        published = args.out / (f"{name}.tar.gz" if unpack else name)
        if not unpack:
            published.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(args.kit / name, published)
        entry = {"name": str(published.relative_to(args.out)), "sha256": _digest(published), "size": published.stat().st_size}
        if unpack:
            entry["unpack"] = unpack
        files.append(entry)
        print(f"{entry['name']}: {entry['size'] / 1e6:.1f} MB")
    unpacked = sum(_unpacked(args.kit / name) for name, _ in units)
    MANIFEST.write_text(json.dumps({
        "repo": REPO, "path": PATH, "revision": args.revision, "unpacked": unpacked, "files": files,
    }, indent=1) + "\n", "utf-8")
    print(f"{sum(f['size'] for f in files) / 1e6:.0f} MB to download, {unpacked / 1e6:.0f} MB unpacked: {MANIFEST}")


if __name__ == "__main__":
    main()
