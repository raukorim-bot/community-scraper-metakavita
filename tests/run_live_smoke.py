"""Smoke tests — tous les scrapers community (contrat + fetch live).

Usage (depuis le clone community, avec MetaKavita sur PYTHONPATH) :
  set PYTHONPATH=Z:\\kavitafetcher
  python tests/run_live_smoke.py

Quitte avec code 1 s'il y a des FAIL (SKIP / EXPECTED ne comptent pas).
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
MK = Path(os.environ.get("METAKAVITA_ROOT", r"Z:\kavitafetcher"))
if str(MK) not in sys.path:
    sys.path.insert(0, str(MK))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Scrapers community (hors debug_*)
SKIP_FILES = {"debug_dump_ann.py", "debug_dump_planetebd.py"}

# Requêtes live par type de bibliothèque
QUERIES: Dict[str, List[Tuple[str, str]]] = {
    "Book": [("Le Petit Prince", "Book"), ("1984", "Book")],
    "Comic": [("Watchmen", "Comic"), ("Tintin", "Comic")],
    "Manga": [("Death Note", "Manga"), ("One Piece", "Manga")],
}

# Providers qui nécessitent une clé / cookies — skip live si absente
KEY_ENV = {
    "METRON": "METRON_API_KEY",
    "LOCG": "LOCG_API_KEY",
    "ISBNDB": "ISBNDB_API_KEY",
    "NOVELUPDATES": "NOVELUPDATES_API_KEY",  # cookies CF optionnels
    "GCD": "GCD_API_KEY",  # optionnel mais utile si 429
}

REQUIRED_CAND_KEYS = {"title", "genres", "tags", "staff", "format", "alternative_titles"}


def _load_config_safe() -> dict:
    try:
        from config_manager import load_config

        return load_config() or {}
    except Exception:
        return {}


def _has_key(scraper_id: str) -> bool:
    env_name = KEY_ENV.get(scraper_id)
    if not env_name:
        return True
    cfg = _load_config_safe()
    val = (cfg.get(env_name) or os.environ.get(env_name) or "").strip()
    if scraper_id == "NOVELUPDATES":
        # cookies optionnels : on tente quand même le live
        return True
    if scraper_id == "GCD":
        return True  # API anon OK sauf 429
    return bool(val)


def _discover_modules() -> List[Path]:
    files = sorted(ROOT.glob("*.py"))
    out = []
    for f in files:
        if f.name.startswith("_") or f.name in SKIP_FILES:
            continue
        if f.name == "conftest.py":
            continue
        out.append(f)
    return out


def _load_scraper_classes(path: Path) -> List[type]:
    from scrapers.base import BaseScraper

    name = f"community_smoke_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"spec_from_file_location failed for {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    classes = []
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        if obj.__module__ != mod.__name__:
            continue
        if issubclass(obj, BaseScraper) and obj is not BaseScraper:
            classes.append(obj)
    return classes


def _validate_contract(cls: type, inst: Any) -> List[str]:
    errs = []
    if not getattr(inst, "id", None):
        errs.append("id vide")
    elif not str(inst.id).isupper() or " " in str(inst.id):
        errs.append(f"id suspect: {inst.id!r} (attendu MAJUSCULES sans espace)")
    if not getattr(inst, "display_name", None):
        errs.append("display_name vide")
    types = getattr(inst, "supported_types", None) or set()
    if not types:
        errs.append("supported_types vide")
    bad = set(types) - {"Manga", "Comic", "Book"}
    if bad:
        errs.append(f"supported_types invalides: {bad}")
    if not isinstance(getattr(inst, "rate_limit", None), (int, float)):
        errs.append("rate_limit manquant")
    if not getattr(inst, "proxy_domains", None):
        errs.append("proxy_domains vide")
    if not callable(getattr(inst, "fetch", None)):
        errs.append("fetch manquant")
    if not callable(getattr(inst, "fetch_covers", None)):
        errs.append("fetch_covers manquant")
    if not getattr(inst, "uses_unified_scoring", False):
        errs.append("uses_unified_scoring=False (info)")
    return errs


def _validate_candidate(meta: dict, scraper_id: str) -> List[str]:
    errs = []
    if not isinstance(meta, dict):
        return ["candidat non-dict"]
    for k in REQUIRED_CAND_KEYS:
        if k not in meta:
            errs.append(f"clé manquante: {k}")
    title = meta.get("title")
    if not title or not isinstance(title, str):
        errs.append("title invalide")
    genres = meta.get("genres")
    if not isinstance(genres, list) or not genres:
        errs.append("genres doit être une liste non vide")
    tags = meta.get("tags")
    if not isinstance(tags, list):
        errs.append("tags doit être une liste")
    staff = meta.get("staff")
    if not isinstance(staff, list):
        errs.append("staff doit être une liste")
    else:
        for i, s in enumerate(staff[:5]):
            if not isinstance(s, dict):
                errs.append(f"staff[{i}] non-dict")
                continue
            try:
                _ = s["node"]["name"]["full"]
            except Exception:
                errs.append(f"staff[{i}] forme incorrecte (role/node.name.full)")
    fmt = meta.get("format")
    if fmt not in {"manga", "webtoon", "comic", "book", None}:
        errs.append(f"format inattendu: {fmt!r}")
    score = meta.get("_match_score")
    if score is not None:
        try:
            fs = float(score)
            if not (0.0 <= fs <= 1.0):
                errs.append(f"_match_score hors [0,1]: {score}")
        except Exception:
            errs.append(f"_match_score non numérique: {score!r}")
    status = meta.get("status")
    if status is not None and status not in {
        "RELEASING",
        "FINISHED",
        "HIATUS",
        "CANCELLED",
    }:
        errs.append(f"status invalide: {status!r}")
    age = meta.get("age_rating")
    if age is not None and age not in {
        "safe",
        "suggestive",
        "erotica",
        "pornographic",
    }:
        errs.append(f"age_rating invalide: {age!r}")
    year = meta.get("year")
    if year is not None and not isinstance(year, int):
        errs.append(f"year non-int: {year!r}")
    return errs


def _pick_queries(inst: Any) -> List[Tuple[str, str]]:
    types = set(inst.supported_types or [])
    out: List[Tuple[str, str]] = []
    for t in ("Book", "Comic", "Manga"):
        if t in types:
            out.extend(QUERIES[t][:1])  # 1 query par type supporté
    # webtoon-ish : ajouter Solo Leveling pour WEBTOON/TAPAS
    if inst.id == "TAPAS":
        out = [("Solo Leveling", "Manga")]
    if inst.id == "WEBTOON":
        # Solo Leveling n'est plus sur WEBTOON (Line) — Tower of God oui
        out = [("Tower of God", "Manga")]
    if inst.id == "GCD":
        out = [("Watchmen", "Comic")]  # + year via existing_metadata
    if inst.id == "ANN":
        out = [("Death Note", "Manga")]
    if inst.id == "BNF":
        out = [("Les Misérables", "Book")]
    if inst.id == "DNB":
        out = [("Der Prozess", "Book")]
    if inst.id == "BANGUMI":
        out = [("Death Note", "Manga")]
    if inst.id == "PLANETEBD":
        out = [("Astérix", "Comic")]
    if inst.id == "BDGEST":
        out = [("Astérix", "Comic")]
    if inst.id == "SENSCRITIQUE":
        out = [("Tintin", "Comic")]
    if inst.id == "DECITRE":
        out = [("Le Petit Prince", "Book")]
    if inst.id == "BABELIO":
        out = [("Le Petit Prince", "Book")]
    if inst.id == "ANIMEPLANET":
        out = [("Death Note", "Manga")]
    if inst.id == "MANGASANCTUARY":
        out = [("Death Note", "Manga")]
    return out or [("Watchmen", "Comic")]


def run() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print(f"ROOT={ROOT}")
    print(f"METAKAVITA={MK}")
    cfg = _load_config_safe()
    print(
        "keys:",
        {
            k: ("yes" if (cfg.get(k) or os.environ.get(k)) else "no")
            for k in (
                "METRON_API_KEY",
                "LOCG_API_KEY",
                "ISBNDB_API_KEY",
                "NOVELUPDATES_API_KEY",
                "GCD_API_KEY",
            )
        },
    )

    results: List[dict] = []
    modules = _discover_modules()
    print(f"\n=== CONTRACT + LIVE ({len(modules)} fichiers) ===\n")

    for path in modules:
        row: Dict[str, Any] = {
            "file": path.name,
            "id": None,
            "contract": "?",
            "live": "?",
            "detail": "",
        }
        try:
            classes = _load_scraper_classes(path)
            if not classes:
                row["contract"] = "FAIL"
                row["detail"] = "aucune classe BaseScraper"
                results.append(row)
                print(f"[FAIL] {path.name}: aucune classe BaseScraper")
                continue
            if len(classes) > 1:
                row["detail"] = f"{len(classes)} classes (on teste toutes)"

            for cls in classes:
                inst = cls()
                row = {
                    "file": path.name,
                    "id": inst.id,
                    "contract": "?",
                    "live": "?",
                    "detail": "",
                }
                cerrs = _validate_contract(cls, inst)
                # uses_unified_scoring=False = warning only
                hard = [e for e in cerrs if not e.startswith("uses_unified")]
                soft = [e for e in cerrs if e.startswith("uses_unified")]
                if hard:
                    row["contract"] = "FAIL"
                    row["detail"] = "; ".join(hard)
                    results.append(row)
                    print(f"[FAIL] {inst.id} contract: {row['detail']}")
                    continue
                row["contract"] = "PASS" + (f" (warn: {soft[0]})" if soft else "")

                # LIVE
                if getattr(inst, "needs_api_key", False) and not _has_key(inst.id):
                    key = KEY_ENV.get(inst.id, f"{inst.id}_API_KEY")
                    row["live"] = "SKIP"
                    row["detail"] = f"clé manquante ({key})"
                    results.append(row)
                    print(f"[SKIP] {inst.id} live: {row['detail']}")
                    continue

                queries = _pick_queries(inst)
                live_ok = False
                live_notes = []
                for q, lib in queries:
                    existing = None
                    if inst.id == "GCD" and q == "Watchmen":
                        existing = {"year": 1986}
                    try:
                        meta = inst.fetch(
                            q, library_type=lib, is_id=False, existing_metadata=existing
                        )
                    except Exception as e:
                        live_notes.append(f"EXC {q}: {e}")
                        traceback.print_exc()
                        continue

                    if meta is None:
                        # distinguer CF / rate / no match via logs difficiles → note générique
                        live_notes.append(f"None pour '{q}'")
                        continue

                    verrs = _validate_candidate(meta, inst.id)
                    if verrs:
                        live_notes.append(
                            f"shape '{q}' ({meta.get('title')}): {'; '.join(verrs)}"
                        )
                        continue

                    score = meta.get("_match_score")
                    cover = "cover" if meta.get("cover_url") else "no-cover"
                    live_notes.append(
                        f"OK '{q}'→'{meta.get('title')}' "
                        f"score={score} {cover} year={meta.get('year')}"
                    )
                    live_ok = True
                    break  # un succès suffit

                if live_ok:
                    row["live"] = "PASS"
                    row["detail"] = " | ".join(live_notes)
                    print(f"[PASS] {inst.id}: {row['detail']}")
                else:
                    # Novel Updates sans cookies → EXPECTED
                    if inst.id == "NOVELUPDATES" and not (
                        cfg.get("NOVELUPDATES_API_KEY")
                        or os.environ.get("NOVELUPDATES_API_KEY")
                    ):
                        row["live"] = "EXPECTED"
                        row["detail"] = "CF sans cookies — " + " | ".join(live_notes)
                        print(f"[EXPECTED] {inst.id}: {row['detail']}")
                    elif any("429" in n or "rate" in n.lower() for n in live_notes):
                        row["live"] = "EXPECTED"
                        row["detail"] = " | ".join(live_notes)
                        print(f"[EXPECTED] {inst.id}: {row['detail']}")
                    else:
                        row["live"] = "FAIL"
                        row["detail"] = " | ".join(live_notes) or "aucun résultat"
                        print(f"[FAIL] {inst.id} live: {row['detail']}")
                results.append(row)
        except Exception as e:
            row["contract"] = "FAIL"
            row["detail"] = f"import/load: {e}"
            results.append(row)
            print(f"[FAIL] {path.name}: {e}")
            traceback.print_exc()

    # Summary
    print("\n=== SUMMARY ===")
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0, "EXPECTED": 0}
    for r in results:
        status = r["live"] if r["contract"].startswith("PASS") else "FAIL"
        if r["contract"] == "FAIL":
            status = "FAIL"
        elif r["live"] in counts:
            status = r["live"]
        counts[status] = counts.get(status, 0) + 1
        print(
            f"{r.get('id') or r['file']:18} contract={r['contract']:18} live={r['live']:10} {r['detail'][:100]}"
        )

    print(
        f"\nPASS={counts.get('PASS',0)} FAIL={counts.get('FAIL',0)} "
        f"SKIP={counts.get('SKIP',0)} EXPECTED={counts.get('EXPECTED',0)}"
    )

    out_path = ROOT / "tests" / "_smoke_report.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report → {out_path}")

    return 1 if counts.get("FAIL", 0) else 0


if __name__ == "__main__":
    raise SystemExit(run())
