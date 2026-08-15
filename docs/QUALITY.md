# Scraper quality overview

Payload / covers audit dated **2026-08-02** (sources: `tests/run_payload_audit.py`, `store/quality.json`).

Use this page to **pick a scraper**. The machine catalog [`store/catalog.json`](../store/catalog.json) exposes the same `quality` block for MetaKavita.

## Legend

| Field | Meaning |
|-------|---------|
| **Score / Grade** | Payload completeness 0–100 → A (≥90) … E (<55) |
| **Covers** | `cover_url` observed on the positive test case |
| **gaps.provider** | Missing upstream (not a scraper bug) |
| **gaps.bug** | Expected field missing — needs a scraper fix |
| **gaps.optional** | Often empty (comic ISBN, tags, status…) |

## Global table

| ID | Types | Grade | Score | Covers | Useful gaps | Auth | Pick if… |
|----|-------|-------|-------|--------|-------------|------|----------|
| `ANILIST` | Book, Comic, Manga | — | — | N/A | — | — | — |
| `ANIMEPLANET` | Manga | A | 100 | Yes | — | — | EN manga — full payload + covers. |
| `ANN` | Manga | A | 100 | Yes | — | — | EN manga reference (XML API) — covers OK. |
| `BABELIO` | Book | A | 100 | Yes | — | — | French literature — best for FR Book libraries. |
| `BANGUMI` | Book, Manga | A | 100 | Yes | — | — | JP/CN manga & books — very complete (incl. status). |
| `BDGEST` (retired) | Comic | A | 100 | Yes | — | — | Never — retired on 2026-08-13, use BEDETHEQUE (core). |
| `BDTHEQUE` | Comic | — | — | N/A | — | — | — |
| `BEDETHEQUE` | Comic | — | — | N/A | — | — | — |
| `BNE` | Book | A | 98 | No | cover_url | — | Spanish national catalog — records OK, no SRU covers. |
| `BNF` | Book | A | 99 | No | cover_url | — | French national catalog — no covers (pair with Babelio/Decitre). |
| `COMICVINE` | Comic | — | — | N/A | — | key | — |
| `DECITRE` | Book | A | 100 | Yes | — | — | French bookstore — covers + ISBN + summary. |
| `DNB` | Book | A | 98 | No | cover_url, summary | — | German national catalog — rich records, no cover/summary. |
| `FANDOM` | Book, Comic, Manga | — | — | Yes | status, tags | — | Wiki volume index — titles / summaries / dates / ISBN / covers when catalogs miss. Not a primary. |
| `GCD` | Comic | — | — | N/A | — | opt. | US comics — often 429; covers declared but not verified this run. |
| `GOOGLEBOOKS` | Book, Comic | — | — | N/A | — | key | — |
| `HARDCOVER` | Book, Comic | — | — | N/A | — | key | — |
| `ISBNDB` | Book | — | — | N/A | — | key | Worldwide ISBN — paid key required, not live-tested. |
| `KB` | Book | A | 97 | No | cover_url, summary | — | Dutch national catalog — no SRU covers. |
| `KITSU` | Manga | — | — | N/A | — | — | — |
| `LOC` | Book | A | 97 | No | cover_url, summary, url | — | Library of Congress — SRU DC, covers/URL rarely present. |
| `LOCG` | Comic | A | 100 | Yes | — | — | US comics, no API key — series covers + summary. |
| `MAL` | Book, Manga | — | — | N/A | — | key | — |
| `MANGABAKA` | Book, Manga | — | — | N/A | — | — | — |
| `MANGADEX` | Manga | — | — | N/A | — | — | — |
| `MANGANEWS` | Manga | — | — | N/A | — | — | — |
| `MANGASANCTUARY` | Manga | A | 100 | Yes | — | — | French manga site — covers OK. |
| `MANGAUPDATES` | Manga | — | — | N/A | — | — | — |
| `METRON` | Comic | A | 100 | Yes | — | key | Best comics API (key) — staff from 1st issue + covers. |
| `NDL` | Book | A | 99 | No | cover_url | — | JP national library — records, no covers (see openBD). |
| `NOVELUPDATES` | Book, Manga | — | — | N/A | — | opt. | EN novels — Cloudflare; optional cookies. |
| `OPENBD` | Book | A | 99 | Yes | summary | — | JP ISBN + covers — summary often missing. |
| `OPENLIBRARY` | Book, Comic | — | — | N/A | — | — | — |
| `PLANETEBD` | Comic | A | 100 | Yes | — | — | FR BD + comics — very complete payload. |
| `SBN` | Book | A | 97 | No | cover_url, summary | — | Italian catalog — no covers. |
| `SENSCRITIQUE` | Book, Comic | A | 100 | Yes | — | — | FR Book/Comic — GraphQL, covers OK. |
| `SHIKIMORI` | Manga | — | — | N/A | — | — | — |
| `TAPAS` | Manga | A | 98 | Yes | summary, year | — | Manhwa/webcomics — covers OK; public HTML lacks summary/year. |
| `TEBEOSFERA` | Comic | — | — | No | — | — | ES comics — JS/iframe catalog, not scrapable yet. |
| `WEBTOON` | Manga | A | 99 | Yes | year | — | EN webtoon — covers + summary; year not exposed. |
| `WIKIDATA` | Book, Comic, Manga | C | 70 | Yes | status, tags | — | Fallback / ISBN / cross-IDs — limited scope, not a primary. |

## Covers — who provides images?

**Yes (16):** `ANIMEPLANET`, `ANN`, `BABELIO`, `BANGUMI`, `BDGEST`, `DECITRE`, `FANDOM`, `LOCG`, `MANGASANCTUARY`, `METRON`, `OPENBD`, `PLANETEBD`, `SENSCRITIQUE`, `TAPAS`, `WEBTOON`, `WIKIDATA`

**No / provider limit (8):** `BNE`, `BNF`, `DNB`, `KB`, `LOC`, `NDL`, `SBN`, `TEBEOSFERA`

**Not verified (17):** `ANILIST`, `BDTHEQUE`, `BEDETHEQUE`, `COMICVINE`, `GCD`, `GOOGLEBOOKS`, `HARDCOVER`, `ISBNDB`, `KITSU`, `MAL`, `MANGABAKA`, `MANGADEX`, `MANGANEWS`, `MANGAUPDATES`, `NOVELUPDATES`, `OPENLIBRARY`, `SHIKIMORI`

## Suggestions by need

| Need | Recommended scrapers |
|------|----------------------|
| Book FR + covers | `BABELIO`, `DECITRE`, `SENSCRITIQUE` |
| Book FR catalog (no cover) | `BNF` (+ Babelio/Decitre for artwork) |
| Book EN | `LOC` (no cover), `ISBNDB` (paid key) |
| Book DE / ES / IT / NL | `DNB`, `BNE`, `SBN`, `KB` (no covers) |
| Book JP + covers | `OPENBD` (ISBN); records via `NDL` |
| Manga EN | `ANN`, `ANIMEPLANET`, `BANGUMI` |
| Manga FR | `MANGASANCTUARY` |
| Webtoon / manhwa | `WEBTOON`, `TAPAS` |
| Comic US + covers | `METRON` (key), `LOCG`, `PLANETEBD` |
| French BD | `PLANETEBD`, `BEDETHEQUE` (core), `SENSCRITIQUE` |

## Gap detail (optional included)

| ID | provider | bug | optional |
|----|----------|-----|----------|
| `ANILIST` | — | — | — |
| `ANIMEPLANET` | — | — | isbn, publisher, alternative_titles, status |
| `ANN` | — | — | isbn, publisher, status |
| `BABELIO` | — | — | alternative_titles, status |
| `BANGUMI` | — | — | isbn |
| `BDGEST` (retired) | — | — | isbn, publisher, tags, alternative_titles, status |
| `BDTHEQUE` | — | — | — |
| `BEDETHEQUE` | — | — | — |
| `BNE` | cover_url | — | isbn, tags, alternative_titles, status |
| `BNF` | cover_url | — | publisher, tags, alternative_titles, status |
| `COMICVINE` | — | — | — |
| `DECITRE` | — | — | tags, alternative_titles, status |
| `DNB` | cover_url, summary | — | tags, status |
| `FANDOM` | status, tags | — | publisher, alternative_titles |
| `GCD` | — | — | — |
| `GOOGLEBOOKS` | — | — | — |
| `HARDCOVER` | — | — | — |
| `ISBNDB` | — | — | — |
| `KB` | cover_url, summary | — | isbn, tags, alternative_titles, status |
| `KITSU` | — | — | — |
| `LOC` | cover_url, summary, url | — | isbn, publisher, alternative_titles, status |
| `LOCG` | — | — | isbn, publisher, tags, alternative_titles, status |
| `MAL` | — | — | — |
| `MANGABAKA` | — | — | — |
| `MANGADEX` | — | — | — |
| `MANGANEWS` | — | — | — |
| `MANGASANCTUARY` | — | — | isbn, publisher, tags, alternative_titles, status |
| `MANGAUPDATES` | — | — | — |
| `METRON` | — | — | isbn, alternative_titles |
| `NDL` | cover_url | — | tags, alternative_titles, status |
| `NOVELUPDATES` | — | — | — |
| `OPENBD` | summary | — | tags, alternative_titles, status |
| `OPENLIBRARY` | — | — | — |
| `PLANETEBD` | — | — | tags, alternative_titles |
| `SBN` | cover_url, summary | — | isbn, tags, alternative_titles, status |
| `SENSCRITIQUE` | — | — | tags, alternative_titles, status |
| `SHIKIMORI` | — | — | — |
| `TAPAS` | summary, year | — | isbn, publisher, tags, alternative_titles, status |
| `TEBEOSFERA` | — | — | — |
| `WEBTOON` | year | — | isbn, publisher, tags, alternative_titles, status |
| `WIKIDATA` | status, tags | — | publisher, alternative_titles, isbn |

## Updating

1. Re-run `python tests/run_payload_audit.py` (and quality suite if needed).
2. Update [`store/quality.json`](../store/quality.json).
3. Run `python scripts/build_store_catalog.py`.

To propose a new scraper via Pull Request, see [`CONTRIBUTING.md`](../CONTRIBUTING.md).
