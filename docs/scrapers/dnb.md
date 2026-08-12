# DNB (Deutsche Nationalbibliothek)

| | |
|---|---|
| **ID** | `DNB` |
| **File** | [`dnb.py`](../../dnb.py) |
| **Types** | Book |
| **Method** | SRU (catalog) |
| **Status** | Stable |
| **Covers (declared)** | No |
| **Covers (audit)** | No |
| **Quality audit** | A / 98 |
| **Auth** | None |
| **Rate limit** | `1.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | DE — de, en |
| **Site** | https://www.dnb.de |
| **Version** | `1.0.0` |

## Summary

German National Library — SRU MARC21 (no native covers).

## Quality / when to pick

German national catalog — rich records, no cover/summary.

Gaps: `provider: cover_url, summary; opt.: tags, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`dnb.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/dnb.py) into `data/scrapers/`.
2. Verify SHA-256: `f7e1d69edbbfad0f8381cf62029122f77fcbc802d9a97bc784e23f83873de1f1`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book).

### Setup

No API key. Year is often catalogue edition year, not first publication.

## Proxy domains (covers)

`dnb.de`, `services.dnb.de`, `d-nb.info`, `portal.dnb.de`

## Warnings

_None._

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `DNB`.
