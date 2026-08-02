# Decitre

| | |
|---|---|
| **ID** | `DECITRE` |
| **File** | [`decitre.py`](../../decitre.py) |
| **Types** | Book |
| **Method** | HTML / site |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | Yes |
| **Quality audit** | A / 100 |
| **Auth** | None |
| **Rate limit** | `2.5` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | FR — fr |
| **Site** | https://www.decitre.fr |

## Summary

Decitre bookstore — HTML search + JSON-LD product page.

## Quality / when to pick

French bookstore — covers + ISBN + summary.

Gaps: `opt.: tags, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`decitre.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/decitre.py) into `data/scrapers/`.
2. Verify SHA-256: `f2a1767f78f0c2dd2b2cd172d924d7dd7d14d554523720512484ae8eb32e22a7`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book).

### Setup

No API key. rate_limit=2.5 s.

## Proxy domains (covers)

`decitre.fr`, `www.decitre.fr`, `products-images.di-static.com`, `di-static.com`

## Warnings

- E-commerce / WAF possible — respecter le rate limit.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `DECITRE`.
