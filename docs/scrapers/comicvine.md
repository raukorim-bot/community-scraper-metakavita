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
| **Version** | `1.2.0` |

## Summary

ComicVine — comics (API). MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

**Requires MetaKavita 1.7.0 or newer.** On an older version this scraper fails to load and its provider disappears from every search.

1. Download [`comicvine.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/comicvine.py) into `data/scrapers/`.
2. Verify SHA-256: `47c98b62e2e15430b589be46e8f27054410e44bf9e8151bce606cc9b7e0606e0`.
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
