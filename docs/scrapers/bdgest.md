# BDgest / Bédéthèque

> **Retired on 2026-08-13 — do not install.** Use `BEDETHEQUE` instead.

| | |
|---|---|
| **ID** | `BDGEST` |
| **File** | [`bdgest.py`](../../bdgest.py) |
| **Types** | Comic |
| **Method** | HTML / site |
| **Status** | Retired — out of service |
| **Covers (declared)** | Yes |
| **Covers (audit)** | Yes |
| **Quality audit** | A / 100 |
| **Auth** | None |
| **Rate limit** | `3.0` s |
| **Direct ID / URL** | Yes |
| **Region / languages** | FR — fr |
| **Site** | https://www.bedetheque.com |
| **Version** | `1.1.0` |

## Summary

Out of service — duplicate of BEDETHEQUE (core) on the same site, with a separate throttle clock that doubled traffic to bedetheque.com. Use BEDETHEQUE instead.

## Quality / when to pick

Never — retired on 2026-08-13, use BEDETHEQUE (core).

Gaps: `opt.: isbn, publisher, tags, alternative_titles, status` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

## Retired — why

The bdgest.com search is dead: the scraper actually queried bedetheque.com end to end. The catalog already ships BEDETHEQUE for that site, and does it better (CSRF token, ban 403 told apart from a 404, ISO-8859-1 decoding, album index). Above all, throttling is keyed on the scraper id: BDGEST and BEDETHEQUE kept two separate clocks for a single host, so enabling both hit bedetheque.com at the sum of the two rates — which is how an IP got banned.

## Removal (MetaKavita)

MetaKavita refuses to install this entry (HTTP 403, *Install blocked (out of
service)*), and badges it **Out of service** if you already have the file.

1. Open **Manage your scrapers** (`/manage-scrapers`).
2. `BDGEST` is sorted to the top, with the *Out of service* badge — click **Delete**.

The scraper registry reloads on the spot, no restart needed. Deleting
`data/scrapers/bdgest.py` by hand works too, but then MetaKavita only notices
on the next restart.

## Proxy domains (covers)

`bdgest.com`, `www.bdgest.com`, `bedetheque.com`, `www.bedetheque.com`

## Warnings

- Retiré le 2026-08-13 — remplacé par BEDETHEQUE (livré en core).
- Site sensible aux bans IP : deux scrapers sur bedetheque.com = deux fois la cadence.

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `BDGEST`.
