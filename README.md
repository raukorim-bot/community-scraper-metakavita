# Community scrapers — MetaKavita

Official community repository for **plug-and-play** metadata scrapers for [MetaKavita](https://github.com/raukorim-bot/MetaKavita).

Drop a `.py` file into your MetaKavita `data/scrapers/` folder, restart, and the provider appears in the UI.

> **Security:** installing a scraper runs arbitrary Python with the same privileges as MetaKavita. Only install files from this repository (or sources you trust). Full authoring rules: [`CUSTOM_SCRAPERS.md`](CUSTOM_SCRAPERS.md).

---

## Install

1. Copy the scraper `.py` file(s) you want into MetaKavita’s **`data/scrapers/`** directory  
   (Docker: the folder mapped to `/app/data/scrapers`, or your host `./data/scrapers`).
2. Restart MetaKavita.
3. Check **Config / providers** — the new source should be listed for the matching library type.

No rebuild of the MetaKavita image is required.

---

## Available scrapers

| File | ID | Types | Auth | Covers | Notes |
|------|-----|-------|------|--------|-------|
| [`babelio.py`](babelio.py) | `BABELIO` | Book | None | Yes | French literature (HTML) |
| [`senscritique.py`](senscritique.py) | `SENSCRITIQUE` | Book, Comic | None | Yes | FR — GraphQL Apollo |
| [`dnb.py`](dnb.py) | `DNB` | Book | None | No | Deutsche Nationalbibliothek (SRU MARC21) |
| [`metron.py`](metron.py) | `METRON` | Comic | **Required** | Yes | [metron.cloud](https://metron.cloud) API token → `METRON_API_KEY` |
| [`bangumi.py`](bangumi.py) | `BANGUMI` | Manga, Book | None* | Yes | Bangumi (`api.bgm.tv`) — JP/CN |
| [`ann.py`](ann.py) | `ANN` | Manga | None | Yes | Anime News Network encyclopedia (XML) |
| [`planetebd.py`](planetebd.py) | `PLANETEBD` | Comic | None | Yes | Planète BD — BD FR + comics US (HTML) |

\*Bangumi expects a proper User-Agent (handled by the scraper).

### Skipped / blocked for now

| Provider | Reason |
|----------|--------|
| Novel Updates | Cloudflare JS challenge (`Just a moment…`) — TLS impersonation alone is not enough |
| League of Comic Geeks | Official API needs developer `client_id` / `client_secret` |
| Grand Comics Database | Cloudflare JS challenge |
| Nautiljon | IP bans / aggressive anti-bot (historical) |

### Metron API key

1. Create an account on [metron.cloud](https://metron.cloud)
2. Profile → **API Tokens** → generate
3. Paste into MetaKavita config as `METRON_API_KEY`  
   (Bearer token, or `user:password` for basic auth)

---

## Authoring / vibecoding

See **[`CUSTOM_SCRAPERS.md`](CUSTOM_SCRAPERS.md)** for the full contract (BaseScraper, scoring, tags/genres caps, `proxy_domains`, inheritance patterns).

---

## Contributing

1. Fork this repo
2. Add one `.py` file per provider (uppercase `id`, clear `display_name`, `supported_types`, `rate_limit`, `proxy_domains`)
3. Open a PR with a short description + how you tested (title search + covers if any)

Maintainer review required before merge.

---

## Licence

Same spirit as MetaKavita — use at your own risk. Metadata belongs to the respective upstream sites/APIs; respect their terms and rate limits.
