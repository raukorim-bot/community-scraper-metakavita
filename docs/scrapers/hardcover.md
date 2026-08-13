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
| **Version** | `1.1.0` |

## Summary

Hardcover — books (GraphQL). MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

**Requires MetaKavita 1.7.0 or newer.** On an older version this scraper fails to load and its provider disappears from every search.

1. Download [`hardcover.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/hardcover.py) into `data/scrapers/`.
2. Verify SHA-256: `85f9830abac134d3d051954491ec6606660c71d1348016b4a00c18809392953a`.
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
