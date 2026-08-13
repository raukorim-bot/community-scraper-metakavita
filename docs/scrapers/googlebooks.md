# Google Books

| | |
|---|---|
| **ID** | `GOOGLEBOOKS` |
| **File** | [`googlebooks.py`](../../googlebooks.py) |
| **Types** | Book, Comic |
| **Method** | Official API |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | Required — `GOOGLEBOOKS_API_KEY` |
| **Rate limit** | `1.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | INTL — en, fr |
| **Site** | https://books.google.com |
| **Version** | `1.1.0` |

## Summary

Google Books — books / comics (API). MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

**Requires MetaKavita 1.7.0 or newer.** On an older version this scraper fails to load and its provider disappears from every search.

1. Download [`googlebooks.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/googlebooks.py) into `data/scrapers/`.
2. Verify SHA-256: `156c2d1cb0fc7351f31a719421c1fd28d06d15e96d6778b1dbda3b836cd6f54c`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book, Comic).

### Setup

Google key → GOOGLEBOOKS_API_KEY. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`books.google.com`, `books.googleusercontent.com`, `googleusercontent.com`

## Warnings

- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `GOOGLEBOOKS`.
