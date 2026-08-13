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
| **Version** | `1.1.0` |

## Summary

Decitre bookstore — HTML search + JSON-LD product page.

## Quality / when to pick

French bookstore — covers + ISBN + summary.

Gaps: `opt.: tags, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

**Requires MetaKavita 1.7.0 or newer.** On an older version this scraper fails to load and its provider disappears from every search.

1. Download [`decitre.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/decitre.py) into `data/scrapers/`.
2. Verify SHA-256: `6210f382b65061e152489f59abcab55c95b46925e5c9985f11d213236d87a894`.
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
