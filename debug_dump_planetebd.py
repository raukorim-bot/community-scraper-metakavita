"""Dump live Planète BD — PYTHONPATH=<metakavita;community> python debug_dump_planetebd.py [query]."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from planetebd import PlanetebdScraper  # noqa: E402


def main() -> int:
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Astérix"
    s = PlanetebdScraper()
    meta = s.fetch(query, library_type="Comic")
    print("META:")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    covers = s.fetch_covers(query, library_type="Comic")
    print("COVERS:", len(covers))
    for c in covers[:5]:
        print(" ", c)
    return 0 if meta else 1


if __name__ == "__main__":
    raise SystemExit(main())
