# Planète BD

| | |
|---|---|
| **ID** | `PLANETEBD` |
| **File** | [`planetebd.py`](../../planetebd.py) |
| **Types** | Comic |
| **Method** | HTML / site |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | Yes |
| **Quality audit** | A / 100 |
| **Auth** | None |
| **Rate limit** | `2.5` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | FR — fr |
| **Site** | https://www.planetebd.com |
| **Version** | `1.2.1` |

## Summary

Planète BD — French BD / comics albums (HTML).

## Quality / when to pick

FR BD + comics — very complete payload.

Gaps: `opt.: tags, alternative_titles` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

**Requires MetaKavita 1.7.0 or newer.** On an older version this scraper fails to load and its provider disappears from every search.

1. Download [`planetebd.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/planetebd.py) into `data/scrapers/`.
2. Verify SHA-256: `495c6175f31a44eb53f9c4900a7f5a160d40c88523200fe52f5472e306807004`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Comic).

### Setup

No API key. rate_limit=2.5 s.

## Proxy domains (covers)

`planetebd.com`, `static.planetebd.com`, `www.planetebd.com`

## Warnings

- Site HTML — anti-ban rate limit.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `PLANETEBD`.
