# Grand Comics Database

| | |
|---|---|
| **ID** | `GCD` |
| **File** | [`gcd.py`](../../gcd.py) |
| **Types** | Comic |
| **Method** | Official API |
| **Status** | Stable |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | Optional — `user:password` in `GCD_API_KEY` |
| **Rate limit** | `2.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | US — en |
| **Site** | https://www.comics.org |
| **Version** | `1.0.0` |

## Summary

Grand Comics Database — JSON /api/ (HTML blocked by Cloudflare).

## Quality / when to pick

US comics — often 429; covers declared but not verified this run.

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`gcd.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/gcd.py) into `data/scrapers/`.
2. Verify SHA-256: `8b3da951196015a43dacf015d33d067d3a59226b78e5299dcd598f1c4f300b6c`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Comic).

### Setup

Optional: comics.org user:password in GCD_API_KEY (higher quota).

## Proxy domains (covers)

`comics.org`, `www.comics.org`, `files1.comics.org`, `files2.comics.org`, `files.comics.org`

## Warnings

- Couvertures sur files1.comics.org (proxy MetaKavita).

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `GCD`.
