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
| `ANIMEPLANET` | Manga | A | 100 | Yes | — | — | EN manga — full payload + covers. |
| `ANN` | Manga | A | 100 | Yes | — | — | EN manga reference (XML API) — covers OK. |
| `BABELIO` | Book | A | 100 | Yes | — | — | French literature — best for FR Book libraries. |
| `BANGUMI` | Book, Manga | A | 100 | Yes | — | — | JP/CN manga & books — very complete (incl. status). |
| `BDGEST` | Comic | A | 100 | Yes | — | — | FR BD (Bédéthèque) — covers + series year. |
| `BNE` | Book | A | 98 | No | cover_url | — | Spanish national catalog — records OK, no SRU covers. |
| `BNF` | Book | A | 99 | No | cover_url | — | French national catalog — no covers (pair with Babelio/Decitre). |
| `DECITRE` | Book | A | 100 | Yes | — | — | French bookstore — covers + ISBN + summary. |
| `DNB` | Book | A | 98 | No | cover_url, summary | — | German national catalog — rich records, no cover/summary. |
| `GCD` | Comic | — | — | N/A | — | opt. | US comics — often 429; covers declared but not verified this run. |
| `ISBNDB` | Book | — | — | N/A | — | key | Worldwide ISBN — paid key required, not live-tested. |
| `KB` | Book | A | 97 | No | cover_url, summary | — | Dutch national catalog — no SRU covers. |
| `LOC` | Book | A | 97 | No | cover_url, summary, url | — | Library of Congress — SRU DC, covers/URL rarely present. |
| `LOCG` | Comic | A | 100 | Yes | — | — | US comics, no API key — series covers + summary. |
| `MANGASANCTUARY` | Manga | A | 100 | Yes | — | — | French manga site — covers OK. |
| `METRON` | Comic | A | 100 | Yes | — | key | Best comics API (key) — staff from 1st issue + covers. |
| `NDL` | Book | A | 99 | No | cover_url | — | JP national library — records, no covers (see openBD). |
| `NOVELUPDATES` | Book, Manga | — | — | N/A | — | opt. | EN novels — Cloudflare; optional cookies. |
| `OPENBD` | Book | A | 99 | Yes | summary | — | JP ISBN + covers — summary often missing. |
| `PLANETEBD` | Comic | A | 100 | Yes | — | — | FR BD + comics — very complete payload. |
| `SBN` | Book | A | 97 | No | cover_url, summary | — | Italian catalog — no covers. |
| `SENSCRITIQUE` | Book, Comic | A | 100 | Yes | — | — | FR Book/Comic — GraphQL, covers OK. |
| `TAPAS` | Manga | A | 98 | Yes | summary, year | — | Manhwa/webcomics — covers OK; public HTML lacks summary/year. |
| `TEBEOSFERA` | Comic | — | — | No | — | — | ES comics — JS/iframe catalog, not scrapable yet. |
| `WEBTOON` | Manga | A | 99 | Yes | year | — | EN webtoon — covers + summary; year not exposed. |

## Covers — who provides images?

**Yes (14):** `ANIMEPLANET`, `ANN`, `BABELIO`, `BANGUMI`, `BDGEST`, `DECITRE`, `LOCG`, `MANGASANCTUARY`, `METRON`, `OPENBD`, `PLANETEBD`, `SENSCRITIQUE`, `TAPAS`, `WEBTOON`

**No / provider limit (8):** `BNE`, `BNF`, `DNB`, `KB`, `LOC`, `NDL`, `SBN`, `TEBEOSFERA`

**Not verified (3):** `GCD`, `ISBNDB`, `NOVELUPDATES`

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
| French BD | `PLANETEBD`, `BDGEST`, `SENSCRITIQUE` |

## Gap detail (optional included)

| ID | provider | bug | optional |
|----|----------|-----|----------|
| `ANIMEPLANET` | — | — | isbn, publisher, alternative_titles, status |
| `ANN` | — | — | isbn, publisher, status |
| `BABELIO` | — | — | alternative_titles, status |
| `BANGUMI` | — | — | isbn |
| `BDGEST` | — | — | isbn, publisher, tags, alternative_titles, status |
| `BNE` | cover_url | — | isbn, tags, alternative_titles, status |
| `BNF` | cover_url | — | publisher, tags, alternative_titles, status |
| `DECITRE` | — | — | tags, alternative_titles, status |
| `DNB` | cover_url, summary | — | tags, status |
| `GCD` | — | — | — |
| `ISBNDB` | — | — | — |
| `KB` | cover_url, summary | — | isbn, tags, alternative_titles, status |
| `LOC` | cover_url, summary, url | — | isbn, publisher, alternative_titles, status |
| `LOCG` | — | — | isbn, publisher, tags, alternative_titles, status |
| `MANGASANCTUARY` | — | — | isbn, publisher, tags, alternative_titles, status |
| `METRON` | — | — | isbn, alternative_titles |
| `NDL` | cover_url | — | tags, alternative_titles, status |
| `NOVELUPDATES` | — | — | — |
| `OPENBD` | summary | — | tags, alternative_titles, status |
| `PLANETEBD` | — | — | tags, alternative_titles |
| `SBN` | cover_url, summary | — | isbn, tags, alternative_titles, status |
| `SENSCRITIQUE` | — | — | tags, alternative_titles, status |
| `TAPAS` | summary, year | — | isbn, publisher, tags, alternative_titles, status |
| `TEBEOSFERA` | — | — | — |
| `WEBTOON` | year | — | isbn, publisher, tags, alternative_titles, status |

## Updating

1. Re-run `python tests/run_payload_audit.py` (and quality suite if needed).
2. Update [`store/quality.json`](../store/quality.json).
3. Run `python scripts/build_store_catalog.py`.

To propose a new scraper via Pull Request, see [`CONTRIBUTING.md`](../CONTRIBUTING.md).
