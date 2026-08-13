"""Library of Congress — livres EN via API JSON publique loc.gov (sans clé)."""
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

_SEARCH = "https://www.loc.gov/books/"
_SRU = "http://lx2.loc.gov:210/LCDB"
_YEAR = re.compile(r"(1[0-9]{3}|20[0-9]{2})")
_NON_ISBN = re.compile(r"[^0-9Xx]")
_LCCN = re.compile(r"(?:lccn[:\s/]+)?([a-z]{0,3}\d{2,8})", re.I)
_CREATOR_URI = re.compile(r"\s*https?://\S+", re.I)
_SOUND_TYPE = re.compile(r"sound\s*recording|audio|spoken", re.I)
_TEXT_TYPE = re.compile(r"\btext\b|book|fiction|manuscript", re.I)


def _clean_creator(raw: str) -> str:
    name = _CREATOR_URI.sub("", raw or "")
    name = re.sub(r"\s+(author|aut|edt|ed|trl|ill)\b.*$", "", name, flags=re.I)
    name = re.sub(r",\s*\d{4}\s*[-–—]?\s*\d{0,4}\.?\s*$", "", name)
    return name.strip(" .,;")


def _hit_richness(hit: dict) -> int:
    score = 0
    types = hit.get("types") or []
    joined = " ".join(str(t) for t in types)
    if _TEXT_TYPE.search(joined):
        score += 6
    if _SOUND_TYPE.search(joined):
        score -= 8
    if hit.get("contributor"):
        score += 3
    if hit.get("date"):
        score += 2
    if hit.get("subject"):
        score += 1
    if hit.get("number_isbn") or hit.get("url"):
        score += 1
    if hit.get("description"):
        score += 1
    return score


def _norm_isbn(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    c = _NON_ISBN.sub("", str(raw)).upper()
    return c if len(c) in (10, 13) else None


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


class LocScraper(BaseScraper):
    id = "LOC"
    display_name = "Library of Congress"
    supported_types = {"Book"}
    # 1.1.0 : `_search_sru` enchaîne jusqu'à trois formulations de la requête,
    # puis `_search` retombe sur le JSON loc.gov — quatre requêtes possibles qui
    # ne payaient la cadence qu'une fois. Toutes y passent désormais, ce qui
    # compte d'autant plus que loc.gov coupe à 20 requêtes par minute.
    version = "1.1.0"
    rate_limit = 3.4  # ~17.6/min: 10% under loc.gov JSON 20/min
    proxy_domains = [
        "loc.gov",
        "www.loc.gov",
        "tile.loc.gov",
        "cover.loc.gov",
    ]
    has_direct_id_support = True
    needs_api_key = False
    uses_unified_scoring = True

    translations = {
        "fr": {
            "search_title": "🔍 [LoC] Recherche pour '{0}'…",
            "search_isbn": "🔎 [LoC] ISBN {0}…",
            "direct_id": "🎯 [LoC] id={0}",
            "no_match": "⚠️ [LoC] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [LoC] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [LoC] Erreur : {0}",
            "covers_err": "❌ [Covers] LoC : {0}",
        },
        "en": {
            "search_title": "🔍 [LoC] Searching for '{0}'…",
            "search_isbn": "🔎 [LoC] ISBN {0}…",
            "direct_id": "🎯 [LoC] id={0}",
            "no_match": "⚠️ [LoC] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [LoC] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [LoC] Error: {0}",
            "covers_err": "❌ [Covers] LoC: {0}",
        },
    }

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        raw = url.strip()
        if re.fullmatch(r"[a-z]{0,3}\d{2,10}", raw, re.I):
            return raw
        path = urlparse(raw).path if "://" in raw else raw
        m = re.search(r"/item/([^/]+)/?", path)
        if m:
            return m.group(1)
        m = _LCCN.search(raw)
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
                lid = self.extract_id_from_url(query) or query.strip()
                logging.info(self.t("direct_id").format(lid))
                results = self._search(lid, count=5)
                for hit in results:
                    cand = self._hit_to_cand(hit)
                    if cand:
                        return attach_match_score(cand, 1.0)
                return None

            existing_isbn = _norm_isbn((existing_metadata or {}).get("isbn"))
            cleaned = clean_title(query, library_type=library_type)
            if existing_isbn:
                logging.info(self.t("search_isbn").format(existing_isbn))
                for hit in self._search(existing_isbn, count=5):
                    cand = self._hit_to_cand(hit)
                    if cand and _norm_isbn(cand.get("isbn")) == existing_isbn:
                        return attach_match_score(cand, 1.0)

            if not cleaned:
                return None
            logging.info(self.t("search_title").format(cleaned))
            best, best_score = None, -1.0
            soft = re.sub(r"^(the|a|an)\s+", "", cleaned, flags=re.I).strip() or cleaned
            tokens = [t for t in soft.split() if len(t) > 3]
            variants: List[str] = []
            authors = (existing_metadata or {}).get("authors") or []
            if authors and isinstance(authors[0], str) and authors[0].strip():
                last = authors[0].strip().split()[-1]
                if tokens:
                    variants.append(f"{tokens[-1]} {last}")
                variants.append(f"{soft} {last}")
            variants.extend([cleaned, soft])
            if tokens:
                variants.append(tokens[-1])
            seen_v: set = set()
            ordered: List[str] = []
            for v in variants:
                key = v.casefold().strip()
                if not key or key in seen_v:
                    continue
                seen_v.add(key)
                ordered.append(v.strip())
            for v in ordered:
                for hit in self._search(v, count=5):
                    cand = self._hit_to_cand(hit)
                    if not cand or not cand.get("title"):
                        continue
                    score = score_candidate(cand, cleaned, existing_metadata)
                    for tok in tokens:
                        if tok.casefold() in (cand.get("title") or "").casefold():
                            score = min(1.0, score + 0.15)
                    # Préférer notices textuelles riches (auteur / année) vs audio orphelins
                    if cand.get("staff"):
                        score = min(1.0, score + 0.08)
                    if cand.get("year"):
                        score = min(1.0, score + 0.05)
                    if score > best_score:
                        best_score, best = score, cand
                if best_score >= 0.95:
                    break
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
        covers: List[Dict[str, str]] = []
        cleaned = clean_title(query, library_type=library_type) or query
        try:
            for hit in self._search(cleaned, count=5):
                cand = self._hit_to_cand(hit)
                if cand and cand.get("cover_url"):
                    covers.append(
                        {
                            "provider": self.display_name,
                            "title": cand.get("title") or cleaned,
                            "url": cand["cover_url"],
                        }
                    )
        except Exception as e:
            logging.error(self.t("covers_err").format(e))
        return covers

    def _search(self, q: str, count: int = 10) -> List[dict]:
        # SRU d'abord (stable) — JSON loc.gov souvent CF ou résultats hors-sujet
        sru = self._search_sru(q, count)
        if sru:
            return sru

        # Fallback JSON
        try:
            res = _throttled_get(
                self,
                requests,
                _SEARCH,
                params={"q": q, "fo": "json", "c": str(max(1, min(count, 25)))},
                timeout=25,
                headers={
                    "Accept": "application/json",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            if res.status_code == 200 and (res.text or "").lstrip().startswith("{"):
                data = res.json()
                results = data.get("results") if isinstance(data, dict) else None
                if isinstance(results, list) and results:
                    return results
        except Exception:
            pass
        return []

    def _search_sru(self, q: str, count: int) -> List[dict]:
        queries: List[str] = []
        # Requête libre (l'index title= n'est pas supporté par LCDB)
        if (q or "").strip():
            queries.append(q.strip())
            if " " in q.strip():
                queries.append(f'"{q.strip()}"')
        soft = re.sub(r"^(the|a|an)\s+", "", (q or "").strip(), flags=re.I)
        if soft and soft.casefold() != (q or "").strip().casefold():
            queries.append(soft)

        best_batch: List[dict] = []
        for cql in queries:
            try:
                res = _throttled_get(
                    self,
                    requests,
                    _SRU,
                    params={
                        "version": "1.1",
                        "operation": "searchRetrieve",
                        "query": cql,
                        "maximumRecords": str(max(1, min(max(count, 10), 25))),
                        "recordSchema": "dc",
                    },
                    timeout=25,
                    headers={"Accept": "application/xml"},
                )
            except Exception:
                continue
            if res.status_code != 200:
                continue
            try:
                root = ET.fromstring(res.content)
            except ET.ParseError:
                continue
            batch: List[dict] = []
            for rd in root.findall(".//{http://www.loc.gov/zing/srw/}recordData"):
                titles, creators, dates, idents = [], [], [], []
                subjects, types, descriptions = [], [], []
                for el in rd.iter():
                    tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
                    t = (el.text or "").strip()
                    if not t:
                        continue
                    if tag == "title":
                        titles.append(t)
                    elif tag in {"creator", "contributor"}:
                        creators.append(t)
                    elif tag == "date":
                        dates.append(t)
                    elif tag == "identifier":
                        idents.append(t)
                    elif tag == "subject":
                        subjects.append(t)
                    elif tag == "type":
                        types.append(t)
                    elif tag == "description":
                        # ignorer bruit MARC legacy
                        if "marc record derived" in t.casefold():
                            continue
                        descriptions.append(t)
                if not titles:
                    continue
                year = None
                for d in dates:
                    m = _YEAR.search(d)
                    if m:
                        year = int(m.group(1))
                        break
                isbn = None
                url = None
                for ident in idents:
                    if not isbn:
                        isbn = _norm_isbn(ident)
                    if ident.startswith("http") and ("loc.gov" in ident or "lccn" in ident):
                        url = ident
                    elif not url:
                        m = re.search(r"(?:lccn[:\s]+)?([a-z]{0,3}\d{2,10})", ident, re.I)
                        if m and "loc.gov" not in ident.casefold():
                            # avoid treating random tokens as LCCN unless labeled
                            if "lccn" in ident.casefold():
                                url = f"https://lccn.loc.gov/{m.group(1)}"
                summary = ""
                for d in descriptions:
                    if len(d) > len(summary) and len(d) > 20:
                        summary = d
                batch.append(
                    {
                        "title": titles[0],
                        "contributor": creators,
                        "date": dates[0] if dates else year,
                        "number_isbn": isbn,
                        "url": url,
                        "subject": subjects,
                        "types": types,
                        "description": summary,
                    }
                )
            if not batch:
                continue
            batch.sort(key=_hit_richness, reverse=True)
            # garder le meilleur lot (ex. "Moby Dick Melville" > "Moby Dick" audio)
            if not best_batch or _hit_richness(batch[0]) > _hit_richness(best_batch[0]):
                best_batch = batch
            if _hit_richness(best_batch[0]) >= 8:
                break
        return best_batch[:count]

    def _hit_to_cand(self, hit: dict) -> Optional[Dict[str, Any]]:
        if not isinstance(hit, dict):
            return None
        title = hit.get("title") or hit.get("item", {}).get("title")
        if isinstance(title, list):
            title = title[0] if title else None
        if not title:
            return None
        title = str(title).strip()
        # "Moby Dick ; Moby Dick" → première partie
        if " ; " in title:
            left, right = title.split(" ; ", 1)
            if left.strip().casefold() == right.strip().casefold():
                title = left.strip()
        authors = hit.get("contributor") or hit.get("item", {}).get("contributors") or []
        if isinstance(authors, str):
            authors = [authors]
        staff = []
        for a in authors[:5]:
            name = a if isinstance(a, str) else (a.get("title") or a.get("name") if isinstance(a, dict) else None)
            if name:
                cleaned = _clean_creator(str(name))
                if cleaned:
                    staff.append({"role": "Story", "node": {"name": {"full": cleaned}}})
        year = None
        for key in ("date", "dates", "item"):
            raw = hit.get(key)
            if isinstance(raw, dict):
                raw = raw.get("date") or raw.get("dates")
            if isinstance(raw, list):
                raw = " ".join(str(x) for x in raw)
            if raw:
                m = _YEAR.search(str(raw))
                if m:
                    year = int(m.group(1))
                    break
        isbn = None
        for key in ("number_isbn", "isbn", "shelf_id"):
            val = hit.get(key)
            if isinstance(val, list):
                for v in val:
                    isbn = _norm_isbn(str(v))
                    if isbn:
                        break
            else:
                isbn = _norm_isbn(str(val) if val else None)
            if isbn:
                break
        subjects = hit.get("subject") or hit.get("subjects") or []
        if isinstance(subjects, str):
            subjects = [subjects]
        # nettoyer suffixes authority
        cleaned_subj = []
        for s in subjects:
            s = re.sub(r"\s+https?://\S+", "", str(s)).strip()
            s = re.sub(r"\s+(lcsh|lcgft|gsafd)\.?$", "", s, flags=re.I).strip(" .")
            if s:
                cleaned_subj.append(s)
        subjects = cleaned_subj[: get_max_genres() + get_max_tags()]
        url = hit.get("url") or hit.get("id") or hit.get("aka")
        if isinstance(url, list):
            url = url[0] if url else None
        if url and not str(url).startswith("http"):
            url = f"https://www.loc.gov{url}" if str(url).startswith("/") else None
        cover = None
        image_url = hit.get("image_url") or hit.get("resources")
        if isinstance(image_url, list) and image_url:
            cover = image_url[0] if isinstance(image_url[0], str) else None
        elif isinstance(image_url, str):
            cover = image_url
        summary = hit.get("description") or hit.get("summary") or ""
        if not isinstance(summary, str):
            summary = ""
        return {
            "title": title,
            "alternative_titles": [],
            "summary": summary,
            "cover_url": cover,
            "genres": subjects[: get_max_genres()] if subjects else ["Book"],
            "tags": subjects[get_max_genres() : get_max_genres() + get_max_tags()],
            "year": year,
            "staff": staff,
            "format": "book",
            "url": url,
            "links": [url] if url else [],
            "isbn": isbn,
        }
