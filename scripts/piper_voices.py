#!/usr/bin/env python3
"""Write voice_incubator/piper_voices.json: the voices rhasspy/piper-voices has
for the app's languages (every pack's ``piper_languages``), at one revision of
it -- each one's name, language, quality, speakers (in the order of their ids)
and files with their sizes and MD5 digests, which voice_incubator/piper_voices.py
downloads and checks -- and what each language is called, in English.

    python3 scripts/piper_voices.py [--revision <commit>] [--language en_US ...]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "voice_incubator/piper_voices.json"
REPO = "https://huggingface.co/rhasspy/piper-voices"
REGIONS = {"en_US": "US English", "en_GB": "British English"}
"""What a language is called where Piper's "English (United States)" isn't."""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--revision", help="a commit of rhasspy/piper-voices (default: main's latest)")
    parser.add_argument("--language", action="append", help="a language code to keep, as en_US (default: every pack's)")
    args = parser.parse_args()
    revision = args.revision
    if revision is None:
        with urllib.request.urlopen(f"https://huggingface.co/api/models/rhasspy/piper-voices") as response:
            revision = json.load(response)["sha"]
    from voice_incubator import languages  # pylint: disable=import-outside-toplevel

    keep = set(args.language or (code for pack in map(languages.load, languages.codes()) for code in pack.piper_languages))
    with urllib.request.urlopen(f"{REPO}/resolve/{revision}/voices.json") as response:
        catalog = json.load(response)
    voices = {}
    regions = {}
    for key, voice in sorted(catalog.items()):
        if voice["language"]["code"] not in keep:
            continue
        language = voice["language"]
        regions[language["code"]] = REGIONS.get(
            language["code"], f"{language['name_english']} ({language['country_english']})")
        speakers = sorted(voice.get("speaker_id_map") or {}, key=lambda name: voice["speaker_id_map"][name])
        voices[key] = {
            "name": voice["name"],
            "language": voice["language"]["code"],
            "quality": voice["quality"],
            "speakers": speakers,
            "files": {path: [f["size_bytes"], f["md5_digest"]] for path, f in voice["files"].items()},
        }
    OUT.write_text(json.dumps({"revision": revision, "regions": dict(sorted(regions.items())), "voices": voices}, indent=1) + "\n",
                   encoding="utf-8")
    print(f"{OUT}: {len(voices)} voices at {revision}")


if __name__ == "__main__":
    main()
