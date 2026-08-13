# BDTheque.com (Franco-Belge)

| | |
|---|---|
| **ID** | `BDTHEQUE` |
| **File** | [`bdtheque.py`](../../bdtheque.py) |
| **Types** | Comic |
| **Method** | HTML / site |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | None |
| **Rate limit** | `2.2` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | FR — fr |
| **Site** | https://www.bdtheque.com |
| **Version** | `1.1.0` |

## Summary

BDTheque.com — Franco-Belgian comics (HTML). MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

**Requires MetaKavita 1.7.0 or newer.** On an older version this scraper fails to load and its provider disappears from every search.

1. Download [`bdtheque.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/bdtheque.py) into `data/scrapers/`.
2. Verify SHA-256: `8ee34a435ef7cf02bd91ed63499f44fea1f1432ccd570c00c25595c19c01e1b5`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Comic).

### Setup

No API key. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`bdtheque.com`, `www.bdtheque.com`

## Warnings

- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `BDTHEQUE`.
