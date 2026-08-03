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
| **Rate limit** | `1.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | INTL — en, ja |
| **Site** | https://anilist.co |

## Summary

AniList — manga / LN metadata (GraphQL). MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`anilist.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/anilist.py) into `data/scrapers/`.
2. Verify SHA-256: `45c44569647b62aef3fec176282d2646221334634256963bba8e6e9291171c38`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book, Comic, Manga).

### Setup

No API key. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`anilist.co`

## Warnings

- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `ANILIST`.
