# BDgest / Bédéthèque

| | |
|---|---|
| **ID** | `BDGEST` |
| **File** | [`bdgest.py`](../../bdgest.py) |
| **Types** | Comic |
| **Method** | HTML / site |
| **Status** | Beta |
| **Covers (declared)** | Yes |
| **Covers (audit)** | Yes |
| **Quality audit** | A / 100 |
| **Auth** | None |
| **Rate limit** | `3.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | FR — fr |
| **Site** | https://www.bedetheque.com |

## Summary

BDgest / Bédéthèque — French BD via bedetheque.com (HTML, best-effort).

## Quality / when to pick

FR BD (Bédéthèque) — covers + series year.

Gaps: `opt.: isbn, publisher, tags, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`bdgest.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/bdgest.py) into `data/scrapers/`.
2. Verify SHA-256: `b9993ab015cc78d0f91a6ab117aef8b10e8c1cb9291c0c5ea19594208c9f8057`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Comic).

### Setup

No API key. rate_limit=3.0 s.

## Proxy domains (covers)

`bdgest.com`, `www.bdgest.com`, `bedetheque.com`, `www.bedetheque.com`

## Warnings

- Matching encore perfectible.
- Site sensible aux bans IP.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `BDGEST`.
