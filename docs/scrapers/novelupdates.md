# Novel Updates

| | |
|---|---|
| **ID** | `NOVELUPDATES` |
| **File** | [`novelupdates.py`](../../novelupdates.py) |
| **Types** | Book, Manga |
| **Method** | HTML / site |
| **Status** | Limited |
| **Covers (declared)** | Yes |
| **Covers (audit)** | N/A |
| **Quality audit** | — / — |
| **Auth** | Optional — Cloudflare cookies in `NOVELUPDATES_API_KEY` |
| **Rate limit** | `3.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | US — en |
| **Site** | https://www.novelupdates.com |

## Summary

Novel Updates — light novels (HTML). Often behind Cloudflare.

## Quality / when to pick

EN novels — Cloudflare; optional cookies.

Gaps: `—` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`novelupdates.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/novelupdates.py) into `data/scrapers/`.
2. Verify SHA-256: `e00fde53ed1efb636318da84e994261b4d777b872653d84e17c0ed4de7abc3c0`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book, Manga).

### Setup

Optional: paste cf_clearance=… browser cookies into NOVELUPDATES_API_KEY. rate_limit=3.0 s.

## Proxy domains (covers)

`novelupdates.com`, `www.novelupdates.com`

## Warnings

- Sans cookies CF, les recherches échouent souvent.
- Ne pas partager vos cookies publiquement.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `NOVELUPDATES`.
