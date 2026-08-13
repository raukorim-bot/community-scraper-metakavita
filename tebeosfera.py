"""Tebeosfera — comics / tebeos ES (HTML, best-effort)."""
from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin, urlparse

from bs4 import BeautifulSoup
from curl_cffi import requests

from config_manager import get_max_genres, get_max_tags
from scrapers.base import BaseScraper
from scrapers.utils import (
    attach_match_score,
    clean_title,
    get_match_accept_threshold,
    score_candidate,
)

_BASE = "https://www.tebeosfera.com"
_YEAR = re.compile(r"(1[0-9]{3}|20[0-9]{2})")


def _abs(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    return urljoin(_BASE, url.split("#", 1)[0])


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


def _throttled_post(scraper, client, url: str, **kwargs):
    """POST cadencé, même contrat que `_throttled_get`."""
    helper = getattr(scraper, "_http_post", None)
    if callable(helper):
        return helper(client, url, **kwargs)
    _throttle_fallback(scraper)
    kwargs.setdefault("timeout", getattr(scraper, "http_timeout", 20.0))
    return client.post(url, **kwargs)


class TebeosferaScraper(BaseScraper):
    id = "TEBEOSFERA"
    display_name = "Tebeosfera"
    supported_types = {"Comic"}
    # 1.1.0 : toutes les requêtes passent par la cadence. `_search` en essaie
    # jusqu'à cinq d'affilée pour trouver le bon point d'entrée du moteur du
    # site : c'était la rafale la plus brutale du catalogue.
    version = "1.1.0"
    rate_limit = 3.0  # HTML ES — anti-ban IP
    proxy_domains = ["tebeosfera.com", "www.tebeosfera.com"]
    has_direct_id_support = True
    needs_api_key = False
    uses_unified_scoring = True

    translations = {
        "fr": {
            "search_title": "🔍 [Tebeosfera] Recherche pour '{0}'…",
            "direct_id": "🎯 [Tebeosfera] path={0}",
            "no_match": "⚠️ [Tebeosfera] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [Tebeosfera] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [Tebeosfera] Erreur : {0}",
            "covers_err": "❌ [Covers] Tebeosfera : {0}",
        },
        "en": {
            "search_title": "🔍 [Tebeosfera] Searching for '{0}'…",
            "direct_id": "🎯 [Tebeosfera] path={0}",
            "no_match": "⚠️ [Tebeosfera] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [Tebeosfera] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [Tebeosfera] Error: {0}",
            "covers_err": "❌ [Covers] Tebeosfera: {0}",
        },
    }

    def __init__(self) -> None:
        self._session = requests.Session(impersonate="chrome110")
        self._session.headers.update(
            {
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.5",
                "Referer": f"{_BASE}/",
            }
        )

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url:
            return None
        raw = url.strip()
        if raw.startswith("/") and "tebeosfera" not in raw:
            return raw
        path = urlparse(raw).path if "://" in raw else raw
        if "/obras/" in path or "/numeros/" in path or "/autores/" in path:
            return path
        return None

    def fetch(
        self,
        query: str,
        library_type: str = "Comic",
        is_id: bool = False,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            if is_id:
                path = self.extract_id_from_url(query) or query.strip()
                logging.info(self.t("direct_id").format(path))
                cand = self._parse_detail(_abs(path) or f"{_BASE}{path}")
                return attach_match_score(cand, 1.0) if cand else None

            cleaned = clean_title(query, library_type=library_type)
            if not cleaned:
                return None
            logging.info(self.t("search_title").format(cleaned))
            hits = self._search(cleaned)
            best, best_score = None, -1.0
            for hit in hits[:8]:
                seed = self._hit_to_cand(hit)
                if not seed:
                    continue
                score = score_candidate(seed, cleaned, existing_metadata)
                detail = None
                if score >= get_match_accept_threshold() - 0.15 and hit.get("url"):
                    detail = self._parse_detail(hit["url"])
                cand = detail or seed
                score = score_candidate(cand, cleaned, existing_metadata)
                if score > best_score:
                    best_score, best = score, cand
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

    def fetch_covers(self, query: str, library_type: str = "Comic") -> List[Dict[str, str]]:
        covers: List[Dict[str, str]] = []
        cleaned = clean_title(query, library_type=library_type)
        if not cleaned:
            return covers
        try:
            for hit in self._search(cleaned)[:6]:
                url = hit.get("cover")
                if url:
                    covers.append(
                        {
                            "provider": self.display_name,
                            "title": hit.get("title") or cleaned,
                            "url": url,
                        }
                    )
        except Exception as e:
            logging.error(self.t("covers_err").format(e))
        return covers

    def _search(self, terms: str) -> List[dict]:
        """Recherche best-effort.

        Le buscador Tebeosfera est majoritairement JS (`preventDefault` + AJAX).
        On tente GET/POST HTML et on filtre les bannières promo / nav qui
        polluaient les covers (liens /numeros/ hors-sujet).
        """
        qcf = (terms or "").casefold().strip()
        # Requêtes HTTP à essayer (GET url) ou (POST url, data)
        attempts = [
            ("POST", f"{_BASE}/buscador/", {"busqueda": terms, "tabla_especifica": "obras"}),
            ("POST", f"{_BASE}/buscador/", {"busqueda": terms}),
            ("GET", f"{_BASE}/buscador/?texto={quote_plus(terms)}", None),
            ("GET", f"{_BASE}/catalogos/obras/?q={quote_plus(terms)}", None),
            ("GET", f"{_BASE}/busqueda/?q={quote_plus(terms)}", None),
        ]
        promo_markers = (
            "nueva catalogación",
            "novedad de acyt",
            "teoría sobre tebeos",
            "hemos catalogado",
            "números",
            "tebeos de hoy",
        )
        out: List[dict] = []
        seen = set()
        for method, url, data in attempts:
            try:
                if method == "POST":
                    res = _throttled_post(self, self._session, url, data=data or {}, timeout=25)
                else:
                    res = _throttled_get(self, self._session, url, timeout=25)
            except Exception:
                continue
            if res.status_code != 200 or len(res.text) < 500:
                continue
            if "just a moment" in res.text.casefold():
                continue
            soup = BeautifulSoup(res.text, "html.parser")
            batch: List[dict] = []
            for a in soup.select("a[href*='/obras/'], a[href*='/numeros/']"):
                href = _abs(a.get("href"))
                if not href or href in seen:
                    continue
                # Ignorer index /numeros/ seul
                path = urlparse(href).path.rstrip("/")
                if path in {"/numeros", "/obras"}:
                    continue
                title = a.get_text(" ", strip=True)
                if not title or len(title) < 2:
                    continue
                tcf = title.casefold()
                if any(p in tcf for p in promo_markers):
                    continue
                # Exiger un ancrage minimal sur la requête (évite les sidebars)
                if qcf and qcf not in tcf and not any(
                    tok and tok in tcf for tok in qcf.split() if len(tok) >= 4
                ):
                    continue
                seen.add(href)
                img = a.find("img")
                cover = None
                if img:
                    cover = _abs(img.get("data-src") or img.get("src"))
                batch.append({"title": title, "url": href, "cover": cover})
            if batch:
                out.extend(batch)
                break
        return out

    def _hit_to_cand(self, hit: dict) -> Optional[Dict[str, Any]]:
        title = hit.get("title")
        if not title:
            return None
        url = hit.get("url")
        return {
            "title": title,
            "alternative_titles": [],
            "summary": "",
            "cover_url": hit.get("cover"),
            "genres": ["Comic"][: get_max_genres()],
            "tags": [],
            "year": None,
            "staff": [],
            "format": "comic",
            "url": url,
            "links": [url] if url else [],
        }

    def _parse_detail(self, url: str) -> Optional[Dict[str, Any]]:
        res = _throttled_get(self, self._session, url, timeout=25)
        if res.status_code != 200:
            return None
        soup = BeautifulSoup(res.text, "html.parser")
        title = None
        h1 = soup.select_one("h1")
        if h1:
            title = h1.get_text(" ", strip=True)
        if not title and soup.title:
            title = soup.title.get_text(" ", strip=True).split("|")[0].strip()
        if not title:
            return None
        summary = ""
        for sel in (".sinopsis", ".resumen", ".descripcion", "meta[name='description']"):
            el = soup.select_one(sel)
            if not el:
                continue
            summary = (
                el.get("content") if el.name == "meta" else el.get_text(" ", strip=True)
            ) or ""
            if summary:
                break
        year = None
        blob = soup.get_text(" ", strip=True)[:2000]
        m = _YEAR.search(blob)
        if m:
            year = int(m.group(1))
        cover = None
        og = soup.select_one('meta[property="og:image"]')
        if og and og.get("content"):
            cover = _abs(og["content"])
        if not cover:
            img = soup.select_one("article img, .portada img, .cover img, img")
            if img:
                cover = _abs(img.get("data-src") or img.get("src"))
        staff = []
        for sel in (".autor a", ".autores a", "a[href*='/autores/']"):
            for a in soup.select(sel)[:5]:
                name = a.get_text(" ", strip=True)
                if name:
                    staff.append({"role": "Story", "node": {"name": {"full": name}}})
            if staff:
                break
        return {
            "title": title,
            "alternative_titles": [],
            "summary": summary,
            "cover_url": cover,
            "genres": ["Comic"][: get_max_genres()],
            "tags": [],
            "year": year,
            "staff": staff,
            "format": "comic",
            "url": url,
            "links": [url],
        }
