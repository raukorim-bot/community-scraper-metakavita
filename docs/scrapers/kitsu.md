# Kitsu (JSON:API)

| | |
|---|---|
| **ID** | `KITSU` |
| **File** | [`kitsu.py`](../../kitsu.py) |
| **Types** | Manga |
| **Method** | Official API |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | None |
| **Rate limit** | `1.5` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | INTL — en, ja |
| **Site** | https://kitsu.io |
| **Version** | `1.0.0` |

## Summary

Kitsu — manga (JSON:API). MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`kitsu.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/kitsu.py) into `data/scrapers/`.
2. Verify SHA-256: `34bcb2894853e60761d95347e0b65db8cd08d411c3f70085c9c083b1427d9764`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Manga).

### Setup

No API key. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`kitsu.io`, `media.kitsu.app`, `media.kitsu.io`

## Warnings

- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `KITSU`.
