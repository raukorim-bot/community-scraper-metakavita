#!/usr/bin/env python3
"""Audit qualité + complétude payload des scrapers communautaires.

Pour chaque scraper (1er cas positif) :
- note /100 (match + champs utiles)
- champs présents / absents
- classification absences : PROVIDER_LIMIT | LIKELY_BUG | N/A

Usage:
  set PYTHONPATH=Z:\\kavitafetcher
  set METRON_API_KEY=...
  python tests/run_payload_audit.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Reuse quality harness pieces
from tests.run_quality import (  # noqa: E402
    FILE_BY_ID,
    KEY_ENV,
    SUITES,
    Case,
    Suite,
    _has_key,
    _load_scraper,
    title_ok,
)

# Champs « métier » attendus dans un candidat MetaKavita
CORE_FIELDS = (
    "title",
    "summary",
    "cover_url",
    "year",
    "staff",
    "genres",
    "tags",
    "format",
    "url",
    "alternative_titles",
    "isbn",
    "publisher",
    "status",
)

# Ce que le catalogue store déclare comme capacité
META_PATH = ROOT / "store" / "meta.json"


def _load_meta() -> dict:
    if META_PATH.exists():
        return json.loads(META_PATH.read_text(encoding="utf-8"))
    return {}


def _truthy_list(val: Any) -> bool:
    return isinstance(val, list) and len(val) > 0


def _truthy_str(val: Any) -> bool:
    return isinstance(val, str) and bool(val.strip())


def field_present(meta: dict, key: str) -> bool:
    if key not in meta:
        return False
    val = meta.get(key)
    if key in {"staff", "genres", "tags", "alternative_titles", "links"}:
        return _truthy_list(val)
    if key in {"year"}:
        return isinstance(val, int) and val > 0
    if key in {"title", "summary", "cover_url", "url", "format", "isbn", "publisher", "status"}:
        return _truthy_str(val) if key != "year" else False
    return val is not None and val != "" and val != []


def classify_missing(
    key: str,
    sid: str,
    store_meta: dict,
    method: str,
) -> str:
    """PROVIDER_LIMIT | LIKELY_BUG | OPTIONAL."""
    covers_declared = store_meta.get("covers")
    # Catalogues nationaux SRU : souvent sans cover / summary pauvre
    sru_no_cover = method == "sru" or sid in {"BNF", "DNB", "BNE", "KB", "NDL", "SBN"}
    isbn_only = sid == "OPENBD"

    if key == "cover_url":
        if covers_declared is False or sru_no_cover or sid == "LOC":
            return "PROVIDER_LIMIT"
        if covers_declared is True:
            return "LIKELY_BUG"
        return "OPTIONAL"

    if key == "summary":
        if sru_no_cover or sid in {"OPENBD", "GCD", "LOC", "TAPAS"}:
            # SRU/OpenBD : notice courte ; Tapas : pitch marketing HTML, synopsis API auth
            return "PROVIDER_LIMIT"
        return "LIKELY_BUG" if method in {"html", "graphql", "api"} else "OPTIONAL"

    if key == "isbn":
        if sid in {"WEBTOON", "TAPAS", "ANN", "ANIMEPLANET", "BANGUMI", "LOCG", "METRON", "GCD", "BDGEST", "PLANETEBD", "SENSCRITIQUE", "MANGASANCTUARY"}:
            return "OPTIONAL"  # comics/manga : ISBN rare
        if isbn_only:
            return "LIKELY_BUG"  # openBD est ISBN-centric
        return "OPTIONAL"

    if key == "publisher":
        return "OPTIONAL"

    if key == "status":
        return "OPTIONAL"  # beaucoup de providers ne l'exposent pas

    if key == "tags":
        return "OPTIONAL"

    if key == "alternative_titles":
        return "OPTIONAL"

    if key == "year":
        if sid in {"WEBTOON", "TAPAS"}:
            return "PROVIDER_LIMIT"
        return "LIKELY_BUG"

    if key == "staff":
        if sru_no_cover:
            return "PROVIDER_LIMIT"  # parfois creators absents en DC
        return "LIKELY_BUG"

    if key in {"title", "format", "genres"}:
        return "LIKELY_BUG"

    if key == "url":
        if sid == "LOC":
            # DC SRU : identifier/LCCN souvent absent
            return "PROVIDER_LIMIT"
        return "LIKELY_BUG"

    return "OPTIONAL"


def score_payload(meta: Optional[dict], case: Case, store_meta: dict, method: str, sid: str) -> Tuple[int, dict]:
    """Retourne (note 0-100, détail)."""
    detail: Dict[str, Any] = {
        "fields": {},
        "missing_provider": [],
        "missing_bug": [],
        "missing_optional": [],
        "match_ok": False,
        "score": None,
    }
    if not meta:
        return 0, detail

    title = meta.get("title") or ""
    match_ok = True
    if case.expect_title and case.expect_title != "*":
        match_ok = title_ok(title, case.expect_title, case.title_mode)
    elif case.expect_title == "*":
        match_ok = bool(str(title).strip())
    detail["match_ok"] = match_ok
    detail["score"] = meta.get("_match_score")
    detail["title"] = title

    present = 0
    weighed = 0.0
    weights = {
        "title": 20,
        "cover_url": 15,
        "summary": 12,
        "year": 12,
        "staff": 12,
        "genres": 8,
        "url": 8,
        "format": 5,
        "isbn": 4,
        "publisher": 2,
        "tags": 1,
        "alternative_titles": 1,
        "status": 0,
    }
    for key, w in weights.items():
        ok = field_present(meta, key)
        detail["fields"][key] = ok
        if ok:
            present += 1
            weighed += w
        else:
            kind = classify_missing(key, sid, store_meta, method)
            if kind == "PROVIDER_LIMIT":
                detail["missing_provider"].append(key)
                weighed += w * 0.85  # ne pas pénaliser fort
            elif kind == "LIKELY_BUG":
                detail["missing_bug"].append(key)
            else:
                detail["missing_optional"].append(key)
                weighed += w * 0.95

    # Match = 40% de la note, payload = 60%
    match_part = 40.0 if match_ok else 0.0
    payload_part = min(60.0, weighed * 0.6)
    # weighed max théorique ~100 → *0.6 = 60
    note = int(round(match_part + payload_part))
    # pénalité bugs
    note -= 8 * len(detail["missing_bug"])
    note = max(0, min(100, note))
    detail["present_count"] = present
    return note, detail


def primary_case(suite: Suite) -> Optional[Case]:
    for c in suite.cases:
        if c.expect_title is not None:
            return c
    return None


def grade(note: int) -> str:
    if note >= 90:
        return "A"
    if note >= 80:
        return "B"
    if note >= 70:
        return "C"
    if note >= 55:
        return "D"
    return "E"


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    meta_all = _load_meta()
    rows = []
    print("Payload audit — community scrapers\n")

    for suite in SUITES:
        sid = suite.scraper_id
        store = meta_all.get(sid) or {}
        method = store.get("method") or "?"

        if suite.skip_reason and not suite.cases:
            rows.append(
                {
                    "id": sid,
                    "status": "SKIP",
                    "note": None,
                    "grade": "-",
                    "detail": suite.skip_reason,
                    "method": method,
                }
            )
            print(f"{sid:16} SKIP  — {suite.skip_reason}")
            continue

        if sid in KEY_ENV and not _has_key(sid):
            rows.append(
                {
                    "id": sid,
                    "status": "SKIP",
                    "note": None,
                    "grade": "-",
                    "detail": f"clé {KEY_ENV[sid]} manquante",
                    "method": method,
                }
            )
            print(f"{sid:16} SKIP  — clé manquante")
            continue

        case = primary_case(suite)
        if not case:
            rows.append(
                {
                    "id": sid,
                    "status": "SKIP",
                    "note": None,
                    "grade": "-",
                    "detail": "pas de cas positif",
                    "method": method,
                }
            )
            continue

        try:
            scraper = _load_scraper(sid)
        except Exception as e:
            rows.append(
                {
                    "id": sid,
                    "status": "FAIL",
                    "note": 0,
                    "grade": "E",
                    "detail": f"load: {e}",
                    "method": method,
                }
            )
            print(f"{sid:16} FAIL  load {e}")
            continue

        t0 = time.time()
        try:
            result = scraper.fetch(
                case.query,
                library_type=case.library_type,
                is_id=case.is_id,
                existing_metadata=case.existing,
            )
        except Exception as e:
            rows.append(
                {
                    "id": sid,
                    "status": "FAIL",
                    "note": 0,
                    "grade": "E",
                    "detail": f"EXC {e}",
                    "method": method,
                }
            )
            print(f"{sid:16} FAIL  EXC {e}")
            continue
        elapsed = round(time.time() - t0, 2)

        # Novel Updates CF → EXPECTED
        if sid == "NOVELUPDATES" and result is None:
            rows.append(
                {
                    "id": sid,
                    "status": "EXPECTED",
                    "note": None,
                    "grade": "-",
                    "detail": "CF probable",
                    "method": method,
                    "elapsed": elapsed,
                }
            )
            print(f"{sid:16} EXPECTED — CF")
            continue

        note, detail = score_payload(result, case, store, method, sid)
        status = "PASS" if detail["match_ok"] and note >= 55 else "FAIL"
        if sid == "GCD" and result is None:
            status = "EXPECTED"
            detail["title"] = None

        row = {
            "id": sid,
            "status": status,
            "note": note,
            "grade": grade(note) if status == "PASS" else ("-" if status != "FAIL" else "E"),
            "query": case.query,
            "title": detail.get("title"),
            "match_score": detail.get("score"),
            "fields": detail.get("fields"),
            "missing_provider": detail.get("missing_provider"),
            "missing_bug": detail.get("missing_bug"),
            "missing_optional": detail.get("missing_optional"),
            "method": method,
            "covers_declared": store.get("covers"),
            "elapsed": elapsed,
        }
        rows.append(row)

        bugs = ",".join(detail.get("missing_bug") or []) or "-"
        prov = ",".join(detail.get("missing_provider") or []) or "-"
        print(
            f"{sid:16} {status:8} {grade(note) if status=='PASS' else '-':2} "
            f"{note if note is not None else '-':>3}  "
            f"title={(detail.get('title') or '')[:40]!r:42}  "
            f"bug=[{bugs}]  provider=[{prov}]  {elapsed}s"
        )

    # Summary table
    print("\n=== NOTES ===")
    print(f"{'ID':16} {'St':8} {'G':2} {'Note':>4}  Bugs (LIKELY)              Provider limits")
    print("-" * 100)
    for r in rows:
        if r["status"] in {"SKIP", "EXPECTED"}:
            print(f"{r['id']:16} {r['status']:8} {'-':2} {'—':>4}  {r.get('detail','')}")
            continue
        bugs = ",".join(r.get("missing_bug") or []) or "—"
        prov = ",".join(r.get("missing_provider") or []) or "—"
        print(
            f"{r['id']:16} {r['status']:8} {r.get('grade','-'):2} {r.get('note') or 0:4d}  "
            f"{bugs:26}  {prov}"
        )

    out_path = ROOT / "tests" / "_payload_audit.json"
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nreport → {out_path}")

    fails = sum(1 for r in rows if r["status"] == "FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
