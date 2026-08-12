#!/usr/bin/env python3
"""Copy MetaKavita core scrapers into this repo + ensure is_core=True + meta.json."""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(r"Z:\kavitafetcher\scrapers")

MISSING = [
    "anilist.py",
    "bdtheque.py",
    "bedetheque.py",
    "comicvine.py",
    "googlebooks.py",
    "hardcover.py",
    "kitsu.py",
    "mal.py",
    "mangabaka.py",
    "mangadex.py",
    "manganews.py",
    "mangaupdates.py",
    "openlibrary.py",
    "shikimori.py",
]
EXISTING_CORE = [
    "ann.py",
    "babelio.py",
    "decitre.py",
    "locg.py",
    "metron.py",
    "planetebd.py",
    "senscritique.py",
]

CORE_WARN = [
    "Already ships in the MetaKavita image — Store shows state=core.",
]

META_NEW = {
    "ANILIST": {
        "method": "graphql",
        "languages": ["en", "ja"],
        "covers": True,
        "status": "stable",
        "homepage": "https://anilist.co",
        "region": "INTL",
        "auth": {"required": False, "config_key": None, "kind": "none"},
        "summary_fr": "AniList — métadonnées manga / LN (GraphQL). Scraper core MetaKavita.",
        "summary_en": "AniList — manga / LN metadata (GraphQL). MetaKavita core scraper.",
        "setup_fr": "Aucune clé. Livré en core MetaKavita (is_core).",
        "setup_en": "No API key. Ships as MetaKavita core (is_core).",
        "warnings": list(CORE_WARN),
    },
    "BDTHEQUE": {
        "method": "html",
        "languages": ["fr"],
        "covers": True,
        "status": "stable",
        "homepage": "https://www.bdtheque.com",
        "region": "FR",
        "auth": {"required": False, "config_key": None, "kind": "none"},
        "summary_fr": "BDTheque.com — BD franco-belge (HTML). Scraper core MetaKavita.",
        "summary_en": "BDTheque.com — Franco-Belgian comics (HTML). MetaKavita core scraper.",
        "setup_fr": "Aucune clé. Livré en core MetaKavita (is_core).",
        "setup_en": "No API key. Ships as MetaKavita core (is_core).",
        "warnings": list(CORE_WARN),
    },
    "BEDETHEQUE": {
        "method": "html",
        "languages": ["fr"],
        "covers": True,
        "status": "stable",
        "homepage": "https://www.bedetheque.com",
        "region": "FR",
        "auth": {"required": False, "config_key": None, "kind": "none"},
        "summary_fr": "Bedetheque — BD franco-belge (HTML). Scraper core MetaKavita.",
        "summary_en": "Bedetheque — Franco-Belgian comics (HTML). MetaKavita core scraper.",
        "setup_fr": "Aucune clé. Livré en core MetaKavita (is_core).",
        "setup_en": "No API key. Ships as MetaKavita core (is_core).",
        "warnings": list(CORE_WARN),
    },
    "COMICVINE": {
        "method": "api",
        "languages": ["en"],
        "covers": True,
        "status": "stable",
        "homepage": "https://comicvine.gamespot.com",
        "region": "US",
        "auth": {"required": True, "config_key": "COMICVINE_API_KEY", "kind": "api_key"},
        "summary_fr": "ComicVine — comics / BD (API). Scraper core MetaKavita.",
        "summary_en": "ComicVine — comics (API). MetaKavita core scraper.",
        "setup_fr": "Clé ComicVine → COMICVINE_API_KEY. Livré en core MetaKavita (is_core).",
        "setup_en": "ComicVine key → COMICVINE_API_KEY. Ships as MetaKavita core (is_core).",
        "warnings": list(CORE_WARN),
    },
    "GOOGLEBOOKS": {
        "method": "api",
        "languages": ["en", "fr"],
        "covers": True,
        "status": "stable",
        "homepage": "https://books.google.com",
        "region": "INTL",
        "auth": {"required": True, "config_key": "GOOGLEBOOKS_API_KEY", "kind": "api_key"},
        "summary_fr": "Google Books — livres / comics (API). Scraper core MetaKavita.",
        "summary_en": "Google Books — books / comics (API). MetaKavita core scraper.",
        "setup_fr": "Clé Google → GOOGLEBOOKS_API_KEY. Livré en core MetaKavita (is_core).",
        "setup_en": "Google key → GOOGLEBOOKS_API_KEY. Ships as MetaKavita core (is_core).",
        "warnings": list(CORE_WARN),
    },
    "HARDCOVER": {
        "method": "graphql",
        "languages": ["en"],
        "covers": True,
        "status": "stable",
        "homepage": "https://hardcover.app",
        "region": "US",
        "auth": {"required": True, "config_key": "HARDCOVER_API_KEY", "kind": "api_key"},
        "summary_fr": "Hardcover — livres (GraphQL). Scraper core MetaKavita.",
        "summary_en": "Hardcover — books (GraphQL). MetaKavita core scraper.",
        "setup_fr": "Clé Hardcover → HARDCOVER_API_KEY. Livré en core MetaKavita (is_core).",
        "setup_en": "Hardcover key → HARDCOVER_API_KEY. Ships as MetaKavita core (is_core).",
        "warnings": list(CORE_WARN),
    },
    "KITSU": {
        "method": "api",
        "languages": ["en", "ja"],
        "covers": True,
        "status": "stable",
        "homepage": "https://kitsu.io",
        "region": "INTL",
        "auth": {"required": False, "config_key": None, "kind": "none"},
        "summary_fr": "Kitsu — manga (JSON:API). Scraper core MetaKavita.",
        "summary_en": "Kitsu — manga (JSON:API). MetaKavita core scraper.",
        "setup_fr": "Aucune clé. Livré en core MetaKavita (is_core).",
        "setup_en": "No API key. Ships as MetaKavita core (is_core).",
        "warnings": list(CORE_WARN),
    },
    "MAL": {
        "method": "api",
        "languages": ["en", "ja"],
        "covers": True,
        "status": "stable",
        "homepage": "https://myanimelist.net",
        "region": "INTL",
        "auth": {"required": True, "config_key": "MAL_API_KEY", "kind": "api_key"},
        "summary_fr": "MyAnimeList — API officielle (Client ID). Scraper core MetaKavita.",
        "summary_en": "MyAnimeList — official API (Client ID). MetaKavita core scraper.",
        "setup_fr": "Client ID MAL → MAL_API_KEY. Livré en core MetaKavita (is_core).",
        "setup_en": "MAL Client ID → MAL_API_KEY. Ships as MetaKavita core (is_core).",
        "warnings": list(CORE_WARN),
    },
    "MANGABAKA": {
        "method": "api",
        "languages": ["en", "ja"],
        "covers": True,
        "status": "stable",
        "homepage": "https://mangabaka.org",
        "region": "INTL",
        "auth": {"required": False, "config_key": None, "kind": "none"},
        "summary_fr": "MangaBaka — API v2 (manga / novels). Scraper core MetaKavita.",
        "summary_en": "MangaBaka — v2 API (manga / novels). MetaKavita core scraper.",
        "setup_fr": "Aucune clé. Livré en core MetaKavita (is_core).",
        "setup_en": "No API key. Ships as MetaKavita core (is_core).",
        "warnings": list(CORE_WARN),
    },
    "MANGADEX": {
        "method": "api",
        "languages": ["en", "ja"],
        "covers": True,
        "status": "stable",
        "homepage": "https://mangadex.org",
        "region": "INTL",
        "auth": {"required": False, "config_key": None, "kind": "none"},
        "summary_fr": "MangaDex — API publique. Scraper core MetaKavita.",
        "summary_en": "MangaDex — public API. MetaKavita core scraper.",
        "setup_fr": "Aucune clé. Livré en core MetaKavita (is_core).",
        "setup_en": "No API key. Ships as MetaKavita core (is_core).",
        "warnings": list(CORE_WARN),
    },
    "MANGANEWS": {
        "method": "html",
        "languages": ["fr"],
        "covers": True,
        "status": "stable",
        "homepage": "https://www.manga-news.com",
        "region": "FR",
        "auth": {"required": False, "config_key": None, "kind": "none"},
        "summary_fr": "Manga-News — catalogue VF. Scraper core MetaKavita.",
        "summary_en": "Manga-News — French catalog. MetaKavita core scraper.",
        "setup_fr": "Aucune clé. Livré en core MetaKavita (is_core).",
        "setup_en": "No API key. Ships as MetaKavita core (is_core).",
        "warnings": list(CORE_WARN),
    },
    "MANGAUPDATES": {
        "method": "api",
        "languages": ["en"],
        "covers": True,
        "status": "stable",
        "homepage": "https://www.mangaupdates.com",
        "region": "US",
        "auth": {"required": False, "config_key": None, "kind": "none"},
        "summary_fr": "MangaUpdates (Baka-Updates) — API. Scraper core MetaKavita.",
        "summary_en": "MangaUpdates (Baka-Updates) — API. MetaKavita core scraper.",
        "setup_fr": "Aucune clé. Livré en core MetaKavita (is_core).",
        "setup_en": "No API key. Ships as MetaKavita core (is_core).",
        "warnings": list(CORE_WARN),
    },
    "OPENLIBRARY": {
        "method": "api",
        "languages": ["en"],
        "covers": True,
        "status": "stable",
        "homepage": "https://openlibrary.org",
        "region": "INTL",
        "auth": {"required": False, "config_key": None, "kind": "none"},
        "summary_fr": "Open Library — livres / romans. Scraper core MetaKavita.",
        "summary_en": "Open Library — books / novels. MetaKavita core scraper.",
        "setup_fr": "Aucune clé. Livré en core MetaKavita (is_core).",
        "setup_en": "No API key. Ships as MetaKavita core (is_core).",
        "warnings": list(CORE_WARN),
    },
    "SHIKIMORI": {
        "method": "api",
        "languages": ["ru", "en", "ja"],
        "covers": True,
        "status": "stable",
        "homepage": "https://shikimori.one",
        "region": "RU",
        "auth": {"required": False, "config_key": None, "kind": "none"},
        "summary_fr": "Shikimori — API JSON manga. Scraper core MetaKavita.",
        "summary_en": "Shikimori — manga JSON API. MetaKavita core scraper.",
        "setup_fr": "Aucune clé. Livré en core MetaKavita (is_core).",
        "setup_en": "No API key. Ships as MetaKavita core (is_core).",
        "warnings": list(CORE_WARN),
    },
}


def rewrite_imports(text: str) -> str:
    text = text.replace("from .base import", "from scrapers.base import")
    text = text.replace("from .utils import", "from scrapers.utils import")
    text = text.replace("from .wikidata_map import", "from scrapers.wikidata_map import")
    return text


def ensure_is_core(text: str) -> str:
    if re.search(r"^\s*is_core\s*=\s*True\s*$", text, re.M):
        return text
    m = re.search(r"(class \w+\(BaseScraper\):\n(?:    .*\n)*?    id = [^\n]+\n)", text)
    if not m:
        raise RuntimeError("could not insert is_core")
    return text[: m.end(1)] + "    is_core = True\n" + text[m.end(1) :]


def class_has_is_core(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for item in node.body:
            if isinstance(item, ast.Assign):
                for t in item.targets:
                    if isinstance(t, ast.Name) and t.id == "is_core":
                        if isinstance(item.value, ast.Constant) and item.value.value is True:
                            return True
    return False


def merge_entry(old: dict | None, new: dict) -> dict:
    """Refresh an entry from META_NEW without dropping curated fields.

    Warnings written by hand (rate-limit notes…) and `covers_note` live only in
    meta.json, so a blind overwrite would silently delete them.
    """
    merged = dict(new)
    if not old:
        return merged
    fresh = list(new.get("warnings") or [])
    kept = [w for w in (old.get("warnings") or []) if w not in fresh]
    merged["warnings"] = kept + fresh
    if old.get("covers_note") and not merged.get("covers_note"):
        merged["covers_note"] = old["covers_note"]
    return merged


def main() -> int:
    if not SRC.is_dir():
        print(f"missing MetaKavita scrapers dir: {SRC}", file=sys.stderr)
        return 1

    for name in MISSING:
        src = SRC / name
        if not src.is_file():
            print(f"missing source {src}", file=sys.stderr)
            return 1
        raw = rewrite_imports(src.read_text(encoding="utf-8"))
        raw = ensure_is_core(raw)
        dest = ROOT / name
        dest.write_text(raw, encoding="utf-8", newline="\n")
        assert class_has_is_core(dest), name
        print(f"copied {name}")

    for name in EXISTING_CORE:
        path = ROOT / name
        if not path.is_file():
            print(f"missing existing {name}", file=sys.stderr)
            return 1
        text = path.read_text(encoding="utf-8")
        text2 = ensure_is_core(text)
        if text2 != text:
            path.write_text(text2, encoding="utf-8", newline="\n")
            print(f"tagged {name}")
        else:
            print(f"already tagged {name}")
        assert class_has_is_core(path), name

    meta_path = ROOT / "store" / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    for sid, entry in META_NEW.items():
        meta[sid] = merge_entry(meta.get(sid), entry)
        print(f"meta+ {sid}")
    meta = {k: meta[k] for k in sorted(meta.keys())}
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"meta keys={len(meta)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
