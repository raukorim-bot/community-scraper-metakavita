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
| **Rate limit** | `2.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | INTL — en |
| **Site** | https://openlibrary.org |

## Summary

Open Library — books / novels. MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`openlibrary.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/openlibrary.py) into `data/scrapers/`.
2. Verify SHA-256: `afebb79794799ac44b3d29db0159788c8caff1ac0225a5c762c2dec6b6b4c276`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book, Comic).

### Setup

No API key. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`openlibrary.org`, `covers.openlibrary.org`, `books.google.com`

## Warnings

- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `OPENLIBRARY`.
