# Contributing a scraper (Pull Request)

Anyone can propose a new metadata scraper for MetaKavita by opening a **Pull Request** on this repository. After review and merge, the scraper appears in the community store catalog and can be sideloaded into `data/scrapers/`.

> **Security:** a scraper is executable Python with MetaKavita’s privileges. PRs are reviewed before merge. Do not paste untrusted scrapers into your own `data/scrapers/` outside this repo. Full rules: [`CUSTOM_SCRAPERS.md`](CUSTOM_SCRAPERS.md).

---

## Overview

```text
Fork → write one .py → test locally → update store/meta.json
  → (optional) store/quality.json → regenerate catalog → open PR
```

Maintainers review code, rate limits, matching quality, and security before merge.

---

## 1. Fork and branch

1. Fork [community-scraper-metakavita](https://github.com/raukorim-bot/community-scraper-metakavita).
2. Create a branch, e.g. `scraper/mysite`.
3. Keep **one scraper per PR** when possible (easier review).

---

## 2. Implement the scraper

Follow the contract in **[`CUSTOM_SCRAPERS.md`](CUSTOM_SCRAPERS.md)** (BaseScraper, scoring, allowed libraries, `proxy_domains`).

Checklist for the `.py` file:

| Requirement | Detail |
|-------------|--------|
| One file | e.g. `mysite.py` at the **repo root** (same level as `babelio.py`) |
| `id` | Uppercase unique id (`MYSITE`) |
| `display_name` | Human label shown in MetaKavita |
| `supported_types` | Subset of `Book` / `Manga` / `Comic` |
| `rate_limit` | Seconds between requests (be polite; HTML sites often ≥ 2.5–3.0) |
| `proxy_domains` | Hosts needed for covers / API |
| `needs_api_key` | `True` if a Config key is required |
| Libraries | Prefer `curl_cffi` + `bs4`; **no** Selenium / Playwright |
| Matching | Use `clean_title`, `score_candidate`, `attach_match_score`, `get_match_accept_threshold` |
| Caps | Respect `get_max_genres()` / `get_max_tags()` |

Do **not** commit API keys, cookies, or personal tokens.

---

## 3. Test locally

You need a MetaKavita checkout on `PYTHONPATH` (imports `scrapers.base`, `config_manager`, …).

```bat
set PYTHONPATH=Z:\path\to\MetaKavita
set METAKAVITA_ROOT=Z:\path\to\MetaKavita
```

Minimum checks to mention in the PR:

1. **Positive match** — known title returns the right series/book + sensible `_match_score`.
2. **Negative match** — nonsense query (`zzzzqwxnotitle999`) returns `None`.
3. **Covers** — if the site has images, `cover_url` / `fetch_covers` work.
4. **Optional:** copy the `.py` into MetaKavita `data/scrapers/`, restart, enrich a series in the UI.

Helpers in this repo:

```bat
python tests\run_live_smoke.py
python tests\run_quality.py
python tests\run_payload_audit.py
```

(Wire your scraper into `tests/run_quality.py` suites if you can; otherwise describe manual tests in the PR.)

---

## 4. Register it in the store

So MetaKavita’s catalog can list your scraper:

1. Add an entry in **[`store/meta.json`](store/meta.json)** for your `id` (`method`, `languages`, `covers`, `status`, `auth`, `summary_fr` / `summary_en`, `setup_*`, `warnings`).
2. Optionally add a stub in **[`store/quality.json`](store/quality.json)** (`audit_status`: `SKIP` or `PASS` after you ran the audit).
3. Regenerate:

```bat
python scripts\build_store_catalog.py
```

This updates `store/catalog.json`, `docs/scrapers/<name>.md`, `docs/README.md`, and `docs/QUALITY.md`.

If you only ship the `.py` + a clear PR description, maintainers can fill meta/catalog — but including them speeds up merge.

---

## 5. Open the Pull Request

Target branch: **`main`**.

### PR title

```text
Add <SiteName> scraper (<ID>)
```

### PR body (copy this)

```markdown
## Summary
- Site / API:
- Library types: Book / Manga / Comic
- Auth: none / key name
- Covers: yes / no

## How to test
- Query 1 → expected title:
- Query 2 (negative) → None
- Covers checked: yes / no
- Commands run:

## Checklist
- [ ] One `.py` at repo root, unique uppercase `id`
- [ ] Follows CUSTOM_SCRAPERS.md (no Selenium, unified scoring)
- [ ] Polite `rate_limit` + complete `proxy_domains`
- [ ] No secrets committed
- [ ] `store/meta.json` updated (or explicitly left to maintainers)
- [ ] `python scripts/build_store_catalog.py` run if meta changed
```

### What reviewers look for

- Safe code (no shell, no unexpected outbound hosts, no secret exfiltration patterns)
- Stable matching (not first-hit-only chaos)
- Honest `covers` / warnings (CF, paid key, JS-only sites → document limits)
- Catalog consistency (`id`, sha256, docs)

---

## 6. After merge

1. The scraper is available from this repo / raw GitHub URL.
2. Users install by copying the `.py` into MetaKavita `data/scrapers/` (or via the future store UI reading `store/catalog.json`).
3. Bump quality scores later with `run_payload_audit.py` when maintainers re-audit.

---

## Questions / ideas without code

Open a GitHub **Issue** (provider name, URL, Book/Manga/Comic, whether an API exists). A PR with a working scraper is preferred when you can.

---

## Licence / upstream terms

Respect the target site’s terms of use and rate limits. Metadata belongs to upstream providers. Contributions are accepted in the same spirit as MetaKavita — use at your own risk.
