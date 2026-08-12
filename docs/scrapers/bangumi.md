# Bangumi (JP/CN)

| | |
|---|---|
| **ID** | `BANGUMI` |
| **File** | [`bangumi.py`](../../bangumi.py) |
| **Types** | Book, Manga |
| **Method** | Official API |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | Yes |
| **Quality audit** | A / 100 |
| **Auth** | None |
| **Rate limit** | `1.2` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | JP/CN — ja, zh, en |
| **Site** | https://bgm.tv |
| **Version** | `1.0.0` |

## Summary

Bangumi API (JP/CN manga / light novels). User-Agent handled by scraper.

## Quality / when to pick

JP/CN manga & books — very complete (incl. status).

Gaps: `opt.: isbn` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`bangumi.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/bangumi.py) into `data/scrapers/`.
2. Verify SHA-256: `8e780d12347e83714a506d4a1cd0abc16e9fa154db54052ffff3d968690a835a`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book, Manga).

### Setup

No API key.

## Proxy domains (covers)

`bgm.tv`, `api.bgm.tv`, `lain.bgm.tv`

## Warnings

_None._

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `BANGUMI`.
