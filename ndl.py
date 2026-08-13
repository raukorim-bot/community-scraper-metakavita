"""NDL Search (国立国会図書館) — livres JP via OpenSearch (gratuit, sans clé)."""
from __future__ import annotations

import logging
import re
import threading
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from curl_cffi import requests

from config_manager import get_max_genres, get_max_tags
from scrapers.base import BaseScraper
from scrapers.utils import (
    attach_match_score,
    clean_title,
    get_match_accept_threshold,
    score_candidate,
)

_OPENSEARCH = "https://ndlsearch.ndl.go.jp/api/opensearch"
_PORTAL = "https://ndlsearch.ndl.go.jp"
_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "openSearch": "http://a9.com/-/spec/opensearchrss/1.0/",
}
_YEAR = re.compile(r"(1[0-9]{3}|20[0-9]{2})")
_NON_ISBN = re.compile(r"[^0-9Xx]")
_NDL_ID = re.compile(r"(?:ndl[^/]*/)?(?:books?|pid)/([a-zA-Z0-9._-]+)", re.I)


def _norm_isbn(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    c = _NON_ISBN.sub("", str(raw)).upper()
    return c if len(c) in (10, 13) else None


def _isbn_equal(a: Optional[str], b: Optional[str]) -> bool:
    """Compare ISBN-10 / ISBN-13 (978…) without requiring exact string match."""
    x, y = _norm_isbn(a), _norm_isbn(b)
    if not x or not y:
        return False
    if x == y:
        return True
    # 978 + ISBN-10 (sans check digit recompute : compare core 9 digits)
    if len(x) == 13 and x.startswith("978") and len(y) == 10:
        return x[3:12] == y[:9]
    if len(y) == 13 and y.startswith("978") and len(x) == 10:
        return y[3:12] == x[:9]
    return False


def _text(el: Optional[ET.Element]) -> str:
    if el is None or el.text is None:
        return ""
    return (el.text or "").strip()


def _texts(parent: ET.Element, path: str) -> List[str]:
    out = []
    for el in parent.findall(path, _NS):
        t = _text(el)
        if t:
            out.append(t)
    return out


# --- Cadence des requêtes (repli de compatibilité) ---------------------------
# `BaseScraper._http_get` applique le `rate_limit` du scraper AVANT CHAQUE
# requête. Sans lui, la cadence n'est honorée qu'une fois par `fetch()`, par
# l'appelant, et les requêtes émises À L'INTÉRIEUR partent en rafale : c'est ce
# profil de trafic qui fait bannir une IP sur un site sans API. Ce helper est
# récent, et un scraper du catalogue peut être installé sur une image MetaKavita
# antérieure où l'appeler lèverait `AttributeError` à l'exécution. On sonde donc
# sa présence à chaque appel et, quand il manque, on refait son travail ici :
# aucun chemin ne doit pouvoir émettre une requête non cadencée.
_LAST_CALL: dict = {}
_LAST_CALL_LOCK = threading.Lock()


def _throttle_fallback(scraper) -> None:
    """Attend le solde du `rate_limit` sur les images sans `_http_get`.

    `services.provider_throttle` est privilégié quand il existe : c'est
    l'horloge que partagent tous les chemins de l'application (enrichissement,
    recherche de couvertures, diagnostic), et tenir un compteur séparé
    reviendrait à autoriser deux fois la cadence sur le même fournisseur. Le
    compteur local ci-dessous n'est qu'un dernier recours, pour une image qui
    n'aurait même pas ce module.
    """
    try:
        from services.provider_throttle import throttle_provider
    except Exception:
        pass
    else:
        throttle_provider(scraper)
        return

    delay = float(getattr(scraper, "rate_limit", 1.0) or 0.0)
    key = getattr(scraper, "id", "") or scraper.__class__.__name__
    with _LAST_CALL_LOCK:
        last = _LAST_CALL.get(key)
        now = time.monotonic()
        if last is not None and now - last < delay:
            time.sleep(delay - (now - last))
        _LAST_CALL[key] = time.monotonic()


def _throttled_get(scraper, client, url: str, **kwargs):
    """GET cadencé : `BaseScraper._http_get` s'il existe, repli explicite sinon."""
    helper = getattr(scraper, "_http_get", None)
    if callable(helper):
        return helper(client, url, **kwargs)
    _throttle_fallback(scraper)
    kwargs.setdefault("timeout", getattr(scraper, "http_timeout", 20.0))
    return client.get(url, **kwargs)


class NdlScraper(BaseScraper):
    id = "NDL"
    display_name = "NDL Search (JP)"
    supported_types = {"Book"}
    # 1.1.0 : `_search` est appelé plusieurs fois par `fetch()` (ISBN puis titre)
    # et ne payait la cadence qu'une fois. Toutes y passent désormais.
    version = "1.1.0"
    rate_limit = 1.2
    proxy_domains = [
        "ndl.go.jp",
        "ndlsearch.ndl.go.jp",
        "dl.ndl.go.jp",
        "www.ndl.go.jp",
    ]
    has_direct_id_support = True
    needs_api_key = False
    uses_unified_scoring = True

    translations = {
        "fr": {
            "search_title": "🔍 [NDL] Recherche pour '{0}'…",
            "search_isbn": "🔎 [NDL] ISBN {0}…",
            "direct_id": "🎯 [NDL] id={0}",
            "no_match": "⚠️ [NDL] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [NDL] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [NDL] Erreur : {0}",
            "covers_err": "❌ [Covers] NDL : pas de covers natives fiables",
        },
        "en": {
            "search_title": "🔍 [NDL] Searching for '{0}'…",
            "search_isbn": "🔎 [NDL] ISBN {0}…",
            "direct_id": "🎯 [NDL] id={0}",
            "no_match": "⚠️ [NDL] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [NDL] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [NDL] Error: {0}",
            "covers_err": "❌ [Covers] NDL: no reliable native covers",
        },
    }

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        raw = url.strip()
        if raw.isdigit() or re.match(r"^[a-zA-Z0-9._-]+$", raw):
            if "://" not in raw and "/" not in raw:
                return raw
        m = _NDL_ID.search(urlparse(raw).path if "://" in raw else raw)
        return m.group(1) if m else None

    def fetch(
        self,
        query: str,
        library_type: str = "Book",
        is_id: bool = False,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            if is_id:
                nid = self.extract_id_from_url(query) or query.strip()
                logging.info(self.t("direct_id").format(nid))
                items = self._search(params={"dpid": nid, "cnt": 5})
                if not items:
                    items = self._search(params={"any": nid, "cnt": 5})
                for it in items:
                    cand = self._item_to_cand(it)
                    if cand:
                        return attach_match_score(cand, 1.0)
                return None

            existing_isbn = _norm_isbn((existing_metadata or {}).get("isbn"))
            cleaned = clean_title(query, library_type=library_type)
            if existing_isbn:
                logging.info(self.t("search_isbn").format(existing_isbn))
                items = self._search(params={"isbn": existing_isbn, "cnt": 5})
                for it in items:
                    cand = self._item_to_cand(it)
                    if not cand:
                        continue
                    if _isbn_equal(cand.get("isbn"), existing_isbn) or not cand.get("isbn"):
                        cand["isbn"] = existing_isbn
                        return attach_match_score(cand, 1.0)
                # ISBN query NDL a renvoyé des notices : prendre la 1re livre
                for it in items:
                    cand = self._item_to_cand(it)
                    if not cand:
                        continue
                    cats = " ".join(cand.get("_categories") or [])
                    if "記事" in cats:
                        continue
                    cand["isbn"] = existing_isbn
                    cand.pop("_categories", None)
                    return attach_match_score(cand, 1.0)

            if not cleaned:
                return None
            logging.info(self.t("search_title").format(cleaned))
            # Combiner title / any ; filtrer articles (記事)
            items = self._search(params={"title": cleaned, "cnt": 15})
            if not items:
                items = self._search(params={"any": cleaned, "cnt": 15})
            best, best_score = None, -1.0
            for it in items:
                cand = self._item_to_cand(it)
                if not cand or not cand.get("title"):
                    continue
                score = score_candidate(cand, cleaned, existing_metadata)
                cats = " ".join(cand.get("_categories") or [])
                if "記事" in cats or "article" in cats.casefold():
                    score -= 0.35
                if "図書" in cats or "book" in cats.casefold():
                    score = min(1.0, score + 0.08)
                # Titre contient la requête (JP exact / contient)
                if cleaned in (cand.get("title") or ""):
                    score = min(1.0, score + 0.25)
                if score > best_score:
                    best_score, best = score, cand
            if best:
                best.pop("_categories", None)
            if not best or best_score < get_match_accept_threshold():
                logging.warning(
                    self.t("no_match").format(cleaned, int(max(best_score, 0) * 100))
                )
                return None
            logging.info(self.t("matched").format(best.get("title"), int(best_score * 100)))
            return attach_match_score(best, best_score)
        except Exception as e:
            logging.error(self.t("err").format(e))
            return None

    def fetch_covers(self, query: str, library_type: str = "Book") -> List[Dict[str, str]]:
        return []

    def _search(self, params: Dict[str, Any]) -> List[ET.Element]:
        res = _throttled_get(
            self,
            requests,
            _OPENSEARCH,
            params=params,
            timeout=25,
            headers={"Accept": "application/xml, application/rss+xml, */*"},
        )
        if res.status_code != 200:
            return []
        try:
            root = ET.fromstring(res.content)
        except ET.ParseError:
            return []
        # RSS item or Atom entry
        items = root.findall(".//item")
        if not items:
            items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
        return items

    def _item_to_cand(self, item: ET.Element) -> Optional[Dict[str, Any]]:
        # Prefer dc:title
        titles = _texts(item, "dc:title")
        if not titles:
            titles = [_text(item.find("title")) or _text(item.find("atom:title", _NS))]
        titles = [t for t in titles if t]
        if not titles:
            return None
        title = titles[0]
        creators = _texts(item, "dc:creator")
        if not creators:
            creators = _texts(item, "author") or _texts(item, "atom:author/atom:name")
        staff = [
            {"role": "Story", "node": {"name": {"full": n}}} for n in creators[:5]
        ]
        year = None
        for d in _texts(item, "dc:date") + _texts(item, "dcterms:issued"):
            m = _YEAR.search(d)
            if m:
                year = int(m.group(1))
                break
        isbn = None
        for ident in _texts(item, "dc:identifier"):
            n = _norm_isbn(ident)
            if n:
                isbn = n
                break
        subjects = _texts(item, "dc:subject")
        publishers = _texts(item, "dc:publisher")
        descriptions = _texts(item, "dc:description") + _texts(item, "description")
        categories = [c for c in _texts(item, "category") if c]
        # RSS category without namespace
        for el in item.findall("category"):
            t = _text(el)
            if t and t not in categories:
                categories.append(t)
        link = None
        link_el = item.find("link")
        if link_el is not None:
            link = (link_el.get("href") or link_el.text or "").strip() or None
        if not link:
            id_el = item.find("guid") or item.find("atom:id", _NS)
            link = _text(id_el) or None
        if link and not link.startswith("http"):
            link = f"{_PORTAL}/{link.lstrip('/')}"
        return {
            "title": title,
            "alternative_titles": titles[1:4],
            "summary": "\n\n".join(descriptions),
            "cover_url": None,
            "genres": (subjects[: get_max_genres()] if subjects else ["Book"]),
            "tags": subjects[get_max_genres() : get_max_genres() + get_max_tags()],
            "year": year,
            "staff": staff,
            "publisher": publishers[0] if publishers else None,
            "format": "book",
            "url": link,
            "links": [link] if link else [],
            "isbn": isbn,
            "_categories": categories,
        }
