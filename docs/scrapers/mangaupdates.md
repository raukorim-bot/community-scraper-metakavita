# MangaUpdates (Baka-Updates)

| | |
|---|---|
| **ID** | `MANGAUPDATES` |
| **File** | [`mangaupdates.py`](../../mangaupdates.py) |
| **Types** | Manga |
| **Method** | Official API |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | None |
| **Rate limit** | `0.55` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | US — en |
| **Site** | https://www.mangaupdates.com |

## Summary

MangaUpdates (Baka-Updates) — API. MetaKavita core scraper.

## Quality / when to pick

_Not audited yet._

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`mangaupdates.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/mangaupdates.py) into `data/scrapers/`.
2. Verify SHA-256: `92d542a9721cb15d58b3fd6b90e815a44518bfc5f0cbf0a3c47ceacc3a7b2782`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Manga).

### Setup

No API key. Ships as MetaKavita core (is_core).

## Proxy domains (covers)

`mangaupdates.com`, `api.mangaupdates.com`, `www.mangaupdates.com`

## Warnings

- Reads mostly unlimited; 0.55 s cushions DDoS 429 protection.

- Already ships in the MetaKavita image — Store shows state=core.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `MANGAUPDATES`.
