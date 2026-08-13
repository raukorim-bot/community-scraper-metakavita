"""Deutsche Nationalbibliothek (DNB) — SRU MARC21, gratuit, sans clé API."""
from __future__ import annotations

import html
import logging
import re
import threading
import time
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from curl_cffi import requests

from config_manager import get_max_genres, get_max_tags
from scrapers.base import BaseScraper
from scrapers.utils import (
    attach_match_score,
    clean_title,
    get_match_accept_threshold,
    score_candidate,
)

_SRU = "https://services.dnb.de/sru/dnb"
_PORTAL = "https://d-nb.info"
_NS = {
    "srw": "http://www.loc.gov/zing/srw/",
    "marc": "http://www.loc.gov/MARC21/slim",
}

# MARC non-sorting article markers (NSB/NSE)
_MARC_NS = re.compile(r"[\x98\x9c\x88\x89]")
_NON_ISBN = re.compile(r"[^0-9Xx]")
_YEAR = re.compile(r"(1[0-9]{3}|20[0-9]{2})")
_IDN = re.compile(r"^\d{7,12}$")

# Rôles MARC $4 à garder comme auteurs principaux
_AUTHOR_CODES = {"aut", "aui", "lyr", "cmp"}

# Formes / supports à écarter pour une bibliothèque Book Kavita
_COMIC_HINTS = re.compile(
    r"\b(comic|comics|cartoon|graphic\s*novel|manga|bildgeschichte)\b",
    re.I,
)
_AUDIO_HINTS = re.compile(
    r"(gesprochenes\s+wort|hörbuch|hoerbuch|audiobook|tonträger|tontraeger)",
    re.I,
)
_ONLINE_HINTS = re.compile(
    r"(online[\s-]?ressource|computermedien|ebook|e-book)",
    re.I,
)
_SECONDARY_HINTS = re.compile(
    r"(kommentar|interpretation|analyse|unterricht|skript|abschlussarbeit|"
    r"dissertation|examen|leitmotiv|gestaltungs?|anthropomorph)",
    re.I,
)


def _normalize_isbn(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    cleaned = _NON_ISBN.sub("", str(raw)).upper()
    if len(cleaned) in (10, 13):
        return cleaned
    return None


def _clean_marc_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = _MARC_NS.sub("", text)
    # Articles allemands souvent encadrés : «Der» → Der
    text = text.replace("\u0098", "").replace("\u009c", "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip(" .,;:/")


def _current_pub_year() -> int:
    return date.today().year


def _edition_adjustments(
    candidate: Dict[str, Any], query: str
) -> Tuple[float, List[str]]:
    """Ajustements de score DNB (éditions futures, comics, audio, online…).

    Retourne (delta, raisons) — delta typiquement négatif pour écarter le bruit.
    """
    delta = 0.0
    reasons: List[str] = []
    title = candidate.get("title") or ""
    year = candidate.get("year")
    carrier = candidate.get("_carrier") or "print"
    is_comic = bool(candidate.get("_is_comic"))
    genres_blob = " ".join(candidate.get("genres") or [])
    blob = f"{title} {genres_blob}"

    now = _current_pub_year()
    if isinstance(year, int) and year > now:
        # Catalogage anticipé (ex. Faust 2050, Prozess 2027)
        delta -= 0.40
        reasons.append(f"future_year:{year}")

    if is_comic or _COMIC_HINTS.search(blob):
        delta -= 0.50
        reasons.append("comic_form")

    if carrier == "audio" or _AUDIO_HINTS.search(blob):
        delta -= 0.45
        reasons.append("audio")
    elif carrier == "online" or _ONLINE_HINTS.search(blob):
        delta -= 0.18
        reasons.append("online")

    if _SECONDARY_HINTS.search(title) and query.casefold() not in title.casefold()[: len(query) + 5]:
        # Titres académiques « … in Der Hobbit » : déjà mal scorés, petit coup de pouce
        delta -= 0.10
        reasons.append("secondary_lit")

    # Bonus titre exact (éditions « Der Prozess » vs « Der Prozess der … »)
    t_norm = re.sub(r"\s+", " ", title).strip().casefold()
    q_norm = re.sub(r"\s+", " ", query).strip().casefold()
    if t_norm == q_norm:
        delta += 0.08
        reasons.append("exact_title")
    elif t_norm.startswith(q_norm + " ") or t_norm.startswith(q_norm + ":"):
        # « Der Hobbit oder … » reste un vrai roman, léger bonus vs graphic novel
        if not _COMIC_HINTS.search(title):
            delta += 0.04
            reasons.append("title_prefix")

    # Préférer les éditions plus anciennes (rééditions courantes DNB = année en cours)
    if isinstance(year, int) and year >= now - 1:
        delta -= 0.06
        reasons.append(f"recent_reprint:{year}")
    elif isinstance(year, int) and year < now - 30:
        delta += 0.03
        reasons.append("older_edition")

    return delta, reasons


def _invert_author(name: str) -> str:
    """'Kafka, Franz' → 'Franz Kafka' ; laisse inchangé si pas de virgule."""
    name = _clean_marc_text(name)
    if "," not in name:
        return name
    last, first = name.split(",", 1)
    first = first.strip()
    last = last.strip()
    return f"{first} {last}".strip() if first else last


def _cql_quote(term: str) -> str:
    safe = term.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{safe}"'


def _subfields(datafield: ET.Element) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for sf in datafield.findall("marc:subfield", _NS):
        code = sf.get("code") or ""
        val = sf.text or ""
        out.setdefault(code, []).append(val)
    return out


def _first_sub(subs: Dict[str, List[str]], code: str) -> str:
    vals = subs.get(code) or []
    return vals[0] if vals else ""


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


class DnbScraper(BaseScraper):
    id = "DNB"
    display_name = "DNB (Deutsche Nationalbibliothek)"
    supported_types = {"Book"}
    # 1.1.0 : `_sru` est appelé plusieurs fois par `fetch()` (cascade de requêtes
    # CQL) et ne payait la cadence qu'une fois. Toutes y passent désormais.
    version = "1.1.0"
    rate_limit = 1.0  # SRU public ~60–100 req/min ; on reste poli
    proxy_domains = ["dnb.de", "services.dnb.de", "d-nb.info", "portal.dnb.de"]
    has_direct_id_support = True
    requires_proxy = False
    needs_api_key = False
    uses_unified_scoring = True

    translations = {
        "fr": {
            "direct_id": "🎯 [DNB] Requête directe IDN={0}",
            "search_isbn": "🔎 [DNB] Recherche ISBN {0}…",
            "matched_isbn": "🎯 [DNB] Match ISBN ({0}) : '{1}'",
            "search_title": "🔍 [DNB] Recherche pour '{0}'…",
            "no_match": "⚠️ [DNB] Aucun résultat pertinent pour '{0}' (Score max: {1}%)",
            "matched": "🎯 [DNB] Match validé : '{0}' (Score: {1}%)",
            "err": "❌ [DNB] Erreur : {0}",
            "covers_err": "❌ [Covers] DNB : pas de couvertures natives",
        },
        "en": {
            "direct_id": "🎯 [DNB] Direct IDN request={0}",
            "search_isbn": "🔎 [DNB] ISBN search {0}…",
            "matched_isbn": "🎯 [DNB] ISBN match ({0}): '{1}'",
            "search_title": "🔍 [DNB] Searching for '{0}'…",
            "no_match": "⚠️ [DNB] No relevant result for '{0}' (Max score: {1}%)",
            "matched": "🎯 [DNB] Match validated: '{0}' (Score: {1}%)",
            "err": "❌ [DNB] Error: {0}",
            "covers_err": "❌ [Covers] DNB: no native cover images",
        },
        "de": {
            "direct_id": "🎯 [DNB] Direkte IDN-Anfrage={0}",
            "search_isbn": "🔎 [DNB] ISBN-Suche {0}…",
            "matched_isbn": "🎯 [DNB] ISBN-Treffer ({0}): '{1}'",
            "search_title": "🔍 [DNB] Suche nach '{0}'…",
            "no_match": "⚠️ [DNB] Kein passendes Ergebnis für '{0}' (Max. Score: {1}%)",
            "matched": "🎯 [DNB] Treffer bestätigt: '{0}' (Score: {1}%)",
            "err": "❌ [DNB] Fehler: {0}",
            "covers_err": "❌ [Covers] DNB: keine Cover-Bilder",
        },
    }

    def extract_id_from_url(self, url: str) -> Optional[str]:
        if not url or not isinstance(url, str):
            return None
        url = url.strip()
        if _IDN.match(url):
            return url
        # https://d-nb.info/1395282102  |  portal.dnb.de/...idn=...
        m = re.search(r"d-nb\.info/(\d{7,12})", url)
        if m:
            return m.group(1)
        m = re.search(r"[?&]idn=(\d{7,12})", url, flags=re.I)
        if m:
            return m.group(1)
        m = re.search(r"/(\d{7,12})(?:/|$)", url)
        if m and ("dnb.de" in url or "d-nb.info" in url):
            return m.group(1)
        return None

    def fetch(
        self,
        query: str,
        library_type: str = "Book",
        is_id: bool = False,
        existing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        session = requests.Session()
        try:
            if is_id:
                idn = self.extract_id_from_url(query) or (
                    query.strip() if _IDN.match(query.strip()) else None
                )
                if not idn:
                    return None
                logging.info(self.t("direct_id").format(idn))
                records = self._sru(session, f"idn={idn}", maximum=1)
                if not records:
                    return None
                candidate = self._marc_to_candidate(records[0])
                if candidate:
                    candidate.pop("_isbns", None)
                    return attach_match_score(candidate, 1.0)
                return None

            existing_isbn = _normalize_isbn(
                (existing_metadata or {}).get("isbn") if existing_metadata else None
            )
            cleaned = clean_title(query, library_type=library_type)

            # 1) ISBN prioritaire
            if existing_isbn:
                logging.info(self.t("search_isbn").format(existing_isbn))
                records = self._sru(session, f"num={existing_isbn}", maximum=5)
                for rec in records:
                    candidate = self._marc_to_candidate(rec)
                    if not candidate:
                        continue
                    cand_isbn = _normalize_isbn(candidate.get("isbn"))
                    extras = candidate.pop("_isbns", []) or []
                    if cand_isbn == existing_isbn or existing_isbn in extras:
                        logging.info(
                            self.t("matched_isbn").format(
                                existing_isbn, candidate.get("title")
                            )
                        )
                        candidate.pop("_carrier", None)
                        candidate.pop("_is_comic", None)
                        return attach_match_score(candidate, 1.0)
                    score = score_candidate(
                        candidate, cleaned or existing_isbn, existing_metadata
                    )
                    adj, _ = _edition_adjustments(
                        candidate, cleaned or existing_isbn
                    )
                    score = max(0.0, min(1.0, round(score + adj, 2)))
                    candidate.pop("_carrier", None)
                    candidate.pop("_is_comic", None)
                    if score >= get_match_accept_threshold():
                        return attach_match_score(candidate, score)

            if not cleaned:
                return None

            logging.info(self.t("search_title").format(cleaned))
            cql = f"tit={_cql_quote(cleaned)}"
            # Ancrage auteur Kavita si dispo
            authors = (existing_metadata or {}).get("authors") or []
            if authors and isinstance(authors[0], str) and authors[0].strip():
                # atr marche mieux avec le nom de famille
                author_term = authors[0].strip()
                if "," in author_term:
                    author_term = author_term.split(",", 1)[0].strip()
                else:
                    parts = author_term.split()
                    author_term = parts[-1] if parts else author_term
                cql = f"{cql} and atr={_cql_quote(author_term)}"

            # Exclure le catalogage anticipé (années futures) — repli sans filtre
            year_cap = _current_pub_year()
            cql_capped = f"{cql} and jhr<={year_cap}"
            records = self._sru(session, cql_capped, maximum=12)
            if not records:
                records = self._sru(session, cql, maximum=12)
            if not records and " and atr=" in cql:
                # Repli sans auteur
                base = f"tit={_cql_quote(cleaned)}"
                records = self._sru(
                    session, f"{base} and jhr<={year_cap}", maximum=12
                ) or self._sru(session, base, maximum=12)
            if not records:
                return None

            best_match = None
            best_score = -1.0
            for rec in records:
                candidate = self._marc_to_candidate(rec)
                if not candidate or not candidate.get("title"):
                    continue
                candidate.pop("_isbns", None)
                score = score_candidate(candidate, cleaned, existing_metadata)
                adj, _reasons = _edition_adjustments(candidate, cleaned)
                score = max(0.0, min(1.0, round(score + adj, 2)))
                # Nettoyage flags internes avant exposition
                candidate.pop("_carrier", None)
                candidate.pop("_is_comic", None)
                if score > best_score:
                    best_score = score
                    best_match = candidate
                elif (
                    score == best_score
                    and best_match
                    and self._prefer_candidate(candidate, best_match)
                ):
                    best_match = candidate

            if not best_match or best_score < get_match_accept_threshold():
                logging.warning(
                    self.t("no_match").format(cleaned, int(max(best_score, 0) * 100))
                )
                return None

            logging.info(
                self.t("matched").format(best_match.get("title"), int(best_score * 100))
            )
            return attach_match_score(best_match, best_score)

        except Exception as e:
            logging.error(self.t("err").format(e))
            return None
        finally:
            try:
                session.close()
            except Exception:
                pass

    def fetch_covers(
        self, query: str, library_type: str = "Book"
    ) -> List[Dict[str, str]]:
        # La DNB ne fournit pas d'images de couverture via SRU/MARC.
        return []

    @staticmethod
    def _prefer_candidate(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
        """Tie-break : pas futur, puis année plus ancienne, puis titre plus court."""
        now = _current_pub_year()
        ya, yb = a.get("year"), b.get("year")
        a_future = isinstance(ya, int) and ya > now
        b_future = isinstance(yb, int) and yb > now
        if a_future != b_future:
            return not a_future
        if isinstance(ya, int) and isinstance(yb, int) and ya != yb:
            return ya < yb
        ta = len(a.get("title") or "")
        tb = len(b.get("title") or "")
        if ta != tb:
            return ta < tb
        return False

    # ------------------------------------------------------------------ SRU

    def _sru(
        self, session, cql: str, *, maximum: int = 8
    ) -> List[ET.Element]:
        params = {
            "version": "1.1",
            "operation": "searchRetrieve",
            "query": cql,
            "recordSchema": "MARC21-xml",
            "maximumRecords": str(max(1, min(maximum, 20))),
        }
        res = _throttled_get(
            self,
            session,
            _SRU,
            params=params,
            impersonate="chrome",
            headers={
                "Accept": "application/xml, text/xml",
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
                "User-Agent": "MetaKavita-DNB/1.0 (self-hosted; +https://github.com)",
            },
            timeout=25,
        )
        if res.status_code != 200:
            return []
        try:
            root = ET.fromstring(res.content)
        except ET.ParseError:
            return []
        return list(root.findall(".//marc:record", _NS))

    # ------------------------------------------------------------------ MARC → candidat

    def _marc_to_candidate(self, record: ET.Element) -> Optional[Dict[str, Any]]:
        idn = record.findtext("marc:controlfield[@tag='001']", default="", namespaces=_NS)
        idn = (idn or "").strip()

        title, subtitle = self._parse_title(record)
        if not title:
            return None

        authors = self._parse_authors(record)
        staff = [
            {"role": "Story", "node": {"name": {"full": name}}} for name in authors
        ]

        isbns = self._parse_isbns(record)
        isbn = None
        for n in isbns:
            if len(n) == 13:
                isbn = n
                break
        if not isbn and isbns:
            isbn = isbns[0]

        publisher, year = self._parse_publisher_year(record)
        genres, tags = self._parse_subjects(record)
        summary = self._parse_summary(record)
        series = self._parse_series(record)
        carrier, is_comic = self._parse_carrier_and_form(record, title, genres)

        alt: List[str] = []
        if subtitle and subtitle.casefold() != title.casefold():
            alt.append(subtitle)
        if series and series.casefold() not in {title.casefold(), *(a.casefold() for a in alt)}:
            alt.append(series)

        url = f"{_PORTAL}/{idn}" if idn else None

        return {
            "title": title,
            "alternative_titles": alt,
            "summary": summary,
            "cover_url": None,
            "genres": genres[: get_max_genres()] if genres else ["Book"],
            "tags": tags[: get_max_tags()],
            "year": year,
            # BF56 / BF59 : pas d'âge / statut inventés
            "staff": staff,
            "publisher": publisher,
            "format": "book",
            "url": url,
            "links": [url] if url else [],
            "isbn": isbn,
            "_isbns": isbns,
            "_carrier": carrier,
            "_is_comic": is_comic,
        }

    def _parse_carrier_and_form(
        self,
        record: ET.Element,
        title: str,
        genres: List[str],
    ) -> Tuple[str, bool]:
        """Retourne (carrier, is_comic).

        carrier ∈ {'print', 'online', 'audio', 'other'}
        """
        texts: List[str] = [title, *genres]
        for tag in ("336", "337", "338", "655", "300"):
            for df in record.findall(f"marc:datafield[@tag='{tag}']", _NS):
                for code in ("a", "b"):
                    val = _clean_marc_text(_first_sub(_subfields(df), code))
                    if val:
                        texts.append(val)
        blob = " | ".join(texts)

        is_comic = bool(_COMIC_HINTS.search(blob)) or any(
            "comic" in (g or "").casefold() or "cartoon" in (g or "").casefold()
            for g in genres
        )

        if _AUDIO_HINTS.search(blob):
            carrier = "audio"
        elif _ONLINE_HINTS.search(blob):
            carrier = "online"
        elif re.search(r"\bBand\b", blob, re.I) or re.search(
            r"ohne Hilfsmittel", blob, re.I
        ):
            carrier = "print"
        else:
            carrier = "other"
        return carrier, is_comic

    def _parse_title(self, record: ET.Element) -> Tuple[str, str]:
        df = record.find("marc:datafield[@tag='245']", _NS)
        if df is None:
            return "", ""
        subs = _subfields(df)
        title = _clean_marc_text(_first_sub(subs, "a"))
        subtitle = _clean_marc_text(_first_sub(subs, "b"))
        return title, subtitle

    def _parse_authors(self, record: ET.Element) -> List[str]:
        names: List[str] = []
        seen: set = set()
        for tag in ("100", "700"):
            for df in record.findall(f"marc:datafield[@tag='{tag}']", _NS):
                subs = _subfields(df)
                codes = {c.strip().lower() for c in (subs.get("4") or [])}
                relators = " ".join(subs.get("e") or []).lower()
                is_author = bool(codes & _AUTHOR_CODES) or "verfasser" in relators
                # 100 sans $4 : auteur principal par défaut
                if tag == "100" and not codes and not relators:
                    is_author = True
                if not is_author:
                    continue
                raw = _first_sub(subs, "a")
                name = _invert_author(raw)
                key = name.casefold()
                if name and key not in seen:
                    seen.add(key)
                    names.append(name)
        return names

    def _parse_isbns(self, record: ET.Element) -> List[str]:
        found: List[str] = []
        for df in record.findall("marc:datafield[@tag='020']", _NS):
            subs = _subfields(df)
            for code in ("a", "9"):
                for raw in subs.get(code) or []:
                    # 020 $a peut contenir "978… : EUR …"
                    token = raw.split()[0] if raw else ""
                    n = _normalize_isbn(token)
                    if n and n not in found:
                        found.append(n)
        for df in record.findall("marc:datafield[@tag='024']", _NS):
            if df.get("ind1") not in ("3",):  # EAN
                continue
            for raw in _subfields(df).get("a") or []:
                n = _normalize_isbn(raw)
                if n and n not in found:
                    found.append(n)
        return found

    def _parse_publisher_year(
        self, record: ET.Element
    ) -> Tuple[Optional[str], Optional[int]]:
        publisher = None
        year = None
        for tag in ("264", "260"):
            for df in record.findall(f"marc:datafield[@tag='{tag}']", _NS):
                # 264 ind2=1 = publication
                if tag == "264" and df.get("ind2") not in (None, " ", "1"):
                    continue
                subs = _subfields(df)
                if not publisher:
                    publisher = _clean_marc_text(_first_sub(subs, "b")) or None
                if year is None:
                    m = _YEAR.search(_first_sub(subs, "c") or "")
                    if m:
                        y = int(m.group(1))
                        if 1000 <= y <= 2100:
                            year = y
            if publisher and year:
                break
        return publisher, year

    def _parse_subjects(
        self, record: ET.Element
    ) -> Tuple[List[str], List[str]]:
        genres: List[str] = []
        tags: List[str] = []
        seen_g: set = set()
        seen_t: set = set()

        for df in record.findall("marc:datafield[@tag='655']", _NS):
            label = _clean_marc_text(_first_sub(_subfields(df), "a"))
            key = label.casefold()
            if label and key not in seen_g:
                seen_g.add(key)
                # Forme DNB souvent "Erzählende Literatur: …" → garder court
                short = label.split(":")[0].strip() if ":" in label else label
                genres.append(short if len(short) <= 60 else label[:60])

        for df in record.findall("marc:datafield[@tag='650']", _NS):
            label = _clean_marc_text(_first_sub(_subfields(df), "a"))
            key = label.casefold()
            if label and key not in seen_t and key not in seen_g:
                seen_t.add(key)
                tags.append(label)

        return genres, tags

    def _parse_summary(self, record: ET.Element) -> str:
        parts: List[str] = []
        for df in record.findall("marc:datafield[@tag='520']", _NS):
            text = _clean_marc_text(_first_sub(_subfields(df), "a"))
            if text:
                parts.append(text)
        return "\n\n".join(parts)

    def _parse_series(self, record: ET.Element) -> Optional[str]:
        for tag in ("490", "830"):
            df = record.find(f"marc:datafield[@tag='{tag}']", _NS)
            if df is None:
                continue
            name = _clean_marc_text(_first_sub(_subfields(df), "a"))
            if name:
                return name
        return None
