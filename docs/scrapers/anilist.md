# AniList (International)

| | |
|---|---|
| **ID** | `ANILIST` |
| **File** | [`anilist.py`](../../anilist.py) |
| **Types** | Book, Comic, Manga |
| **Method** | GraphQL (front) |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | None |
| **Rate limit** | `2.25` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | INTL — en, ja |
| **Site** | https://anilist.co |
| **Version** | `1.0.0` |

## Summary

AniList — manga / LN metadata (GraphQL). MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`anilist.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/anilist.py) into `data/scrapers/`.
2. Verify SHA-256: `7c053811528d33bd75e74c2b1e4b137cfb674c38872dc988ee43a2b4c64c3be3`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book, Comic, Manga).

### Setup

No API key. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`anilist.co`

## Warnings

- AniList API currently degraded to 30 req/min (normal 90); rate_limit=2.25 keeps ~10% headroom.
- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `ANILIST`.
