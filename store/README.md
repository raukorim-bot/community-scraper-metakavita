# MetaKavita Scraper Store

Primary files for the future MetaKavita **scraper store**:

- **[`catalog.json`](catalog.json)** — machine-readable list of community scrapers.
- **[`meta.json`](meta.json)** — human-edited texts / auth / warnings (build input).
- **[`quality.json`](quality.json)** — human-edited payload / covers / gaps audit scores.
- **Human overview:** [`docs/QUALITY.md`](../docs/QUALITY.md) — global view to help pick a scraper.

## Stable URL (wire into MetaKavita)

```text
https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main/store/catalog.json
```

Repo: https://github.com/raukorim-bot/community-scraper-metakavita

## Contract `schema_version: 1`

MetaKavita can:

1. `GET` the catalog JSON.
2. Display `display_name`, `summary`, `supported_types`, `status`, `auth`, `warnings`, **`quality`**.
3. Filter / sort on `quality.covers_ok`, `quality.grade`, `tags` (`covers`, `no-covers`, `grade-a`…).
4. Offer install: download `install.url` → `install.target` (`data/scrapers/<file>`).
5. Verify `install.sha256` before enabling.
6. Prompt for a restart (auto-discovery of `.py` files).

### Important per-scraper fields

| Field | UI / runtime use |
|-------|------------------|
| `id` | Provider id (unique) |
| `file` / `install.url` | File to sideload |
| `install.sha256` | Integrity check |
| `supported_types` | Book / Manga / Comic |
| `needs_api_key` + `auth.config_key` | Show Config key field |
| `proxy_domains` | Cover allowlist (also read when loading the `.py`) |
| `rate_limit` | Docs / info (enforced in the `.py`) |
| `status` | `stable` / `beta` / `limited` / `untested` |
| `covers` | Declared capability (meta) |
| `quality.covers_ok` | Cover seen in live audit (`true` / `false` / `null`) |
| `quality.grade` / `quality.note` | Payload grade A–E / score 0–100 |
| `quality.gaps` | `{ provider, bug, optional }` — classified missing fields |
| `quality.pick` | Short FR/EN “pick this if…” blurb |
| `docs` | Human doc page |

### Security

Install **only** entries from this catalog (or an explicit fork). A sideloaded `.py` runs with MetaKavita’s privileges — see `CUSTOM_SCRAPERS.md`.

To **propose a new scraper**, open a Pull Request — see [`CONTRIBUTING.md`](../CONTRIBUTING.md).

### Regeneration

After changing a scraper, `meta.json`, or `quality.json`:

```bat
python scripts\build_store_catalog.py
```

This regenerates `store/catalog.json`, `docs/scrapers/*.md`, `docs/README.md`, and `docs/QUALITY.md`.
