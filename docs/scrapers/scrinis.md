# Scrin.is (Bêta)

| | |
|---|---|
| **ID** | `SCRINIS` |
| **File** | [`scrinis.py`](../../scrinis.py) |
| **Types** | Book, Comic, Manga |
| **Method** | Official API |
| **Status** | Beta |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | Required — `SCRINIS_API_KEY` |
| **Rate limit** | `0.5` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | FR — fr, en |
| **Site** | https://scrin.is |
| **Version** | `0.2.0` |

## Summary

Scrin.is — manga / comics / books catalog via its REST API: series match and volume index matched to the owned edition (beta).

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

**Requires MetaKavita 1.7.0 or newer.** On an older version this scraper fails to load and its provider disappears from every search.

1. Download [`scrinis.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/scrinis.py) into `data/scrapers/`.
2. Verify SHA-256: `a7ec41d83c8f644fc2f529af59a3b7132e2040d4593a84604238ffd8a2993737`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book, Comic, Manga).

### Setup

Scrin.is API key (read-only) → SCRINIS_API_KEY. Store scraper (not core), beta.

## Proxy domains (covers)

`scrin.is`, `www.scrin.is`

## Warnings

- Beta — the catalog and API are still being filled before the public launch.
- Read-only key: it can search and read, never ingest. The provisional 'metakavita' key is replaced at launch.
- Volume index matches the library's edition (owned ISBN, then language / print / volume count / year). Without any hint it falls back to the site's primary edition.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `SCRINIS`.
