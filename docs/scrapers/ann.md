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
| **Rate limit** | `1.2` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | US — en |
| **Site** | https://www.animenewsnetwork.com |

## Summary

Anime News Network encyclopedia — public XML API.

## Quality / when to pick

EN manga reference (XML API) — covers OK.

Gaps: `opt.: isbn, publisher, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`ann.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/ann.py) into `data/scrapers/`.
2. Verify SHA-256: `e303e53b47a506e533a2fde177e7e78a9afeb2231518a1acd7e8731e6dc343f6`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Manga).

### Setup

No API key.

## Proxy domains (covers)

`animenewsnetwork.com`, `cdn.animenewsnetwork.com`

## Warnings

_None._

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `ANN`.
