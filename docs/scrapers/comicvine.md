# ComicVine (Ultime BD/Comics)

| | |
|---|---|
| **ID** | `COMICVINE` |
| **File** | [`comicvine.py`](../../comicvine.py) |
| **Types** | Comic |
| **Method** | Official API |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | Required — `COMICVINE_API_KEY` |
| **Rate limit** | `1.2` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | US — en |
| **Site** | https://comicvine.gamespot.com |
| **Version** | `1.2.1` |

## Summary

ComicVine — comics (API). MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

**Requires MetaKavita 1.7.0 or newer.** On an older version this scraper fails to load and its provider disappears from every search.

1. Download [`comicvine.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/comicvine.py) into `data/scrapers/`.
2. Verify SHA-256: `b18e4d1bdd0cf408028617a834c69dd99bcd98cac057f479e53e0b20463b68b2`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Comic).

### Setup

ComicVine key → COMICVINE_API_KEY. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`comicvine.gamespot.com`, `static.comicvine.com`

## Warnings

- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `COMICVINE`.
