# BNE (España)

| | |
|---|---|
| **ID** | `BNE` |
| **File** | [`bne.py`](../../bne.py) |
| **Types** | Book |
| **Method** | SRU (catalog) |
| **Status** | Stable |
| **Covers (declared)** | No |
| **Covers (audit)** | No |
| **Quality audit** | A / 98 |
| **Auth** | None |
| **Rate limit** | `1.2` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | ES — es |
| **Site** | https://www.bne.es |

## Summary

National Library of Spain — Alma SRU (DC).

## Quality / when to pick

Spanish national catalog — records OK, no SRU covers.

Gaps: `provider: cover_url; opt.: isbn, tags, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`bne.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/bne.py) into `data/scrapers/`.
2. Verify SHA-256: `2d53ec833819bc1ab34f30d49a216eb29581aca5c0f254cc7f41598eec5fa146`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book).

### Setup

No API key. CC0 data.

## Proxy domains (covers)

`bne.es`, `catalogo.bne.es`, `datos.bne.es`, `www.bne.es`

## Warnings

_None._

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `BNE`.
