# KB (Nederland)

| | |
|---|---|
| **ID** | `KB` |
| **File** | [`kb.py`](../../kb.py) |
| **Types** | Book |
| **Method** | SRU (catalog) |
| **Status** | Beta |
| **Covers (declared)** | No |
| **Covers (audit)** | No |
| **Quality audit** | A / 97 |
| **Auth** | None |
| **Rate limit** | `1.5` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | NL — nl |
| **Site** | https://www.kb.nl |
| **Version** | `1.1.0` |

## Summary

KB National Library of the Netherlands — JSRU SRU (GGC/DPO).

## Quality / when to pick

Dutch national catalog — no SRU covers.

Gaps: `provider: cover_url, summary; opt.: isbn, tags, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`kb.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/kb.py) into `data/scrapers/`.
2. Verify SHA-256: `b9f60397a24dac46a8c535251af2ce6bc826a97f2b4432c161f1f683ef877a1c`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book).

### Setup

No API key. Catalog coverage to validate live.

## Proxy domains (covers)

`kb.nl`, `jsru.kb.nl`, `www.kb.nl`, `resolver.kb.nl`

## Warnings

- Collections SRU KB surtout numériques / GGC — à finetuner après tests.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `KB`.
