"""Live volume-index battery for FANDOM (manga).

Manga-News lists French volumes one page at a time and stops at 40.
Fandom is the EN wiki fallback: one list parse, or Volume N articles.

Usage (MetaKavita on PYTHONPATH):
  set PYTHONPATH=Z:\\kavitafetcher
  python tests/run_fandom_volume_smoke.py

Jitter is left at 4–8 s unless FANDOM_SMOKE_FAST=1 (0.12 s, research only).
Writes tests/_fandom_volume_smoke.json (gitignored via tests/_*).
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
MK = Path(os.environ.get("METAKAVITA_ROOT", r"Z:\kavitafetcher"))
for path in (str(MK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

if os.environ.get("FANDOM_SMOKE_FAST") == "1":
    random.uniform = lambda a, b: 0.12  # noqa: E731

from fandom import (  # noqa: E402
    FandomRef,
    FandomScraper,
    pages_to_parse,
    series_name_to_slugs,
)

# Diversité de slugs / layouts, pas un palmarès. Les contrôles en tête.
SERIES: List[Tuple[str, str]] = [
    ("Death Note", "control compact wiki"),
    ("One Punch Man", "hyphenated title"),
    ("Attack on Titan", "EN title ≠ JP wiki sometimes"),
    ("Demon Slayer", "EN title, JP wiki kimetsu-no-yaiba"),
    ("Jujutsu Kaisen", "current shonen list page"),
    ("Chainsaw Man", "short title"),
    ("Spy x Family", "x in title"),
    ("Frieren", "colon subtitle often stripped"),
    ("Dandadan", "new series, small wiki"),
    ("Vinland Saga", "seinen"),
    ("My Hero Academia", "long EN title / boku no hero"),
    ("Tokyo Ghoul", "compact"),
    ("The Promised Neverland", "leading The"),
    ("Komi Can't Communicate", "apostrophe"),
    ("Kaguya-sama", "honorific + hyphen"),
    ("Oshi no Ko", "particle no"),
    ("Blue Lock", "two words"),
    ("Dorohedoro", "seinen niche"),
    ("Hellsing", "short seinen"),
    ("20th Century Boys", "leading number"),
    ("Delicious in Dungeon", "EN vs dungeon meshi"),
    ("The Apothecary Diaries", "leading The + long"),
    ("Made in Abyss", "in"),
    ("JoJo's Bizarre Adventure", "apostrophe + long"),
    ("Fullmetal Alchemist", "classic"),
    ("Hunter x Hunter", "x"),
    ("Goodnight Punpun", "literary seinen"),
    ("A Silent Voice", "leading A / koe no katachi"),
    ("7th Garden", "no list page regression"),
    ("A Couple of Cuckoos", "last-word slug + Volume Infobox"),
]

OUT_JSON = ROOT / "tests" / "_fandom_volume_smoke.json"
OUT_TXT = ROOT / "tests" / "_fandom_volume_smoke.txt"


def _stats(index: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not index:
        return {"n": 0, "title": 0, "summary": 0, "date": 0, "isbn": 0, "cover": 0}
    keys = list(index)
    return {
        "n": len(keys),
        "title": sum(1 for k in keys if index[k].get("title")),
        "summary": sum(1 for k in keys if index[k].get("summary")),
        "date": sum(1 for k in keys if index[k].get("release_date")),
        "isbn": sum(1 for k in keys if index[k].get("isbn")),
        "cover": sum(1 for k in keys if index[k].get("cover_url")),
    }


def _sample(index: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not index:
        return []
    keys = sorted(index, key=lambda k: float(k) if k.replace(".", "", 1).isdigit() else 0)
    out = []
    for key in keys[:2]:
        payload = index[key]
        out.append(
            {
                "n": key,
                "title": payload.get("title") or "",
                "date": payload.get("release_date") or "",
                "isbn": payload.get("isbn") or "",
                "summary": (payload.get("summary") or "")[:180],
            }
        )
    return out


def _diagnose(scraper: FandomScraper, session, query: str) -> Dict[str, Any]:
    """Pourquoi l'index est vide / maigre — une passe API, pas un second index."""
    info: Dict[str, Any] = {"slugs": series_name_to_slugs(query), "wikis": []}
    for i, slug in enumerate(info["slugs"][:5]):
        ref = FandomRef(wiki=slug)
        general = scraper._siteinfo(session, ref)
        row: Dict[str, Any] = {
            "slug": slug,
            "exists": bool(general),
            "sitename": (general or {}).get("sitename") or "",
        }
        if general:
            existing = scraper._existing_titles(session, ref, pages_to_parse(ref))
            titles = scraper._volume_page_titles(session, ref)
            row["list_pages"] = existing
            row["volume_pages"] = len(titles)
            row["volume_sample"] = titles[:6]
        info["wikis"].append(row)
        if i >= 1 and not general:
            continue
    return info


def main() -> int:
    scraper = FandomScraper()
    rows: List[Dict[str, Any]] = []
    lines = [
        f"FANDOM volume smoke  version={scraper.version}  fast={os.environ.get('FANDOM_SMOKE_FAST')}",
        "",
    ]
    for name, note in SERIES:
        started = time.monotonic()
        try:
            index = scraper.fetch_volume_index(name, library_type="Manga")
            error = ""
        except Exception as exc:
            index = None
            error = f"{type(exc).__name__}: {exc}"
        elapsed = round(time.monotonic() - started, 2)
        stats = _stats(index)
        weak = stats["n"] == 0 or (stats["n"] < 3 and name not in {"Look Back", "Goodbye Eri"})
        row: Dict[str, Any] = {
            "query": name,
            "note": note,
            "seconds": elapsed,
            "error": error,
            **stats,
            "sample": _sample(index),
        }
        if weak:
            session = scraper._session()
            try:
                row["diagnose"] = _diagnose(scraper, session, name)
            except Exception as exc:
                row["diagnose"] = {"error": f"{type(exc).__name__}: {exc}"}
            finally:
                session.close()
        rows.append(row)
        flag = "EMPTY" if stats["n"] == 0 else ("WEAK" if weak else "OK")
        lines.append(
            f"{flag:5} {name:28} n={stats['n']:3} "
            f"sum={stats['summary']:3} date={stats['date']:3} "
            f"isbn={stats['isbn']:3} cover={stats['cover']:3}  {elapsed}s  {note}"
        )
        if error:
            lines.append(f"      ERROR {error}")
        if row.get("diagnose"):
            lines.append(f"      diag {json.dumps(row['diagnose'], ensure_ascii=False)[:400]}")
        if row["sample"]:
            first = row["sample"][0]
            lines.append(
                f"      #1 {first['title']!r} {first['date']} {first['isbn']} "
                f"{first['summary'][:120]}"
            )

    empty = sum(1 for r in rows if r["n"] == 0)
    ok = sum(1 for r in rows if r["n"] >= 3)
    payload = {
        "version": scraper.version,
        "empty": empty,
        "ok": ok,
        "total": len(rows),
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    lines.append("")
    lines.append(f"ok(>=3)={ok}/{len(rows)} empty={empty} → {OUT_JSON.name}")
    OUT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        print("\n".join(lines))
    except UnicodeEncodeError:
        print(OUT_TXT.read_text(encoding="utf-8").encode("ascii", "replace").decode("ascii"))
    return 1 if empty > len(rows) // 2 else 0


if __name__ == "__main__":
    raise SystemExit(main())
