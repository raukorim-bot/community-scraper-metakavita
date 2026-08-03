# Hardcover (Expérimental / GraphQL)

| | |
|---|---|
| **ID** | `HARDCOVER` |
| **File** | [`hardcover.py`](../../hardcover.py) |
| **Types** | Book, Comic |
| **Method** | GraphQL (front) |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | Required — `HARDCOVER_API_KEY` |
| **Rate limit** | `1.2` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | US — en |
| **Site** | https://hardcover.app |

## Summary

Hardcover — books (GraphQL). MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`hardcover.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/hardcover.py) into `data/scrapers/`.
2. Verify SHA-256: `9030b0e380d659aff880a60ad0250f1da27ae521dfb78d7c3e83cab49889c88c`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book, Comic).

### Setup

Hardcover key → HARDCOVER_API_KEY. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`hardcover.app`, `api.hardcover.app`, `img.hardcover.app`

## Warnings

- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `HARDCOVER`.
