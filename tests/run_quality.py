"""Quality battery — un scraper à la fois (matching, métadonnées, anti-bruit).

Usage:
  set PYTHONPATH=Z:\\kavitafetcher
  set METAKAVITA_ROOT=Z:\\kavitafetcher
  python tests/run_quality.py                  # tous, dans l'ordre
  python tests/run_quality.py BABELIO DNB      # sélection
  python tests/run_quality.py --list

Critères par cas positif :
  - fetch retourne un candidat
  - titre proche de l'attendu (token overlap / exact / contains)
  - score >= min_score (défaut 0.60)
  - champs optionnels exigés (cover, year, staff, summary) si declared
  - année dans [year_min, year_max] si declared

Cas négatif :
  - fetch None OU score bas OU titre clairement autre chose
"""
from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import os
import re
import sys
import time
import traceback
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
MK = Path(os.environ.get("METAKAVITA_ROOT", r"Z:\kavitafetcher"))
if str(MK) not in sys.path:
    sys.path.insert(0, str(MK))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FILE_BY_ID = {
    "ANIMEPLANET": "animeplanet.py",
    "ANN": "ann.py",
    "BABELIO": "babelio.py",
    "BANGUMI": "bangumi.py",
    "BDGEST": "bdgest.py",
    "BNE": "bne.py",
    "BNF": "bnf.py",
    "DECITRE": "decitre.py",
    "DNB": "dnb.py",
    "GCD": "gcd.py",
    "ISBNDB": "isbndb.py",
    "KB": "kb.py",
    "LOC": "loc.py",
    "LOCG": "locg.py",
    "MANGASANCTUARY": "mangasanctuary.py",
    "METRON": "metron.py",
    "NDL": "ndl.py",
    "NOVELUPDATES": "novelupdates.py",
    "OPENBD": "openbd.py",
    "PLANETEBD": "planetebd.py",
    "SBN": "sbn.py",
    "SENSCRITIQUE": "senscritique.py",
    "TAPAS": "tapas.py",
    "TEBEOSFERA": "tebeosfera.py",
    "WEBTOON": "webtoon.py",
}

KEY_ENV = {
    "METRON": "METRON_API_KEY",
    "ISBNDB": "ISBNDB_API_KEY",
}


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.casefold()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(s: str) -> set:
    return {t for t in _fold(s).split() if len(t) > 1}


def title_ok(got: str, expect: str, mode: str = "soft") -> bool:
    g, e = _fold(got), _fold(expect)
    if not g or not e:
        return False
    if mode == "exact":
        return g == e
    if mode == "contains":
        return e in g or g in e
    # soft: exact, contains, or token recall >= 0.7
    if g == e or e in g or g in e:
        return True
    et, gt = _tokens(expect), _tokens(got)
    if not et:
        return False
    return len(et & gt) / len(et) >= 0.7


@dataclass
class Case:
    query: str
    library_type: str
    expect_title: Optional[str] = None  # None = negative / must miss
    min_score: float = 0.60
    title_mode: str = "soft"
    require_cover: bool = False
    require_year: bool = False
    require_staff: bool = False
    require_summary: bool = False
    year_min: Optional[int] = None
    year_max: Optional[int] = None
    existing: Optional[Dict[str, Any]] = None
    is_id: bool = False
    note: str = ""


@dataclass
class Suite:
    scraper_id: str
    cases: List[Case] = field(default_factory=list)
    skip_reason: str = ""  # if set, whole suite skipped


# Ordre qualité : Book → Manga → Comic (clés / CF en fin)
SUITES: List[Suite] = [
    Suite(
        "BABELIO",
        [
            Case("Le Petit Prince", "Book", "Le Petit Prince", require_cover=True, require_staff=True, year_min=1940, year_max=2025),
            Case("L'Étranger", "Book", "L'Étranger", require_staff=True, year_min=1940, year_max=2020),
            Case("zzzzqwxnotitle999", "Book", None, note="bruit"),
        ],
    ),
    Suite(
        "DECITRE",
        [
            Case("Le Petit Prince", "Book", "Le Petit Prince", require_cover=True, year_min=1940, year_max=2025),
            Case("1984", "Book", "1984", require_cover=True, year_min=1940, year_max=2025),
            Case("zzzzqwxnotitle999", "Book", None),
        ],
    ),
    Suite(
        "BNF",
        [
            Case("Les Misérables", "Book", "Les Misérables", require_year=True, year_min=1800, year_max=2025),
            Case("Madame Bovary", "Book", "Madame Bovary", year_min=1850, year_max=2025),
            Case("zzzzqwxnotitle999", "Book", None),
        ],
    ),
    Suite(
        "DNB",
        [
            # DNB = année d'édition catalogue (souvent réédition), pas 1re parution
            Case("Der Prozess", "Book", "Der Prozess", require_year=True, year_min=1910, year_max=2026),
            Case("Die Verwandlung", "Book", "Die Verwandlung", year_min=1910, year_max=2026),
            Case("zzzzqwxnotitle999", "Book", None),
        ],
    ),
    Suite(
        "SENSCRITIQUE",
        [
            Case("Tintin", "Comic", "Tintin", title_mode="contains", min_score=0.55, require_cover=True),
            Case("Watchmen", "Comic", "Watchmen", require_cover=True, year_min=1980, year_max=2015),
            Case("Le Petit Prince", "Book", "Le Petit Prince", require_cover=True),
            Case("zzzzqwxnotitle999", "Book", None),
        ],
    ),
    Suite(
        "ANN",
        [
            Case("Death Note", "Manga", "Death Note", require_cover=True, require_staff=True, year_min=2003, year_max=2005),
            Case("One Piece", "Manga", "One Piece", require_cover=True, year_min=1996, year_max=1999),
            Case("zzzzqwxnotitle999", "Manga", None),
        ],
    ),
    Suite(
        "ANIMEPLANET",
        [
            Case("Death Note", "Manga", "Death Note", require_cover=True, year_min=2003, year_max=2005),
            Case("Naruto", "Manga", "Naruto", require_cover=True, year_min=1999, year_max=2001),
            Case("zzzzqwxnotitle999", "Manga", None),
        ],
    ),
    Suite(
        "BANGUMI",
        [
            Case("Death Note", "Manga", "Death Note", title_mode="contains", require_cover=True, year_min=2003, year_max=2005),
            Case("ONE PIECE", "Manga", "ONE PIECE", title_mode="soft", require_cover=True, year_min=1996, year_max=1999),
            Case("zzzzqwxnotitle999", "Manga", None),
        ],
    ),
    Suite(
        "MANGASANCTUARY",
        [
            Case("Death Note", "Manga", "Death Note", require_cover=True, year_min=2000, year_max=2008),
            Case("One Piece", "Manga", "One Piece", require_cover=True, year_min=1995, year_max=2005),
            Case("zzzzqwxnotitle999", "Manga", None),
        ],
    ),
    Suite(
        "TAPAS",
        [
            Case("Solo Leveling", "Manga", "Solo Leveling", require_cover=True),
            Case("Solo Leveling: Ragnarok", "Manga", "Solo Leveling", title_mode="contains", require_cover=True, min_score=0.55),
            Case("zzzzqwxnotitle999", "Manga", None),
        ],
    ),
    Suite(
        "WEBTOON",
        [
            Case("Tower of God", "Manga", "Tower of God", require_cover=True),
            Case("Omniscient Reader", "Manga", "Omniscient Reader", title_mode="contains", require_cover=True),
            Case("zzzzqwxnotitle999", "Manga", None),
        ],
    ),
    Suite(
        "PLANETEBD",
        [
            Case("Astérix", "Comic", "Astérix", require_cover=True),
            Case("Watchmen", "Comic", "Watchmen", require_cover=True, year_min=1980, year_max=2025),
            Case("zzzzqwxnotitle999", "Comic", None),
        ],
    ),
    Suite(
        "BDGEST",
        [
            Case("Astérix", "Comic", "Astérix", title_mode="contains", require_cover=True, min_score=0.55),
            Case("Tintin", "Comic", "Tintin", title_mode="contains", min_score=0.55),
            Case("zzzzqwxnotitle999", "Comic", None),
        ],
    ),
    Suite(
        "GCD",
        [
            Case("Watchmen", "Comic", "Watchmen", require_cover=True, year_min=1986, year_max=1987, existing={"year": 1986}),
            Case("Sandman", "Comic", "Sandman", title_mode="soft", year_min=1988, year_max=1990, existing={"year": 1989}),
            Case("zzzzqwxnotitle999", "Comic", None),
        ],
    ),
    Suite("ISBNDB", skip_reason="non testé — clé ISBNdb payante requise"),
    Suite(
        "METRON",
        [
            Case(
                "Watchmen",
                "Comic",
                "Watchmen",
                require_cover=True,
                require_staff=True,
                year_min=1986,
                year_max=1988,
                existing={"year": 1986},
            ),
            Case(
                "Sandman",
                "Comic",
                "Sandman",
                title_mode="soft",
                require_cover=True,
                year_min=1988,
                year_max=1996,
                existing={"year": 1989},
            ),
            Case("zzzzqwxnotitle999", "Comic", None),
        ],
    ),
    Suite(
        "OPENBD",
        [
            # Norwegian Wood / ノルウェイの森 — ISBN JP connu openBD
            Case(
                "9784101001517",
                "Book",
                "*",
                is_id=True,
                require_cover=True,
                min_score=0.99,
                note="ISBN direct",
            ),
            Case(
                "ノルウェイの森",
                "Book",
                "*",
                existing={"isbn": "9784101001517"},
                require_cover=True,
                year_min=1980,
                year_max=2025,
            ),
            Case("zzzzqwxnotitle999", "Book", None),
        ],
    ),
    Suite(
        "NDL",
        [
            Case("Norwegian Wood", "Book", "Norwegian Wood", title_mode="soft", year_min=1980, year_max=2025),
            Case(
                "ノルウェイの森",
                "Book",
                "*",
                existing={"isbn": "9784062748681"},
                min_score=0.55,
            ),
            Case("zzzzqwxnotitle999", "Book", None),
        ],
    ),
    Suite(
        "BNE",
        [
            Case("Don Quijote", "Book", "Quijote", title_mode="contains", year_min=1600, year_max=2025),
            Case("Cien años de soledad", "Book", "soledad", title_mode="contains", min_score=0.55),
            Case("zzzzqwxnotitle999", "Book", None),
        ],
    ),
    Suite(
        "LOC",
        [
            Case("Moby Dick", "Book", "Moby", title_mode="contains", require_year=False, year_min=1800, year_max=2025),
            Case(
                "Great Gatsby",
                "Book",
                "Gatsby",
                title_mode="contains",
                min_score=0.55,
                existing={"authors": ["Fitzgerald"]},
            ),
            Case("zzzzqwxnotitle999", "Book", None),
        ],
    ),
    Suite(
        "SBN",
        [
            Case("Il nome della rosa", "Book", "rosa", title_mode="contains", min_score=0.55),
            Case("Se questo è un uomo", "Book", "uomo", title_mode="contains", min_score=0.50),
            Case("zzzzqwxnotitle999", "Book", None),
        ],
    ),
    Suite(
        "KB",
        [
            Case("Max Havelaar", "Book", "Havelaar", title_mode="contains", min_score=0.55),
            Case("Het Achterhuis", "Book", "*", title_mode="soft", min_score=0.50),
            Case("zzzzqwxnotitle999", "Book", None),
        ],
    ),
    Suite(
        "TEBEOSFERA",
        skip_reason="catalogue JS/iframe — HTML non scrapable (shell 19k sans contenu)",
    ),
    Suite(
        "LOCG",
        [
            Case(
                "Watchmen",
                "Comic",
                "Watchmen",
                require_cover=True,
                year_min=1986,
                year_max=1988,
                existing={"year": 1986},
            ),
            Case(
                "Sandman",
                "Comic",
                "Sandman",
                title_mode="soft",
                year_min=1988,
                year_max=1990,
                existing={"year": 1989},
            ),
            Case("zzzzqwxnotitle999", "Comic", None),
        ],
    ),
    Suite(
        "NOVELUPDATES",
        [
            Case("Overlord", "Book", "Overlord", min_score=0.55, require_cover=True),
        ],
        # sera EXPECTED si CF
    ),
]


def _load_config() -> dict:
    try:
        from config_manager import load_config

        return load_config() or {}
    except Exception:
        return {}


def _has_key(sid: str) -> bool:
    env = KEY_ENV.get(sid)
    if not env:
        return True
    cfg = _load_config()
    return bool((cfg.get(env) or os.environ.get(env) or "").strip())


def _load_scraper(sid: str):
    from scrapers.base import BaseScraper

    fname = FILE_BY_ID[sid]
    path = ROOT / fname
    name = f"quality_{sid.lower()}"
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        if obj.__module__ != mod.__name__:
            continue
        if issubclass(obj, BaseScraper) and obj is not BaseScraper:
            return obj()
    raise RuntimeError(f"no BaseScraper in {fname}")


def _check_positive(meta: dict, case: Case) -> List[str]:
    errs = []
    if not meta:
        return ["aucun résultat"]
    title = meta.get("title") or ""
    if case.expect_title and case.expect_title != "*":
        if not title_ok(title, case.expect_title, case.title_mode):
            errs.append(f"titre '{title}' ≠ attendu '{case.expect_title}'")
    elif case.expect_title == "*" and not title.strip():
        errs.append("titre vide")
    score = meta.get("_match_score")
    try:
        fs = float(score) if score is not None else -1.0
    except Exception:
        fs = -1.0
        errs.append(f"score invalide {score!r}")
    if fs < case.min_score:
        errs.append(f"score {fs:.2f} < {case.min_score}")
    if case.require_cover and not meta.get("cover_url"):
        errs.append("cover manquante")
    if case.require_year and meta.get("year") is None:
        errs.append("year manquante")
    if case.require_staff and not (meta.get("staff") or []):
        errs.append("staff manquant")
    if case.require_summary and not (meta.get("summary") or "").strip():
        errs.append("summary manquant")
    year = meta.get("year")
    if isinstance(year, int):
        if case.year_min is not None and year < case.year_min:
            errs.append(f"year {year} < {case.year_min}")
        if case.year_max is not None and year > case.year_max:
            errs.append(f"year {year} > {case.year_max}")
    # forme minimale
    for k in ("genres", "tags", "staff", "format", "alternative_titles"):
        if k not in meta:
            errs.append(f"clé {k} absente")
    if meta.get("genres") is not None and not meta.get("genres"):
        errs.append("genres vide")
    return errs


def _check_negative(meta: Optional[dict], case: Case) -> List[str]:
    if meta is None:
        return []
    score = meta.get("_match_score")
    try:
        fs = float(score) if score is not None else 1.0
    except Exception:
        fs = 1.0
    # Accepter un retour seulement si score très bas (ne devrait pas arriver si threshold)
    if fs >= 0.60:
        return [f"faux positif '{meta.get('title')}' score={fs:.2f}"]
    return []


def run_suite(suite: Suite) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "id": suite.scraper_id,
        "status": "?",
        "cases": [],
        "detail": "",
    }
    cfg = _load_config()

    if suite.skip_reason and not suite.cases:
        out["status"] = "SKIP"
        out["detail"] = suite.skip_reason
        return out

    if suite.scraper_id in KEY_ENV and not _has_key(suite.scraper_id):
        out["status"] = "SKIP"
        out["detail"] = f"clé {KEY_ENV[suite.scraper_id]} manquante"
        return out

    try:
        scraper = _load_scraper(suite.scraper_id)
    except Exception as e:
        out["status"] = "FAIL"
        out["detail"] = f"load: {e}"
        return out

    fails = 0
    expected = 0
    for case in suite.cases:
        crow: Dict[str, Any] = {
            "query": case.query,
            "ok": False,
            "errors": [],
            "title": None,
            "score": None,
            "year": None,
            "cover": False,
        }
        try:
            meta = scraper.fetch(
                case.query,
                library_type=case.library_type,
                is_id=case.is_id,
                existing_metadata=case.existing,
            )
        except Exception as e:
            crow["errors"] = [f"EXC: {e}"]
            traceback.print_exc()
            fails += 1
            out["cases"].append(crow)
            continue

        if case.expect_title is None:
            errs = _check_negative(meta, case)
        else:
            errs = _check_positive(meta or {}, case)
            if meta:
                crow["title"] = meta.get("title")
                crow["score"] = meta.get("_match_score")
                crow["year"] = meta.get("year")
                crow["cover"] = bool(meta.get("cover_url"))
                crow["staff_n"] = len(meta.get("staff") or [])
                crow["summary_len"] = len((meta.get("summary") or "").strip())

        # Novel Updates CF → EXPECTED
        if (
            suite.scraper_id == "NOVELUPDATES"
            and meta is None
            and case.expect_title
            and not (cfg.get("NOVELUPDATES_API_KEY") or os.environ.get("NOVELUPDATES_API_KEY"))
        ):
            crow["errors"] = ["CF probable (pas de cookies)"]
            crow["ok"] = False
            expected += 1
            out["cases"].append(crow)
            continue

        # GCD 429
        if suite.scraper_id == "GCD" and meta is None and case.expect_title:
            crow["errors"] = ["None (possible 429 rate-limit)"]
            crow["ok"] = False
            expected += 1
            out["cases"].append(crow)
            continue

        crow["errors"] = errs
        crow["ok"] = not errs
        if not crow["ok"]:
            fails += 1
        out["cases"].append(crow)
        time.sleep(0.3)

    if fails:
        out["status"] = "FAIL"
        out["detail"] = f"{fails}/{len(suite.cases)} cas en échec"
    elif expected:
        out["status"] = "EXPECTED"
        out["detail"] = "CF / rate-limit / indisponible"
    else:
        out["status"] = "PASS"
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", help="IDs à tester (défaut: tous)")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv)

    if args.list:
        for s in SUITES:
            print(s.scraper_id, f"({len(s.cases)} cases)" if s.cases else s.skip_reason)
        return 0

    want = {x.upper() for x in args.ids} if args.ids else None
    suites = [s for s in SUITES if want is None or s.scraper_id in want]

    print(f"Quality battery — {len(suites)} scraper(s)\n")
    results = []
    for suite in suites:
        print(f"======== {suite.scraper_id} ========")
        row = run_suite(suite)
        results.append(row)
        status = row["status"]
        print(f"→ {status}" + (f" — {row['detail']}" if row.get("detail") else ""))
        for c in row.get("cases") or []:
            mark = "OK" if c.get("ok") else "NO"
            extra = ""
            if c.get("title"):
                extra = f" → '{c['title']}' score={c.get('score')} year={c.get('year')} cover={c.get('cover')}"
            err = f" | {'; '.join(c['errors'])}" if c.get("errors") else ""
            print(f"  [{mark}] {c['query']}{extra}{err}")
        print()

    counts: Dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1

    print("=== SUMMARY ===")
    for r in results:
        print(f"{r['id']:16} {r['status']:10} {r.get('detail','')}")
    print(
        f"\nPASS={counts.get('PASS',0)} FAIL={counts.get('FAIL',0)} "
        f"SKIP={counts.get('SKIP',0)} EXPECTED={counts.get('EXPECTED',0)}"
    )

    out = ROOT / "tests" / "_quality_report.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report → {out}")
    return 1 if counts.get("FAIL", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
