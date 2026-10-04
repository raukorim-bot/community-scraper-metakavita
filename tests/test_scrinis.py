"""Tests Scrin.is (bêta) — hors réseau, MetaKavita remplacé par de petits stubs."""
from __future__ import annotations

import importlib
import sys
import types
from unittest.mock import MagicMock

import pytest


def _install_stubs():
    """Sans MetaKavita sur le PYTHONPATH, pose juste de quoi importer `scrinis`."""
    try:
        import scrapers.base  # noqa: F401
        import config_manager  # noqa: F401
        return []
    except ImportError:
        pass

    class BaseScraper:
        translations = {"fr": {}}

        def t(self, key):
            return self.translations["fr"].get(key, key)

        def _http_get(self, session, url, **kwargs):
            return session.get(url, **kwargs)

    scrapers = types.ModuleType("scrapers")
    base = types.ModuleType("scrapers.base")
    base.BaseScraper = BaseScraper
    utils = types.ModuleType("scrapers.utils")
    utils.PROVIDER_ERROR_AUTH = "auth"
    utils.attach_match_score = lambda c, s: {**c, "_match_score": s}
    utils.clean_title = lambda q, library_type=None: q.strip()
    utils.get_match_accept_threshold = lambda: 0.6
    utils.note_provider_error = lambda *a, **k: None
    utils.response_is_ok = lambda scraper, res, context="": res.status_code == 200
    utils.score_candidate = lambda cand, clean, existing=None: (
        1.0 if cand["title"].lower() == clean.lower() else 0.1
    )
    cfg = types.ModuleType("config_manager")
    cfg.load_config = lambda: {"SCRINIS_API_KEY": "oc_read_test"}
    cfg.get_max_genres = lambda: 5
    cfg.get_max_tags = lambda: 15
    curl = types.ModuleType("curl_cffi")
    curl.requests = MagicMock()
    stubs = {
        "scrapers": scrapers,
        "scrapers.base": base,
        "scrapers.utils": utils,
        "config_manager": cfg,
        "curl_cffi": curl,
        "curl_cffi.requests": curl.requests,
    }
    added = [name for name in stubs if name not in sys.modules]
    for name in added:
        sys.modules[name] = stubs[name]
    return added


_added = _install_stubs()
try:
    scrinis = importlib.import_module("scrinis")
finally:
    # Les stubs ne servent qu'à l'import : `scrinis` garde ses références. Les laisser
    # dans sys.modules ferait croire aux autres tests que MetaKavita est installé.
    for _name in _added:
        sys.modules.pop(_name, None)
ScrinisScraper = scrinis.ScrinisScraper

DETAIL = {
    "hub_id": "9b1deb4d-0000-0000-0000-000000000001",
    "public_n": 1042,
    "type": "manga",
    "format": "tankobon",
    "status": "ended",
    "titles": {
        "primary": "Berserk",
        "localized_primary": "Berserk",
        "all": [
            {"lang": "ja", "title": "ベルセルク", "role": "alt"},
            {"lang": "fr", "title": "Berserk", "role": "main"},
        ],
    },
    "dates": {"started_year": 1989},
    "publication": {"publisher": "Glénat"},
    "taxonomy": {
        "genres": [{"slug": "dark-fantasy", "label": "Dark fantasy", "kind": "genre"}],
        "tags": [{"slug": "demons", "label": "Démons", "kind": "tag"}],
        "demographics": [],
    },
    "age_rating": {"band": "18_plus", "nsfw": True},
    "summary": {"kind": "publisher", "lang": "fr", "text": "Guts, le bretteur noir."},
    "summaries": [],
    "credits": [
        {"role": "writer", "name": "Kentaro Miura"},
        {"role": "artist", "name": "Kentaro Miura"},
        {"role": "translator", "name": "Quelqu'un"},
    ],
    "ids": {"anilist": "30002", "mal": "2"},
    "covers": [{"url": None, "cdn_url": "/cdn/covers/abc.webp"}],
    "characters": [{"name": "Guts", "role": "main"}],
    "volumes": [{"n": 1, "isbn_13": "978-2-7234-2210-8"}],
}


def _res(payload, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    return r


def test_extract_id_from_url():
    s = ScrinisScraper()
    assert s.extract_id_from_url("https://scrin.is/series/1042") == "1042"
    assert s.extract_id_from_url("https://scrin.is/fr/series/1042?x=1") == "1042"
    assert s.extract_id_from_url("https://other.org/series/1042") is None
    assert s.extract_id_from_url("") is None


def test_build_candidate_maps_the_series_card():
    cand = ScrinisScraper()._build_candidate(DETAIL)
    assert cand["title"] == "Berserk"
    assert "ベルセルク" in cand["alternative_titles"]
    assert cand["status"] == "FINISHED"
    assert cand["year"] == 1989
    assert cand["publisher"] == "Glénat"
    assert cand["format"] == "manga"
    assert cand["genres"] == ["Dark fantasy"] and cand["tags"] == ["Démons"]
    assert cand["cover_url"] == "https://scrin.is/cdn/covers/abc.webp"
    assert cand["isbn"] == "9782723422108"
    assert cand["anilist_id"] == "30002" and cand["mal_id"] == "2"
    assert cand["age_rating"] == "erotica"
    assert cand["url"] == "https://scrin.is/series/1042"
    roles = {(s["role"], s["node"]["name"]["full"]) for s in cand["staff"]}
    assert roles == {("Story", "Kentaro Miura"), ("Art", "Kentaro Miura")}


def test_build_candidate_survives_nulls_and_refuses_an_untitled_card():
    s = ScrinisScraper()
    sparse = {
        "titles": {"primary": "X", "all": None},
        "taxonomy": None,
        "credits": None,
        "covers": None,
        "dates": None,
        "publication": None,
        "ids": None,
        "age_rating": None,
    }
    cand = s._build_candidate(sparse)
    assert cand["title"] == "X" and cand["staff"] == [] and cand["cover_url"] is None
    assert "age_rating" not in cand
    assert s._build_candidate({"titles": {}}) is None
    assert s._build_candidate(None) is None


def test_off_site_cover_is_dropped():
    assert ScrinisScraper._cover_url("https://evil.example/x.jpg") is None
    assert ScrinisScraper._cover_url("/cdn/covers/a.webp") == "https://scrin.is/cdn/covers/a.webp"


def test_fetch_sends_the_key_and_returns_the_scored_match(monkeypatch):
    s = ScrinisScraper()
    calls = []

    def fake_get(session, url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/series"):
            return _res({"items": [{"hub_id": DETAIL["hub_id"], "title": "Berserk", "started_year": 1989}]})
        return _res(DETAIL)

    monkeypatch.setattr(s, "_http_get", fake_get)
    cand = s.fetch("Berserk", "Manga")
    assert cand["title"] == "Berserk" and cand["_match_score"] == 1.0
    assert calls[0][1]["headers"]["Authorization"] == "Bearer oc_read_test"
    assert calls[0][1]["params"]["type"] == "manga"
    assert calls[1][0].endswith(f"/series/{DETAIL['hub_id']}")


def test_fetch_rejects_a_weak_match(monkeypatch):
    s = ScrinisScraper()
    monkeypatch.setattr(
        s,
        "_http_get",
        lambda session, url, **kw: _res({"items": [{"hub_id": "u", "title": "Autre chose"}]}),
    )
    assert s.fetch("Berserk", "Manga") is None


def test_fetch_by_isbn_goes_through_the_barcode_lookup(monkeypatch):
    s = ScrinisScraper()
    seen = []

    def fake_get(session, url, **kwargs):
        seen.append(url)
        if "/volumes/lookup" in url:
            assert kwargs["params"] == {"isbn": "9782723422108"}
            return _res({"parent_series": {"hub_id": DETAIL["hub_id"]}})
        return _res(DETAIL)

    monkeypatch.setattr(s, "_http_get", fake_get)
    cand = s.fetch("whatever", "Manga", existing_metadata={"isbn": "978-2-7234-2210-8"})
    assert cand["title"] == "Berserk"
    assert not any(u.endswith("/series") for u in seen)


def test_fetch_without_a_key_does_nothing(monkeypatch):
    monkeypatch.setattr(scrinis, "load_config", lambda: {})
    s = ScrinisScraper()
    monkeypatch.setattr(s, "_http_get", lambda *a, **k: pytest.fail("no request without a key"))
    assert s.fetch("Berserk") is None


def test_a_401_is_not_mistaken_for_no_result(monkeypatch):
    noted = []
    monkeypatch.setattr(scrinis, "note_provider_error", lambda *a: noted.append(a))
    s = ScrinisScraper()
    monkeypatch.setattr(s, "_http_get", lambda *a, **k: _res({}, status=401))
    assert s.fetch("Berserk") is None
    assert noted and noted[0][0] == "SCRINIS"


def test_fetch_by_id_accepts_a_url(monkeypatch):
    s = ScrinisScraper()
    seen = []
    monkeypatch.setattr(s, "_http_get", lambda sess, url, **kw: (seen.append(url), _res(DETAIL))[1])
    cand = s.fetch("https://scrin.is/series/1042", "Manga", is_id=True)
    assert seen == ["https://scrin.is/api/v1/series/1042"] and cand["_match_score"] == 1.0


VOLUMES_DETAIL = {
    "hub_id": DETAIL["hub_id"],
    "public_n": 1042,
    "editions": [
        {"edition": "standard", "medium": "print", "lang": "fr", "volume_count": 2, "is_primary": True},
        {"edition": "deluxe", "medium": "print", "lang": "fr", "volume_count": 1, "is_primary": False},
    ],
    "volumes": [
        {"public_n": 5001, "kind": "volume", "n": 1.0, "title": "L'Épée noire", "isbn_13": "978-2-7234-2210-8",
         "released_on": "1990-03-01", "covers": [{"cdn_url": "/cdn/covers/v1.webp"}],
         "summary": {"text": "Tome un."}},
        {"public_n": 5002, "kind": "volume", "n": 1.0, "variant": 1, "title": "Doublon"},
        {"public_n": 5003, "kind": "volume", "n": 2.5, "isbn_13": "pas un isbn"},
        {"public_n": 5004, "kind": "chapter", "n": 3.0, "title": "Chapitre"},
    ],
}


def test_volume_index_reads_the_primary_edition_in_one_series_call(monkeypatch):
    s = ScrinisScraper()
    calls = []

    def fake_get(session, url, **kwargs):
        calls.append((url, kwargs.get("params")))
        return _res(VOLUMES_DETAIL)

    monkeypatch.setattr(s, "_http_get", fake_get)
    index = s.fetch_volume_index("Berserk", "Manga", series_id="1042")
    assert [c[0] for c in calls] == ["https://scrin.is/api/v1/series/1042"] * 2
    assert calls[1][1] == {"edition": "standard", "medium": "print"}
    assert set(index) == {"1", "2.5"}
    assert index["1"] == {
        "provider_ref": "https://scrin.is/volumes/5001",
        "title": "L'Épée noire",
        "summary": "Tome un.",
        "release_date": "1990-03-01",
        "isbn": "9782723422108",
        "cover_url": "https://scrin.is/cdn/covers/v1.webp",
    }
    assert "isbn" not in index["2.5"]


def test_volume_index_resolves_the_series_by_search_and_declares_the_scope(monkeypatch):
    assert ScrinisScraper.scopes == {"series", "volume"}
    s = ScrinisScraper()

    def fake_get(session, url, **kwargs):
        if url.endswith("/series") and kwargs.get("params", {}).get("q"):
            return _res({"items": [{"hub_id": "uuid-1", "title": "Berserk"}]})
        return _res({**VOLUMES_DETAIL, "editions": []})

    monkeypatch.setattr(s, "_http_get", fake_get)
    assert "1" in s.fetch_volume_index("Berserk", "Manga")


def test_volume_index_gives_nothing_for_an_unknown_series(monkeypatch):
    s = ScrinisScraper()
    monkeypatch.setattr(s, "_http_get", lambda *a, **k: _res({"items": []}))
    assert s.fetch_volume_index("Inconnu", "Manga") is None


# --- appariement de l'édition possédée --------------------------------------

def _ed(edition="standard", medium="print", lang="fr", count=10, primary=False):
    return {"edition": edition, "medium": medium, "lang": lang, "volume_count": count, "is_primary": primary}


def _vol(n, edition_lang="fr", isbn=None, year=None, variant=0, public_n=None):
    return {
        "public_n": public_n or 9000 + int(n * 10) + variant, "kind": "volume", "n": float(n),
        "variant": variant, "lang": edition_lang, "isbn_13": isbn,
        "released_on": f"{year}-01-01" if year else None, "title": f"T{n}v{variant}",
    }


def test_library_hints_reads_what_metakavita_knows_and_ignores_the_rest():
    hints = scrinis.library_hints(
        {"isbn": "978-2-7234-2210-8", "volume_isbns": ["9782723422108", "bad"], "language": "FR-fr",
         "year": 2009, "volume_count": "12", "anything": 1}
    )
    assert hints == {"isbns": ["9782723422108"], "lang": "fr", "count": 12, "year": 2009}
    assert scrinis.library_hints(None) == {"isbns": [], "lang": "", "count": None, "year": None}


def test_edition_scoring_prefers_language_print_and_the_owned_volume_count():
    hints = {"isbns": [], "lang": "en", "count": 3, "year": None}
    ranked = scrinis.rank_editions(
        [_ed(lang="fr", count=3, primary=True), _ed(lang="en", count=3), _ed(medium="ebook", lang="en", count=3)],
        hints,
    )
    assert ranked[0][1]["lang"] == "en" and ranked[0][1]["medium"] == "print"
    # Sans indice : édition principale, puis papier standard français.
    none = {"isbns": [], "lang": "", "count": None, "year": None}
    assert scrinis.rank_editions([_ed(edition="deluxe"), _ed(primary=True)], none)[0][1]["edition"] == "standard"
    # Le nombre de tomes possédés départage une intégrale d'une édition en 10 tomes.
    # Posséder 12 tomes exclut une édition qui n'en compte que 10 ; posséder 3 tomes n'exclut rien.
    twelve = {"isbns": [], "lang": "fr", "count": 12, "year": None}
    got = scrinis.rank_editions([_ed(count=10, primary=True), _ed(edition="poche", count=12)], twelve)
    assert got[0][1]["edition"] == "poche"
    three = {"isbns": [], "lang": "fr", "count": 3, "year": None}
    assert scrinis.rank_editions([_ed(count=10, primary=True), _ed(edition="omnibus", count=3)], three)[0][1]["edition"] == "standard"


def _multi_edition_scraper(monkeypatch, lookup=None, per_edition=None):
    """Série à trois éditions ; `per_edition` rend les tomes de chaque groupe."""
    s = ScrinisScraper()
    calls = []
    editions = [
        _ed("standard", "print", "fr", 2, primary=True),
        _ed("deluxe", "print", "fr", 2),
        _ed("standard", "print", "en", 2),
    ]

    def fake_get(session, url, **kwargs):
        params = kwargs.get("params") or {}
        calls.append((url, params))
        if "/volumes/lookup" in url:
            return _res(lookup) if lookup else _res({}, status=404)
        if url.endswith("/series/1042"):
            key = (params.get("edition"), params.get("medium"))
            vols = (per_edition or {}).get(key, [])
            return _res({"public_n": 1042, "editions": editions, "volumes": vols})
        return _res({"items": []})

    monkeypatch.setattr(s, "_http_get", fake_get)
    return s, calls


FR_STD = [_vol(1, "fr", year=2001, public_n=1), _vol(2, "fr", year=2002, public_n=2),
          _vol(1, "en", year=2005, public_n=3)]
FR_DELUXE = [_vol(1, "fr", year=2019, public_n=11), _vol(2, "fr", year=2019, public_n=12)]
PER = {("standard", "print"): FR_STD, ("deluxe", "print"): FR_DELUXE, (None, None): FR_STD + FR_DELUXE}


def test_a_library_isbn_anchors_the_exact_edition(monkeypatch):
    lookup = {
        "volume": {"edition": "deluxe", "medium": "print", "lang": "fr"},
        "parent_series": {"hub_id": "h", "public_n": 1042},
    }
    s, calls = _multi_edition_scraper(monkeypatch, lookup=lookup, per_edition=PER)
    index = s.fetch_volume_index("Berserk", series_id="1042", existing_metadata={"isbn": "9782723422108"})
    assert {v["provider_ref"] for v in index.values()} == {"https://scrin.is/volumes/11", "https://scrin.is/volumes/12"}
    assert ("https://scrin.is/api/v1/series/1042", {"edition": "deluxe", "medium": "print"}) in calls


def test_an_isbn_from_another_series_gives_no_hint(monkeypatch):
    lookup = {"volume": {"edition": "deluxe", "medium": "print", "lang": "fr"}, "parent_series": {"hub_id": "other", "public_n": 7}}
    s, _ = _multi_edition_scraper(monkeypatch, lookup=lookup, per_edition=PER)
    index = s.fetch_volume_index("Berserk", series_id="1042", existing_metadata={"isbn": "9782723422108"})
    assert index["1"]["provider_ref"] == "https://scrin.is/volumes/1"  # édition principale


def test_the_language_is_filtered_client_side_inside_an_edition_group(monkeypatch):
    s, _ = _multi_edition_scraper(monkeypatch, per_edition=PER)
    index = s.fetch_volume_index("Berserk", series_id="1042", existing_metadata={"language": "fr"})
    # Le tome 1 anglais (public_n 3) partage `standard`/`print` avec le français : il ne doit pas gagner.
    assert index["1"]["provider_ref"] == "https://scrin.is/volumes/1"
    en = ScrinisScraper._group_volumes({"volumes": FR_STD}, "en")
    assert [v["public_n"] for v in en] == [3]


def test_tied_editions_are_split_by_the_year_of_volume_one(monkeypatch):
    # Même langue, même support, même nombre de tomes : seule l'année distingue.
    s, calls = _multi_edition_scraper(monkeypatch, per_edition=PER)
    index = s.fetch_volume_index(
        "Berserk", series_id="1042", existing_metadata={"language": "fr", "year": 2019, "volume_count": 2}
    )
    assert index["1"]["provider_ref"] == "https://scrin.is/volumes/11"
    # Et sans indice d'année, l'édition principale reste.
    s2, _ = _multi_edition_scraper(monkeypatch, per_edition=PER)
    index2 = s2.fetch_volume_index("Berserk", series_id="1042", existing_metadata={"language": "fr", "volume_count": 2})
    assert index2["1"]["provider_ref"] == "https://scrin.is/volumes/1"


def test_homonym_volumes_are_split_by_isbn_then_year_then_age():
    a = _vol(1, isbn="978-2-7234-2210-8", year=2001, variant=0, public_n=1)
    b = _vol(1, isbn="978-2-205-05290-9", year=2008, variant=1, public_n=2)
    pick = ScrinisScraper._pick_variant
    none = {"isbns": [], "year": None}
    assert pick([b, a], none)["public_n"] == 1                                   # le plus ancien
    assert pick([a, b], {"isbns": ["9782205052909"], "year": None})["public_n"] == 2  # ISBN possédé
    assert pick([a, b], {"isbns": [], "year": 2008})["public_n"] == 2             # année


def test_a_multi_edition_series_card_carries_no_isbn_of_a_random_edition():
    cand = ScrinisScraper()._build_candidate({**DETAIL, "editions": [_ed(), _ed("deluxe")]})
    assert "isbn" not in cand
    assert ScrinisScraper()._build_candidate({**DETAIL, "editions": [_ed()]})["isbn"] == "9782723422108"
