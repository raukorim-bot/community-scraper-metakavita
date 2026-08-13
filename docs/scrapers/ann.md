# Anime News Network

| | |
|---|---|
| **ID** | `ANN` |
| **File** | [`ann.py`](../../ann.py) |
| **Types** | Manga |
| **Method** | Official API |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | Yes |
| **Quality audit** | A / 100 |
| **Auth** | None |
| **Rate limit** | `1.1` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | US — en |
| **Site** | https://www.animenewsnetwork.com |
| **Version** | `1.1.0` |

## Summary

Anime News Network encyclopedia — public XML API.

## Quality / when to pick

EN manga reference (XML API) — covers OK.

Gaps: `opt.: isbn, publisher, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

**Requires MetaKavita 1.7.0 or newer.** On an older version this scraper fails to load and its provider disappears from every search.

1. Download [`ann.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/ann.py) into `data/scrapers/`.
2. Verify SHA-256: `991ab976231071a2596c168309ef451f7ce82136480ec0196701c18695e44979`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Manga).

### Setup

No API key.

## Proxy domains (covers)

`animenewsnetwork.com`, `cdn.animenewsnetwork.com`

## Warnings

- Official 1 req/s; rate_limit=1.1 keeps ~10% headroom.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `ANN`.
