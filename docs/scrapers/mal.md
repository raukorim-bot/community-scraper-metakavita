# MyAnimeList (Official API)

| | |
|---|---|
| **ID** | `MAL` |
| **File** | [`mal.py`](../../mal.py) |
| **Types** | Book, Manga |
| **Method** | Official API |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | Required — `MAL_API_KEY` |
| **Rate limit** | `1.2` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | INTL — en, ja |
| **Site** | https://myanimelist.net |
| **Version** | `1.0.0` |

## Summary

MyAnimeList — official API (Client ID). MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`mal.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/mal.py) into `data/scrapers/`.
2. Verify SHA-256: `3b1c7ed6790534b52bfa6608548617996f1692d0780bad71e3469371947ed218`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book, Manga).

### Setup

MAL Client ID → MAL_API_KEY. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`cdn.myanimelist.net`, `myanimelist.net`, `api.myanimelist.net`

## Warnings

- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `MAL`.
