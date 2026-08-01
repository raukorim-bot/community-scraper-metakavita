"""Dump live ANN — usage: PYTHONPATH=<metakavita> python debug_dump_ann.py [query|--id N]."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ann import AnnScraper  # noqa: E402


def main() -> int:
    args = sys.argv[1:]
    is_id = False
    query = "Death Note"
    if args and args[0] == "--id":
        is_id = True
        query = args[1] if len(args) > 1 else "4354"
    elif args:
        query = " ".join(args)

    s = AnnScraper()
    meta = s.fetch(query, library_type="Manga", is_id=is_id)
    print("META:")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    covers = s.fetch_covers(query if not is_id else (meta or {}).get("title") or query)
    print("COVERS:", len(covers))
    for c in covers[:5]:
        print(" ", c)
    return 0 if meta else 1


if __name__ == "__main__":
    raise SystemExit(main())
