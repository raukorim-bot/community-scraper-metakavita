# SBN (Italia)

| | |
|---|---|
| **ID** | `SBN` |
| **File** | [`sbn.py`](../../sbn.py) |
| **Types** | Book |
| **Method** | Official API |
| **Status** | Beta |
| **Covers (declared)** | No |
| **Covers (audit)** | No |
| **Quality audit** | A / 97 |
| **Auth** | None |
| **Rate limit** | `1.5` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | IT — it |
| **Site** | https://opac.sbn.it |

## Summary

SBN / ICCU — Italian national bibliographic catalog (OPAC mobile JSON).

## Quality / when to pick

Italian catalog — no covers.

Gaps: `provider: cover_url, summary; opt.: isbn, tags, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Install (MetaKavita)

1. Download [`sbn.py`](https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/sbn.py) into `data/scrapers/`.
2. Verify SHA-256: `e91dc8c8c27fb2a69a5f324162cc02aaf16c42bfcfd90e7209a3102b4ed32ec4`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types (Book).

### Setup

No API key. OPAC app endpoint (not officially documented for third parties).

## Proxy domains (covers)

`sbn.it`, `opac.sbn.it`, `www.sbn.it`, `iccu.sbn.it`

## Warnings

- API mobile non officiellement documentée — peut changer.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `SBN`.
