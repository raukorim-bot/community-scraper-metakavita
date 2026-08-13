# Bédéthèque (Franco-Belge)

| | |
|---|---|
| **ID** | `BEDETHEQUE` |
| **File** | [`bedetheque.py`](../../bedetheque.py) |
| **Types** | Comic |
| **Method** | HTML / site |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | None |
| **Rate limit** | `2.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | FR — fr |
| **Site** | https://www.bedetheque.com |
| **Version** | `1.2.0` |

## Summary

Bedetheque — Franco-Belgian comics (HTML). MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

**Requires MetaKavita 1.7.0 or newer.** On an older version this scraper fails to load and its provider disappears from every search.

1. Download [`bedetheque.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/bedetheque.py) into `data/scrapers/`.
2. Verify SHA-256: `af66bcb0a4890ce17be487f8546995d9ada971573425e00ba33f2fab0912b33c`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Comic).

### Setup

No API key. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`bedetheque.com`

## Warnings

- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `BEDETHEQUE`.
