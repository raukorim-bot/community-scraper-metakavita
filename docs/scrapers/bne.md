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
| **Version** | `1.1.0` |

## Summary

National Library of Spain — Alma SRU (DC).

## Quality / when to pick

Spanish national catalog — records OK, no SRU covers.

Gaps: `provider: cover_url; opt.: isbn, tags, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`bne.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/bne.py) into `data/scrapers/`.
2. Verify SHA-256: `34b03cb8d63deafc8990cb839f66d0aeec1109b142fc1c82dfc2f70b3c89a345`.
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
