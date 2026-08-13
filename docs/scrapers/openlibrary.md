# Open Library (Livres/Romans)

| | |
|---|---|
| **ID** | `OPENLIBRARY` |
| **File** | [`openlibrary.py`](../../openlibrary.py) |
| **Types** | Book, Comic |
| **Method** | Official API |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | None |
| **Rate limit** | `1.1` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | INTL — en |
| **Site** | https://openlibrary.org |
| **Version** | `1.1.0` |

## Summary

Open Library — books / novels. MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

**Requires MetaKavita 1.7.0 or newer.** On an older version this scraper fails to load and its provider disappears from every search.

1. Download [`openlibrary.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/openlibrary.py) into `data/scrapers/`.
2. Verify SHA-256: `6c6b7b9f51f93e7f1e39fca88a979226378070089ac93aaa66a3e96725db6330`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book, Comic).

### Setup

No API key. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`openlibrary.org`, `covers.openlibrary.org`, `books.google.com`

## Warnings

- Anonymous Open Library ceiling is 1 req/s; rate_limit=1.1 keeps ~10% headroom without requiring identified access.
- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `OPENLIBRARY`.
