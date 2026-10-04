"""Scrin.is — catalogue manga / BD / livres via l'API REST publique (bêta).

Scrin.is expose `/api/v1` (OmniCodex). La lecture est ouverte, mais une clé
`read` lève le plafond anonyme (15 req/min) : elle se saisit dans Config sous
`SCRINIS_API_KEY`. Cette clé ne donne que la consultation, jamais l'ingestion.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from curl_cffi import requests

from config_manager import get_max_genres, get_max_tags, load_config
from scrapers.base import BaseScraper
from scrapers.utils import (
    PROVIDER_ERROR_AUTH,
    attach_match_score,
    clean_title,
    get_match_accept_threshold,
    note_provider_error,
    response_is_ok,
    score_candidate,
)

_SITE = "https://scrin.is"
_API = f"{_SITE}/api/v1"

_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$")
_SERIES_URL_RE = re.compile(r"scrin\.is/(?:[a-z]{2}(?:-[A-Za-z]{2})?/)?series/([0-9A-Za-z-]+)")

_STATUS_MAP = {
    "releasing": "RELEASING",
    "ongoing": "RELEASING",
    "ended": "FINISHED",
    "completed": "FINISHED",
    "finished": "FINISHED",
    "hiatus": "HIATUS",
    "cancelled": "CANCELLED",
    "canceled": "CANCELLED",
}

# Types Scrin.is demandés selon la bibliothèque Kavita (CSV accepté par l'API).
_TYPE_FILTER = {
    "Manga": "manga",
    "Comic": "comic",
    "Book": "book,ln",
}

_FORMAT_MAP = {"manga": "manga", "comic": "comic", "book": "book", "ln": "book"}

_STORY_ROLES = {"author", "writer", "story", "original_creator"}
_ART_ROLES = {"artist", "illustrator", "penciler", "inker", "colorist"}


def _clean(value: Any) -> str:
    return str(value).strip() if isinstance(value, (str, int, float)) and str(value).strip() else ""


# ------------------------------------------------------------------ éditions
#
# Une série Scrin.is a plusieurs éditions (`editions[]` = groupes
# `(edition, medium, lang)` : standard / deluxe / intégrale / poche, papier /
# ebook, fr / en…). L'index des tomes ne doit en lire qu'UNE : celle que la
# bibliothèque Kavita possède. Indices, du plus sûr au plus faible :
#   1. un ISBN de la bibliothèque → `/volumes/lookup` rend le tome, donc son
#      groupe d'édition exact ;
#   2. la langue, le support (papier), le nombre de tomes possédés ;
#   3. l'année de parution du tome 1, ou un ISBN présent dans un groupe, quand
#      les groupes restent à égalité ;
#   4. à défaut, l'édition principale du site.
# Les indices viennent de `existing_metadata` ; une clé absente est ignorée.

_ISBN_KEYS = ("isbn", "isbns", "volume_isbns", "isbn_13")
_LANG_KEYS = ("language", "lang", "library_language")
_COUNT_KEYS = ("volume_count", "volumes_count", "total_volumes", "local_volumes", "owned_volumes")

#: Écart de score en dessous duquel deux éditions restent départageables par un indice
#: fin (année, ISBN) : large avec un tel indice — un bonus d'année pèse plus que
#: l'a priori « standard / principale » —, étroit sans.
_EDITION_TIE = 10.0
_EDITION_TIE_WITH_HINT = 20.0


def _isbn_digits(value: Any) -> str:
    digits = re.sub(r"[^0-9Xx]", "", str(value or ""))
    return digits.upper() if len(digits) in (10, 13) else ""


def library_hints(existing_metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Ce que MetaKavita sait de l'édition possédée : ISBN, langue, année, nombre de tomes."""
    meta = existing_metadata if isinstance(existing_metadata, dict) else {}
    isbns: List[str] = []
    for key in _ISBN_KEYS:
        raw = meta.get(key)
        for item in raw if isinstance(raw, (list, tuple, set)) else [raw]:
            digits = _isbn_digits(item)
            if digits and digits not in isbns:
                isbns.append(digits)
    lang = ""
    for key in _LANG_KEYS:
        lang = _clean(meta.get(key)).lower()[:2]
        if lang:
            break
    count = None
    for key in _COUNT_KEYS:
        try:
            count = int(meta.get(key))
        except (TypeError, ValueError):
            continue
        if count > 0:
            break
        count = None
    year = meta.get("year")
    return {
        "isbns": isbns,
        "lang": lang,
        "count": count,
        "year": year if isinstance(year, int) else None,
    }


def edition_score(edition: dict, hints: Dict[str, Any]) -> float:
    """Vraisemblance qu'un groupe d'édition soit celui de la bibliothèque (sans réseau)."""
    score = 0.0
    lang = _clean(edition.get("lang")).lower()
    if hints.get("lang"):
        score += 40.0 if lang == hints["lang"] else 0.0
    elif lang == "fr":
        score += 5.0  # catalogue francophone : la VF est la plus probable sans autre indice
    medium = _clean(edition.get("medium")).lower()
    score += 20.0 if medium == "print" else -10.0 if medium == "audiobook" else 0.0
    if _clean(edition.get("edition")).lower() == "standard":
        score += 8.0
    have, owned = edition.get("volume_count"), hints.get("count")
    if isinstance(have, int) and have > 0 and owned:
        # Une collection peut être partielle (posséder 3 tomes sur 10 est normal) ;
        # posséder PLUS de tomes que l'édition n'en compte, non.
        score += -25.0 if owned > have else 10.0 * owned / have
    if edition.get("is_primary"):
        score += 6.0
    return score


def edition_key(edition: dict) -> tuple:
    return tuple(_clean(edition.get(k)).lower() for k in ("edition", "medium", "lang"))


def rank_editions(editions: List[dict], hints: Dict[str, Any]) -> List[tuple]:
    """`[(score, groupe)]` du meilleur au moins bon ; égalité départagée par l'ordre du site."""
    scored = [(edition_score(e, hints), i, e) for i, e in enumerate(editions)]
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [(sc, e) for sc, _, e in scored]


class ScrinisScraper(BaseScraper):
    id = "SCRINIS"
    display_name = "Scrin.is (Bêta)"
    supported_types = {"Manga", "Comic", "Book"}
    scopes = {"series", "volume"}
    rate_limit = 0.5
    proxy_domains = ["scrin.is", "www.scrin.is"]
    has_direct_id_support = True
    requires_proxy = False
    needs_api_key = True
    uses_unified_scoring = True
    version = "0.2.0"

    translations = {
        "fr": {
            "display_name": "Scrin.is (Bêta)",
            "err_missing_key": "❌ Clé API Scrin.is manquante. Configurez SCRINIS_API_KEY dans les paramètres.",
            "err_auth": "🔑 [Scrin.is] Clé refusée (HTTP 401) — vérifiez SCRINIS_API_KEY dans les paramètres.",
            "direct_id": "🎯 [Scrin.is] Requête par identifiant : '{0}'",
            "search_isbn": "🔎 [Scrin.is] Recherche prioritaire via ISBN Kavita : '{0}'",
            "search_title": "🔍 [Scrin.is] Recherche pour '{0}'...",
            "no_match": "⚠️ [Scrin.is] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [Scrin.is] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [Scrin.is] Erreur : {0}",
            "covers_err": "❌ [Covers] Erreur Scrin.is : {0}",
            "volume_index_err": "[Scrin.is] Index des tomes : {0}",
        },
        "en": {
            "display_name": "Scrin.is (Beta)",
            "err_missing_key": "❌ Scrin.is API key missing. Set SCRINIS_API_KEY in settings.",
            "err_auth": "🔑 [Scrin.is] Key rejected (HTTP 401) — check SCRINIS_API_KEY in settings.",
            "direct_id": "🎯 [Scrin.is] Request by identifier: '{0}'",
            "search_isbn": "🔎 [Scrin.is] Priority search via Kavita ISBN: '{0}'",
            "search_title": "🔍 [Scrin.is] Searching for '{0}'...",
            "no_match": "⚠️ [Scrin.is] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [Scrin.is] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [Scrin.is] Error: {0}",
            "covers_err": "❌ [Covers] Scrin.is error: {0}",
            "volume_index_err": "[Scrin.is] Volume index: {0}",
        },
    }

    # ------------------------------------------------------------------ ids

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url or not isinstance(url, str):
            return None
        match = _SERIES_URL_RE.search(url)
        return match.group(1) if match else None

    # ----------------------------------------------------------------- HTTP

    @staticmethod
    def _headers(api_key: str) -> Dict[str, str]:
        key = api_key.strip()
        if key.lower().startswith("bearer "):
            key = key[7:].strip()
        return {
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "User-Agent": "MetaKavita-Scrinis/0.1",
        }

    def _get_json(
        self, session, headers: Dict[str, str], path: str, params: Optional[dict] = None
    ) -> Optional[Any]:
        res = self._http_get(
            session, f"{_API}{path}", params=params, headers=headers, timeout=20
        )
        if res.status_code == 401:
            note_provider_error(self.id, PROVIDER_ERROR_AUTH, "HTTP 401")
            logging.error(self.t("err_auth"))
            return None
        # 404 : l'identifiant ou le code-barres n'existe pas, ce n'est pas une panne.
        if res.status_code == 404:
            return None
        if not response_is_ok(self, res, context=path):
            return None
        try:
            return res.json()
        except Exception:
            return None

    # ---------------------------------------------------------------- fetch

    def fetch(
        self,
        query: str,
        library_type: str = "Manga",
        is_id: bool = False,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        api_key = (load_config().get("SCRINIS_API_KEY") or "").strip()
        if not api_key:
            logging.error(self.t("err_missing_key"))
            return None

        headers = self._headers(api_key)
        session = requests.Session()

        try:
            if is_id:
                ref = self.extract_id_from_url(query) or str(query).strip()
                logging.info(self.t("direct_id").format(ref))
                detail = self._get_json(session, headers, f"/series/{ref}")
                if not isinstance(detail, dict):
                    return None
                return attach_match_score(self._build_candidate(detail), 1.0)

            clean = clean_title(query, library_type=library_type)

            isbn = re.sub(r"[^0-9Xx]", "", str((existing_metadata or {}).get("isbn") or ""))
            if isbn:
                logging.info(self.t("search_isbn").format(isbn))
                hit = self._get_json(session, headers, "/volumes/lookup", {"isbn": isbn})
                parent = (hit or {}).get("parent_series") if isinstance(hit, dict) else None
                if isinstance(parent, dict) and parent.get("hub_id"):
                    detail = self._get_json(session, headers, f"/series/{parent['hub_id']}")
                    if isinstance(detail, dict):
                        return attach_match_score(self._build_candidate(detail), 1.0)

            logging.info(self.t("search_title").format(clean))
            items = self._search(session, headers, clean, library_type)
            best_item, best_score = None, -1.0
            for item in items:
                light = self._light_candidate(item)
                if not light:
                    continue
                score = score_candidate(light, clean, existing_metadata)
                if score > best_score:
                    best_item, best_score = item, score

            if not best_item or best_score < get_match_accept_threshold():
                logging.info(
                    self.t("no_match").format(clean, int(max(best_score, 0) * 100))
                )
                return None

            detail = self._get_json(session, headers, f"/series/{best_item['hub_id']}")
            candidate = self._build_candidate(detail) if isinstance(detail, dict) else None
            if not candidate:
                return None
            logging.info(self.t("matched").format(candidate["title"], int(best_score * 100)))
            return attach_match_score(candidate, best_score)

        except Exception as e:  # noqa: BLE001 — un scraper ne doit jamais faire tomber l'enrichissement
            logging.error(self.t("err").format(e))
            return None

    def _search(
        self, session, headers: Dict[str, str], query: str, library_type: str, limit: int = 10
    ) -> List[dict]:
        params: Dict[str, Any] = {"q": query, "limit": limit}
        type_filter = _TYPE_FILTER.get(library_type)
        if type_filter:
            params["type"] = type_filter
        body = self._get_json(session, headers, "/series", params)
        items = body.get("items") if isinstance(body, dict) else None
        return [i for i in (items or []) if isinstance(i, dict) and i.get("hub_id")]

    # ------------------------------------------------------------ candidates

    @staticmethod
    def _cover_url(path: Any) -> Optional[str]:
        url = _clean(path)
        if not url:
            return None
        if url.startswith("/"):
            return f"{_SITE}{url}"
        return url if url.startswith("https://scrin.is/") else None

    def _light_candidate(self, item: dict) -> Optional[dict]:
        """Candidat minimal bâti sur un élément de liste, juste assez pour le scorer."""
        title = _clean(item.get("title")) or _clean(item.get("title_localized"))
        if not title:
            return None
        alts = [t for t in (title, _clean(item.get("title_localized"))) if t]
        light: Dict[str, Any] = {
            "title": title,
            "alternative_titles": list(dict.fromkeys(alts)),
            "year": item.get("started_year"),
            "publisher": item.get("publisher"),
            "staff": [],
        }
        return light

    def _build_candidate(self, data: dict) -> Optional[dict]:
        if not isinstance(data, dict):
            return None

        titles = data.get("titles") or {}
        primary = _clean(titles.get("primary")) or _clean(titles.get("localized_primary"))
        alt_titles: List[str] = []
        for entry in titles.get("all") or []:
            text = _clean(entry.get("title")) if isinstance(entry, dict) else ""
            if text and text not in alt_titles:
                alt_titles.append(text)
        if primary and primary not in alt_titles:
            alt_titles.insert(0, primary)
        if not primary and alt_titles:
            primary = alt_titles[0]
        if not primary:
            return None

        taxonomy = data.get("taxonomy") or {}

        def _labels(key: str) -> List[str]:
            out = []
            for term in taxonomy.get(key) or []:
                label = _clean(term.get("label")) if isinstance(term, dict) else ""
                if label and label not in out:
                    out.append(label)
            return out

        genres = _labels("genres")
        tags = _labels("tags")

        staff = []
        seen = set()
        for credit in data.get("credits") or []:
            if not isinstance(credit, dict):
                continue
            name = _clean(credit.get("name"))
            role = _clean(credit.get("role")).lower()
            kind = "Story" if role in _STORY_ROLES else "Art" if role in _ART_ROLES else None
            if name and kind and (kind, name) not in seen:
                seen.add((kind, name))
                staff.append({"role": kind, "node": {"name": {"full": name}}})

        summary = ""
        for pick in [data.get("summary")] + list(data.get("summaries") or []):
            if isinstance(pick, dict) and _clean(pick.get("text")):
                summary = _clean(pick.get("text"))
                break

        cover_url = None
        for cover in data.get("covers") or []:
            if isinstance(cover, dict):
                cover_url = self._cover_url(cover.get("cdn_url") or cover.get("url"))
                if cover_url:
                    break

        dates = data.get("dates") or {}
        year = dates.get("started_year")
        year = year if isinstance(year, int) else None

        publication = data.get("publication") or {}
        ids = data.get("ids") or {}
        public_n = data.get("public_n")

        candidate: Dict[str, Any] = {
            "title": primary,
            "alternative_titles": alt_titles,
            "summary": summary,
            "cover_url": cover_url,
            "genres": genres[: get_max_genres()],
            "tags": tags[: get_max_tags()],
            "year": year,
            "status": _STATUS_MAP.get(_clean(data.get("status")).lower()),
            "staff": staff,
            "characters": [
                {"name": c["name"], "role": c.get("role")}
                for c in data.get("characters") or []
                if isinstance(c, dict) and _clean(c.get("name"))
            ],
            "publisher": _clean(publication.get("publisher")) or None,
            "format": "webtoon"
            if _clean(data.get("format")).lower() == "webtoon"
            else _FORMAT_MAP.get(_clean(data.get("type")).lower()),
            "url": f"{_SITE}/series/{public_n}" if public_n else None,
            "anilist_id": _clean(ids.get("anilist")) or None,
            "mal_id": _clean(ids.get("mal") or ids.get("myanimelist")) or None,
            "scrinis_id": str(public_n) if public_n else None,
        }

        age = data.get("age_rating") or {}
        if age.get("nsfw") is True:
            candidate["age_rating"] = "erotica"
        elif _clean(age.get("band")) == "all_ages":
            candidate["age_rating"] = "safe"

        # Plusieurs éditions : le premier tome listé peut être celui d'une intégrale
        # ou d'un ebook. Mieux vaut aucun ISBN qu'un ISBN d'une autre édition.
        if len(data.get("editions") or []) <= 1:
            isbn = self._first_isbn(data.get("volumes"))
            if isbn:
                candidate["isbn"] = isbn
        return candidate

    @staticmethod
    def _first_isbn(volumes: Any) -> Optional[str]:
        for vol in volumes or []:
            if isinstance(vol, dict) and vol.get("isbn_13"):
                digits = re.sub(r"\D", "", str(vol["isbn_13"]))
                if digits:
                    return digits
        return None

    # -------------------------------------------------------------- volumes

    @staticmethod
    def _volume_number(n: Any) -> Optional[str]:
        try:
            value = float(n)
        except (TypeError, ValueError):
            return None
        return str(int(value)) if value == int(value) else str(value)

    def _volume_payload(self, vol: dict, series_ref: str) -> Dict[str, str]:
        summary = ""
        for pick in [vol.get("summary")] + list(vol.get("summaries") or []):
            if isinstance(pick, dict) and _clean(pick.get("text")):
                summary = _clean(pick.get("text"))
                break
        cover = ""
        for c in vol.get("covers") or []:
            if isinstance(c, dict):
                cover = self._cover_url(c.get("cdn_url") or c.get("url")) or ""
                if cover:
                    break
        isbn = _isbn_digits(vol.get("isbn_13"))
        payload = {
            "provider_ref": f"{_SITE}/volumes/{vol['public_n']}" if vol.get("public_n") else series_ref,
            "title": _clean(vol.get("title")),
            "summary": summary,
            "release_date": _clean(vol.get("released_on")),
            "isbn": isbn if len(isbn) == 13 else "",
            "cover_url": cover,
        }
        return {k: v for k, v in payload.items() if v}

    def _resolve_series_id(
        self, session, headers, query, library_type, series_id, existing_metadata
    ) -> Optional[str]:
        if series_id:
            return self.extract_id_from_url(str(series_id)) or str(series_id).strip()
        for isbn in library_hints(existing_metadata)["isbns"][:3]:
            hit = self._get_json(session, headers, "/volumes/lookup", {"isbn": isbn})
            parent = hit.get("parent_series") if isinstance(hit, dict) else None
            if isinstance(parent, dict) and parent.get("hub_id"):
                return str(parent["hub_id"])
        clean = clean_title(query, library_type=library_type) or (query or "").strip()
        best_id, best_score = None, -1.0
        for item in self._search(session, headers, clean, library_type):
            light = self._light_candidate(item)
            if not light:
                continue
            score = score_candidate(light, clean, existing_metadata)
            if score > best_score:
                best_id, best_score = item["hub_id"], score
        return str(best_id) if best_id and best_score >= get_match_accept_threshold() else None

    def _edition_detail(self, session, headers, ref: str, edition: dict, cache: dict) -> Optional[dict]:
        """Fiche série restreinte à un groupe d'édition (une requête, mémorisée)."""
        key = edition_key(edition)
        if key not in cache:
            params = {k: edition[k] for k in ("edition", "medium") if edition.get(k)}
            body = self._get_json(session, headers, f"/series/{ref}", params)
            cache[key] = body if isinstance(body, dict) else None
        return cache[key]

    @staticmethod
    def _group_volumes(detail: Optional[dict], lang: str) -> List[dict]:
        """Tomes du groupe : `edition`/`medium` filtrent côté site, pas la langue."""
        out = []
        for vol in (detail or {}).get("volumes") or []:
            if not isinstance(vol, dict) or vol.get("kind", "volume") != "volume":
                continue
            if lang and _clean(vol.get("lang")).lower() not in ("", lang):
                continue
            out.append(vol)
        return out

    @staticmethod
    def _first_year(volumes: List[dict]) -> Optional[int]:
        years = []
        for vol in volumes:
            try:
                years.append(int(str(vol.get("released_on") or "")[:4]))
            except ValueError:
                continue
        return min(years) if years else None

    def _anchor_edition(self, session, headers, ref: str, editions: List[dict], hints) -> Optional[dict]:
        """Le groupe d'un ISBN de la bibliothèque, quand Scrin.is connaît ce tome."""
        for isbn in hints["isbns"][:3]:
            hit = self._get_json(session, headers, "/volumes/lookup", {"isbn": isbn})
            volume = hit.get("volume") if isinstance(hit, dict) else None
            parent = hit.get("parent_series") if isinstance(hit, dict) else None
            if not isinstance(volume, dict):
                continue
            if isinstance(parent, dict) and ref not in (str(parent.get("hub_id")), str(parent.get("public_n"))):
                continue  # ISBN d'une autre série : aucun indice sur celle-ci
            want = tuple(_clean(volume.get(k)).lower() for k in ("edition", "medium", "lang"))
            for edition in editions:
                if edition_key(edition) == want:
                    return edition
        return None

    def choose_edition(
        self, session, headers, ref: str, detail: dict, hints: Dict[str, Any], cache: dict
    ) -> Optional[dict]:
        """Le groupe d'édition à indexer, ou None quand la série n'en a pas d'inventaire."""
        editions = [e for e in detail.get("editions") or [] if isinstance(e, dict)]
        if len(editions) <= 1:
            return editions[0] if editions else None
        anchor = self._anchor_edition(session, headers, ref, editions, hints)
        if anchor:
            return anchor
        ranked = rank_editions(editions, hints)
        fine = bool(hints["year"] or hints["isbns"])
        window = _EDITION_TIE_WITH_HINT if fine else _EDITION_TIE
        close = [(sc, e) for sc, e in ranked if ranked[0][0] - sc < window][:3]
        if len(close) > 1 and fine:
            best, best_total = close[0][1], float("-inf")
            for prior, edition in close:
                vols = self._group_volumes(
                    self._edition_detail(session, headers, ref, edition, cache),
                    _clean(edition.get("lang")).lower(),
                )
                bonus = 0.0
                if any(_isbn_digits(v.get("isbn_13")) in hints["isbns"] for v in vols if v.get("isbn_13")):
                    bonus += 100.0
                first = self._first_year(vols)
                if hints["year"] and first is not None and abs(first - hints["year"]) <= 1:
                    bonus += 25.0
                if prior + bonus > best_total:
                    best, best_total = edition, prior + bonus
            return best
        return ranked[0][1]

    @staticmethod
    def _pick_variant(candidates: List[dict], hints: Dict[str, Any]) -> dict:
        """Entre homonymes d'un même rang : l'ISBN possédé, puis l'année, puis le plus ancien."""
        def rank(vol: dict):
            isbn_hit = _isbn_digits(vol.get("isbn_13")) in hints["isbns"] if vol.get("isbn_13") else False
            try:
                year_hit = abs(int(str(vol.get("released_on"))[:4]) - hints["year"]) <= 1 if hints["year"] else False
            except ValueError:
                year_hit = False
            return (not isbn_hit, not year_hit, vol.get("variant") or 0)

        return sorted(candidates, key=rank)[0]

    def fetch_volume_index(
        self,
        query: str,
        library_type: str = "Manga",
        series_id: Optional[str] = None,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """`{numéro: payload}` pour l'édition que la bibliothèque possède (voir plus haut).

        Une requête pour la fiche, une pour l'édition retenue ; au plus trois de
        plus quand des groupes sont indiscernables et qu'un indice les départage.
        """
        api_key = (load_config().get("SCRINIS_API_KEY") or "").strip()
        if not api_key:
            logging.error(self.t("err_missing_key"))
            return None
        headers = self._headers(api_key)
        session = requests.Session()
        try:
            ref = self._resolve_series_id(
                session, headers, query, library_type, series_id, existing_metadata
            )
            if not ref:
                return None
            detail = self._get_json(session, headers, f"/series/{ref}")
            if not isinstance(detail, dict):
                return None
            hints = library_hints(existing_metadata)
            cache: dict = {}
            edition = self.choose_edition(session, headers, ref, detail, hints, cache)
            lang = _clean((edition or {}).get("lang")).lower()
            if edition and len(detail.get("editions") or []) > 1:
                detail = self._edition_detail(session, headers, ref, edition, cache) or detail
            series_ref = f"{_SITE}/series/{detail.get('public_n') or ref}"
            by_number: Dict[str, List[dict]] = {}
            for vol in self._group_volumes(detail, lang):
                number = self._volume_number(vol.get("n"))
                if number is not None:
                    by_number.setdefault(number, []).append(vol)
            index: Dict[str, Any] = {}
            for number, candidates in by_number.items():
                payload = self._volume_payload(self._pick_variant(candidates, hints), series_ref)
                if payload:
                    index[number] = payload
            return index or None
        except Exception as e:  # noqa: BLE001
            logging.error(self.t("volume_index_err").format(e))
            return None
        finally:
            try:
                session.close()
            except Exception:
                pass

    # --------------------------------------------------------------- covers

    def fetch_covers(self, query: str, library_type: str = "Manga") -> List[Dict[str, str]]:
        api_key = (load_config().get("SCRINIS_API_KEY") or "").strip()
        if not api_key:
            return []
        covers: List[Dict[str, str]] = []
        try:
            clean = clean_title(query, library_type=library_type)
            session = requests.Session()
            for item in self._search(session, self._headers(api_key), clean, library_type, limit=5):
                url = self._cover_url(item.get("cover_url"))
                if url:
                    covers.append(
                        {
                            "provider": "Scrin.is",
                            "title": _clean(item.get("title")) or "Inconnu",
                            "url": url,
                        }
                    )
        except Exception as e:  # noqa: BLE001
            logging.error(self.t("covers_err").format(e))
        return covers[:5]
