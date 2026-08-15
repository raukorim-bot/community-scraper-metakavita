#!/usr/bin/env python3
"""Regenerate store/catalog.json + docs/scrapers/*.md + docs/QUALITY.md.

Sources: scraper `*.py` + `store/meta.json` + `store/quality.json`.
Human-facing docs are generated in English.
"""
from __future__ import annotations

import ast
import datetime
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = "https://github.com/raukorim-bot/community-scraper-metakavita"
RAW = f"https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main"
BRANCH = "main"
SKIP = {"debug_dump_ann.py", "debug_dump_planetebd.py", "debug_dump_fandom.py", "conftest.py"}

METHOD_LABEL = {
    "html": "HTML / site",
    "api": "Official API",
    "graphql": "GraphQL (front)",
    "sru": "SRU (catalog)",
}
STATUS_LABEL = {
    "stable": "Stable",
    "beta": "Beta",
    "limited": "Limited",
    "untested": "Not live-tested",
    "retired": "Retired — out of service",
}

# MetaKavita (`services/scraper_store.is_entry_retired`) reconnaît un retrait sur
# quatre signaux indépendants. On les émet tous les quatre : une entrée de
# catalogue survit à des relectures partielles (un `status` remis à « beta » par
# mégarde, un tri de tags), et il suffit qu'un seul subsiste pour que
# l'installation reste refusée.
RETIRED_STATUS = "retired"
RETIRED_TAG = "retired"


def to_lf(data: bytes) -> bytes:
    """Content as git stores it and raw.githubusercontent.com serves it.

    A Windows clone with core.autocrlf=true has CRLF on disk, so hashing the
    working copy would publish digests no client can ever reproduce.
    """
    return data.replace(b"\r\n", b"\n")


def write_lf(path: pathlib.Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _covers_label(covers_ok) -> str:
    if covers_ok is True:
        return "Yes"
    if covers_ok is False:
        return "No"
    return "N/A"


def retirement_fields(meta_entry: dict) -> dict:
    """Bloc de retrait d'une entrée `meta.json`, ou `{}` si elle est en service.

    Le retrait est déclaré à la main dans `store/meta.json` et non déduit d'un
    scraper absent : le `.py` reste dans le dépôt (`verify_catalog_sha.py` relit
    le fichier de chaque entrée), et l'entrée doit survivre à la disparition du
    scraper pour que l'utilisateur qui l'a déjà installé soit averti.
    """
    retired = bool(meta_entry.get("retired")) or str(
        meta_entry.get("lifecycle") or meta_entry.get("status") or ""
    ).strip().lower() == RETIRED_STATUS
    if not retired:
        return {}
    retirement = meta_entry.get("retirement") or {}
    return {
        "retired": True,
        "lifecycle": RETIRED_STATUS,
        "retirement": {
            "date": retirement.get("date"),
            "replacement": retirement.get("replacement"),
            "reason": {
                "fr": retirement.get("reason_fr") or "",
                "en": retirement.get("reason_en") or "",
            },
        },
    }


def requires_app_fields(meta_entry: dict) -> dict:
    """Plancher de version MetaKavita d'une entrée, ou `{}` si elle n'en a pas.

    Un scraper du catalogue s'exécute *dans* l'image : il appelle les méthodes de
    `BaseScraper` et les fonctions de `scrapers.utils` de la version installée.
    Une copie écrite pour une version ultérieure échoue donc à l'import sur une
    antérieure, et MetaKavita délie le module scraper par scraper : le
    fournisseur disparaît des recherches sans que rien ne l'explique à l'écran.

    Le cas concret : les scrapers core de la 1.7.0 appellent `self._http_get` et
    importent `response_is_ok`, deux choses absentes de la 1.6.x. Publier ces
    copies sans plancher aurait privé de tous leurs fournisseurs core les
    conteneurs restés sur la version précédente.

    Déclaré à la main dans `store/meta.json` (`requires_app`), comme le retrait :
    seul le mainteneur sait contre quelle version une copie a été écrite.
    `services/scraper_store.is_entry_too_new` le respecte à l'installation comme
    à la synchronisation, et à égalité installe — le plancher se lit « à partir
    de cette version ».
    """
    raw = str(meta_entry.get("requires_app") or "").strip()
    return {"requires_app": raw} if raw else {}


def _id_cell(e: dict) -> str:
    """Cellule d'identifiant des tableaux, suffixée quand l'entrée est retirée."""
    return f"`{e['id']}` (retired)" if e.get("retired") else f"`{e['id']}`"


def _gaps_cell(gaps: dict | None) -> str:
    if not gaps:
        return "—"
    parts = []
    for key, label in (
        ("provider", "provider"),
        ("bug", "bug"),
        ("optional", "opt."),
    ):
        vals = gaps.get(key) or []
        if vals:
            parts.append(f"{label}: {', '.join(vals)}")
    return "; ".join(parts) if parts else "—"


def write_quality_doc(scrapers: list[dict], quality_meta: dict, out: pathlib.Path) -> None:
    audited = quality_meta.get("audited_at") or "?"
    lines = [
        "# Scraper quality overview",
        "",
        f"Payload / covers audit dated **{audited}** "
        f"(sources: `tests/run_payload_audit.py`, `store/quality.json`).",
        "",
        "Use this page to **pick a scraper**. "
        "The machine catalog [`store/catalog.json`](../store/catalog.json) "
        "exposes the same `quality` block for MetaKavita.",
        "",
        "## Legend",
        "",
        "| Field | Meaning |",
        "|-------|---------|",
        "| **Score / Grade** | Payload completeness 0–100 → A (≥90) … E (<55) |",
        "| **Covers** | `cover_url` observed on the positive test case |",
        "| **gaps.provider** | Missing upstream (not a scraper bug) |",
        "| **gaps.bug** | Expected field missing — needs a scraper fix |",
        "| **gaps.optional** | Often empty (comic ISBN, tags, status…) |",
        "",
        "## Global table",
        "",
        "| ID | Types | Grade | Score | Covers | Useful gaps | Auth | Pick if… |",
        "|----|-------|-------|-------|--------|-------------|------|----------|",
    ]
    for e in scrapers:
        q = e.get("quality") or {}
        gaps = q.get("gaps") or {}
        useful = []
        useful.extend(gaps.get("bug") or [])
        useful.extend(gaps.get("provider") or [])
        useful_s = ", ".join(useful) if useful else "—"
        grade = q.get("grade") if q.get("grade") is not None else "—"
        note = q.get("note") if q.get("note") is not None else "—"
        auth = "key" if e["auth"].get("required") else (
            "opt." if e["auth"].get("config_key") else "—"
        )
        pick = (q.get("pick") or {}).get("en") or (q.get("pick") or {}).get("fr") or "—"
        lines.append(
            f"| {_id_cell(e)} | {', '.join(e['supported_types'])} | {grade} | {note} | "
            f"{_covers_label(q.get('covers_ok'))} | {useful_s} | {auth} | {pick} |"
        )

    with_covers = [e for e in scrapers if (e.get("quality") or {}).get("covers_ok") is True]
    no_covers = [e for e in scrapers if (e.get("quality") or {}).get("covers_ok") is False]
    unknown = [e for e in scrapers if (e.get("quality") or {}).get("covers_ok") is None]

    lines.extend(
        [
            "",
            "## Covers — who provides images?",
            "",
            f"**Yes ({len(with_covers)}):** "
            + ", ".join(f"`{e['id']}`" for e in with_covers),
            "",
            f"**No / provider limit ({len(no_covers)}):** "
            + ", ".join(f"`{e['id']}`" for e in no_covers),
            "",
            f"**Not verified ({len(unknown)}):** "
            + (", ".join(f"`{e['id']}`" for e in unknown) if unknown else "—"),
            "",
            "## Suggestions by need",
            "",
            "| Need | Recommended scrapers |",
            "|------|----------------------|",
            "| Book FR + covers | `BABELIO`, `DECITRE`, `SENSCRITIQUE` |",
            "| Book FR catalog (no cover) | `BNF` (+ Babelio/Decitre for artwork) |",
            "| Book EN | `LOC` (no cover), `ISBNDB` (paid key) |",
            "| Book DE / ES / IT / NL | `DNB`, `BNE`, `SBN`, `KB` (no covers) |",
            "| Book JP + covers | `OPENBD` (ISBN); records via `NDL` |",
            "| Manga EN | `ANN`, `ANIMEPLANET`, `BANGUMI` |",
            "| Manga FR | `MANGASANCTUARY` |",
            "| Webtoon / manhwa | `WEBTOON`, `TAPAS` |",
            "| Comic US + covers | `METRON` (key), `LOCG`, `PLANETEBD` |",
            # Un seul scraper par hôte : la cadence est indexée sur l'id du
            # scraper, deux entrées visant bedetheque.com y frappent donc à la
            # somme de leurs cadences. `BDGEST` a été retiré pour cette raison.
            "| French BD | `PLANETEBD`, `BEDETHEQUE` (core), `SENSCRITIQUE` |",
            "",
            "## Gap detail (optional included)",
            "",
            "| ID | provider | bug | optional |",
            "|----|----------|-----|----------|",
        ]
    )
    for e in scrapers:
        q = e.get("quality") or {}
        g = q.get("gaps") or {}
        lines.append(
            f"| {_id_cell(e)} | {', '.join(g.get('provider') or []) or '—'} | "
            f"{', '.join(g.get('bug') or []) or '—'} | "
            f"{', '.join(g.get('optional') or []) or '—'} |"
        )
    lines.extend(
        [
            "",
            "## Updating",
            "",
            "1. Re-run `python tests/run_payload_audit.py` (and quality suite if needed).",
            "2. Update [`store/quality.json`](../store/quality.json).",
            "3. Run `python scripts/build_store_catalog.py`.",
            "",
            "To propose a new scraper via Pull Request, see [`CONTRIBUTING.md`](../CONTRIBUTING.md).",
            "",
        ]
    )
    write_lf(out, "\n".join(lines))


def parse_scraper(path: pathlib.Path) -> dict | None:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    cls = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for b in node.bases:
                name = getattr(b, "id", None) or getattr(b, "attr", None)
                if name == "BaseScraper":
                    cls = node
                    break
        if cls:
            break
    if not cls:
        return None
    fields: dict = {}
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name) and t.id in (
                    "id",
                    "display_name",
                    "version",
                    "supported_types",
                    "rate_limit",
                    "needs_api_key",
                    "has_direct_id_support",
                    "proxy_domains",
                    "uses_unified_scoring",
                    "requires_proxy",
                    "is_core",
                ):
                    try:
                        fields[t.id] = ast.literal_eval(stmt.value)
                    except Exception:
                        fields[t.id] = None
    if not fields.get("id"):
        return None
    payload = to_lf(path.read_bytes())
    fields["file"] = path.name
    fields["sha256"] = hashlib.sha256(payload).hexdigest()
    fields["bytes"] = len(payload)
    return fields


def previous_versions(catalog_path: pathlib.Path) -> dict[str, str]:
    if not catalog_path.exists():
        return {}
    try:
        previous = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        s["id"]: s["version"]
        for s in previous.get("scrapers") or []
        if s.get("id") and s.get("version")
    }


def resolve_version(sid: str, fields: dict, published: dict[str, str]) -> str:
    """Class attribute wins, then the version already published, then 1.0.0."""
    declared = fields.get("version")
    if isinstance(declared, str) and declared.strip():
        return declared.strip()
    return published.get(sid) or "1.0.0"


def auth_line(auth: dict) -> str:
    kind = auth.get("kind")
    key = auth.get("config_key")
    if kind == "none":
        return "None"
    if kind == "bearer_or_basic":
        return f"Required — `{key}` (Bearer or `user:password`)"
    if kind == "api_key":
        return f"Required — `{key}`"
    if kind == "optional_cf_cookies":
        return f"Optional — Cloudflare cookies in `{key}`"
    if kind == "optional_basic":
        return f"Optional — `user:password` in `{key}`"
    return str(kind)


def write_doc(e: dict, docs_dir: pathlib.Path, covers_note: str = "") -> None:
    stem = pathlib.Path(e["file"]).stem
    warns = (
        "\n".join(f"- {w}" for w in e["warnings"]) if e["warnings"] else "_None._"
    )
    domains = ", ".join(f"`{d}`" for d in e["proxy_domains"]) or "_—_"
    types = ", ".join(e["supported_types"])
    q = e.get("quality") or {}
    pick = (q.get("pick") or {}).get("en") or (q.get("pick") or {}).get("fr") or "_Not audited yet._"
    summary_en = e["summary"].get("en") or e["summary"].get("fr") or ""
    setup_en = e["setup"].get("en") or e["setup"].get("fr") or ""
    covers_section = f"## Covers\n\n{covers_note.strip()}\n\n" if covers_note.strip() else ""
    retirement = e.get("retirement") or {}
    banner = ""
    # Une entrée retirée garde sa page, mais elle n'a plus rien à installer :
    # la section « Install » est remplacée par la marche à suivre pour se
    # débarrasser du fichier déjà déposé sous `data/scrapers/`.
    if e.get("retired"):
        replacement = retirement.get("replacement")
        instead = f" Use `{replacement}` instead." if replacement else ""
        on_date = f" on {retirement['date']}" if retirement.get("date") else ""
        banner = f"> **Retired{on_date} — do not install.**{instead}\n\n"
        install_section = f"""## Retired — why

{retirement.get("reason", {}).get("en") or summary_en}

## Removal (MetaKavita)

MetaKavita refuses to install this entry (HTTP 403, *Install blocked (out of
service)*), and badges it **Out of service** if you already have the file.

1. Open **Manage your scrapers** (`/manage-scrapers`).
2. `{e["id"]}` is sorted to the top, with the *Out of service* badge — click **Delete**.

The scraper registry reloads on the spot, no restart needed. Deleting
`data/scrapers/{e["file"]}` by hand works too, but then MetaKavita only notices
on the next restart.
"""
    else:
        # Un plancher annoncé seulement dans le JSON serait invisible à qui pose
        # le fichier à la main, hors du Magasin : c'est le seul chemin que
        # MetaKavita ne peut pas garder.
        floor = e.get("requires_app")
        floor_line = (
            f"\n**Requires MetaKavita {floor} or newer.** On an older version this "
            "scraper fails to load and its provider disappears from every search.\n"
            if floor
            else ""
        )
        install_section = f"""## Install (MetaKavita)
{floor_line}
1. Download [`{e["file"]}`]({e["install"]["url"]}) into `data/scrapers/`.
2. Verify SHA-256: `{e["install"]["sha256"]}`.
3. Restart MetaKavita.
4. Enable the provider in Config for the matching types ({types}).

### Setup

{setup_en}
"""
    md = f"""# {e["display_name"]}

{banner}| | |
|---|---|
| **ID** | `{e["id"]}` |
| **File** | [`{e["file"]}`](../../{e["file"]}) |
| **Types** | {types} |
| **Method** | {METHOD_LABEL.get(e["method"], e["method"])} |
| **Status** | {STATUS_LABEL.get(e["status"], e["status"])} |
| **Covers (declared)** | {"Yes" if e["covers"] else "No"} |
| **Covers (audit)** | {_covers_label(q.get("covers_ok"))} |
| **Quality audit** | {q.get("grade") or "—"} / {q.get("note") if q.get("note") is not None else "—"} |
| **Auth** | {auth_line(e["auth"])} |
| **Rate limit** | `{e["rate_limit"]}` s |
| **Direct ID / URL** | {"Yes" if e["has_direct_id_support"] else "No"} |
| **Region / languages** | {e["region"]} — {", ".join(e["languages"])} |
| **Site** | {e["homepage"]} |
| **Version** | `{e["version"]}` |

## Summary

{summary_en}

## Quality / when to pick

{pick}

Gaps: `{_gaps_cell(q.get("gaps"))}` — global overview: [`docs/QUALITY.md`](../QUALITY.md).

{covers_section}{install_section}
## Proxy domains (covers)

{domains}

## Warnings

{warns}

## Store

Catalog entry: [`store/catalog.json`](../../store/catalog.json) → id `{e["id"]}`.
"""
    write_lf(docs_dir / f"{stem}.md", md.strip() + "\n")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    meta_path = ROOT / "store" / "meta.json"
    quality_path = ROOT / "store" / "quality.json"
    catalog_path = ROOT / "store" / "catalog.json"
    if not meta_path.exists():
        print(f"missing {meta_path}", file=sys.stderr)
        return 1
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    quality_raw = {}
    if quality_path.exists():
        quality_raw = json.loads(quality_path.read_text(encoding="utf-8"))
    quality_meta = quality_raw.get("_meta") or {}
    published = previous_versions(catalog_path)

    scrapers = []
    covers_notes: dict[str, str] = {}
    for path in sorted(ROOT.glob("*.py")):
        if path.name.startswith("_") or path.name in SKIP:
            continue
        fields = parse_scraper(path)
        if not fields:
            continue
        sid = fields["id"]
        m = meta.get(sid)
        if not m:
            print(f"WARNING: no meta for {sid} ({path.name})", file=sys.stderr)
            continue
        types = sorted(fields.get("supported_types") or [])
        q_src = quality_raw.get(sid) or {}
        quality = None
        if q_src:
            quality = {
                "grade": q_src.get("grade"),
                "note": q_src.get("note"),
                "audit_status": q_src.get("audit_status"),
                "covers_ok": q_src.get("covers_ok"),
                "gaps": q_src.get("gaps")
                or {"provider": [], "bug": [], "optional": []},
                "tested_query": q_src.get("tested_query"),
                "audited_at": quality_meta.get("audited_at"),
                "pick": {
                    "fr": q_src.get("pick_fr") or "",
                    "en": q_src.get("pick_en") or "",
                },
            }
        is_core = bool(fields.get("is_core"))
        retirement = retirement_fields(m)
        tags = set(
            types
            + [m["method"], m["region"].split("/")[0].lower()]
            + (["api-key"] if m["auth"].get("required") else [])
        )
        if is_core:
            tags.add("core")
        if retirement:
            tags.add(RETIRED_TAG)
        if quality and quality.get("covers_ok") is True:
            tags.add("covers")
        if quality and quality.get("covers_ok") is False:
            tags.add("no-covers")
        if quality and quality.get("grade"):
            tags.add(f"grade-{str(quality['grade']).lower()}")
        entry = {
            "id": sid,
            "file": fields["file"],
            "display_name": fields.get("display_name") or sid,
            "version": resolve_version(sid, fields, published),
            "supported_types": types,
            "library_types": types,
            "method": m["method"],
            "languages": m["languages"],
            "region": m["region"],
            "homepage": m["homepage"],
            "covers": m["covers"],
            "status": m["status"],
            "is_core": is_core,
            "rate_limit": fields.get("rate_limit"),
            "needs_api_key": bool(fields.get("needs_api_key")),
            "has_direct_id_support": bool(fields.get("has_direct_id_support")),
            "uses_unified_scoring": bool(fields.get("uses_unified_scoring", True)),
            "requires_proxy": bool(fields.get("requires_proxy", False)),
            "proxy_domains": fields.get("proxy_domains") or [],
            "auth": m["auth"],
            "summary": {"fr": m["summary_fr"], "en": m["summary_en"]},
            "setup": {"fr": m["setup_fr"], "en": m["setup_en"]},
            "warnings": m["warnings"],
            "quality": quality,
            "docs": f"docs/scrapers/{path.stem}.md",
            **retirement,
            **requires_app_fields(m),
            "install": {
                "path": fields["file"],
                "url": f"{RAW}/{fields['file']}",
                "sha256": fields["sha256"],
                "bytes": fields["bytes"],
                "target": f"data/scrapers/{fields['file']}",
            },
            "tags": sorted(tags),
        }
        covers_notes[sid] = m.get("covers_note") or ""
        scrapers.append(entry)

    catalog = {
        "schema_version": 1,
        "name": "MetaKavita Community Scraper Store",
        "description": {
            "fr": "Catalogue des scrapers communautaires vérifiés pour installation sideload dans data/scrapers/.",
            "en": "Catalog of vetted community scrapers for sideload install into data/scrapers/.",
        },
        "repo": REPO,
        "default_branch": BRANCH,
        "raw_base": RAW,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "quality_docs": "docs/QUALITY.md",
        "quality_audited_at": quality_meta.get("audited_at"),
        "install_notes": {
            "fr": "Télécharger le .py vers data/scrapers/, vérifier sha256, redémarrer MetaKavita. N’installez que des fichiers de ce dépôt.",
            "en": "Download the .py into data/scrapers/, verify sha256, restart MetaKavita. Only install files from this repository.",
        },
        "security": {
            "fr": "Un scraper = code Python exécuté avec les droits de MetaKavita. Voir CUSTOM_SCRAPERS.md.",
            "en": "A scraper is Python executed with MetaKavita privileges. See CUSTOM_SCRAPERS.md.",
        },
        "scrapers": scrapers,
    }

    store = ROOT / "store"
    store.mkdir(exist_ok=True)
    docs_dir = ROOT / "docs" / "scrapers"
    docs_dir.mkdir(parents=True, exist_ok=True)

    write_lf(catalog_path, json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")

    for e in scrapers:
        write_doc(e, docs_dir, covers_notes.get(e["id"], ""))

    write_quality_doc(scrapers, quality_meta, ROOT / "docs" / "QUALITY.md")

    index = [
        "# Community scraper documentation",
        "",
        "Per-scraper pages + machine catalog [`store/catalog.json`](../store/catalog.json).",
        "",
        "**Quality / covers / which scraper to pick:** [`QUALITY.md`](QUALITY.md).  ",
        "**Propose your own scraper via Pull Request:** [`../CONTRIBUTING.md`](../CONTRIBUTING.md).",
        "",
        "| ID | Name | Types | Method | Covers | Grade | Auth | Doc |",
        "|----|------|-------|--------|--------|-------|------|-----|",
    ]
    for e in scrapers:
        stem = pathlib.Path(e["file"]).stem
        auth = "key" if e["auth"].get("required") else ("opt." if e["auth"].get("config_key") else "—")
        q = e.get("quality") or {}
        grade = q.get("grade") if q.get("grade") is not None else "—"
        index.append(
            f"| {_id_cell(e)} | {e['display_name']} | {', '.join(e['supported_types'])} | "
            f"{e['method']} | {_covers_label(q.get('covers_ok'))} | {grade} | {auth} | "
            f"[{stem}.md](scrapers/{stem}.md) |"
        )
    index.append("")
    write_lf(ROOT / "docs" / "README.md", "\n".join(index) + "\n")

    print(
        f"OK — {len(scrapers)} scrapers → store/catalog.json + docs/scrapers/ + docs/QUALITY.md"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
