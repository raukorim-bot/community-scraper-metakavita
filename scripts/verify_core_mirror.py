#!/usr/bin/env python3
"""Verify MetaKavita core scrapers are mirrored & tagged in this community repo."""
from __future__ import annotations

import ast
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MK = Path(r"Z:\kavitafetcher\scrapers")
SKIP = {"__init__.py", "base.py", "utils.py", "wikidata_map.py"}
DEBUG = {"debug_dump_ann.py", "debug_dump_planetebd.py"}
RAW = "https://raw.githubusercontent.com/raukorim-bot/community-scraper-metakavita/main"


def to_lf(data: bytes) -> bytes:
    """Content as git stores it and raw.githubusercontent.com serves it."""
    return data.replace(b"\r\n", b"\n")


def parse_fields(path: Path) -> dict | None:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(
            (getattr(b, "id", None) or getattr(b, "attr", None)) == "BaseScraper"
            for b in node.bases
        ):
            continue
        fields: dict = {}
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name) and t.id in (
                        "id",
                        "is_core",
                        "display_name",
                        "needs_api_key",
                        "supported_types",
                    ):
                        try:
                            fields[t.id] = ast.literal_eval(stmt.value)
                        except Exception:
                            pass
        return fields
    return None


def file_is_core(path: Path) -> tuple[bool, str | None]:
    fields = parse_fields(path) or {}
    return fields.get("is_core") is True, fields.get("id")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    issues: list[str] = []

    mk_core: dict[str, str] = {}
    for p in sorted(MK.glob("*.py")):
        if p.name in SKIP or p.name.startswith("__"):
            continue
        ok, sid = file_is_core(p)
        if ok and sid:
            mk_core[sid] = p.name

    comm: dict[str, dict] = {}
    for p in sorted(ROOT.glob("*.py")):
        if p.name.startswith("_") or p.name in DEBUG:
            continue
        fields = parse_fields(p)
        if not fields or not fields.get("id"):
            continue
        sid = fields["id"]
        text = p.read_text(encoding="utf-8")
        if "from .base import" in text or "from .utils import" in text:
            issues.append(f"RELATIVE_IMPORT {p.name}")
        if "from scrapers.base import" not in text:
            issues.append(f"NO_ABS_BASE_IMPORT {p.name}")
        comm[sid] = {
            "file": p.name,
            "is_core": fields.get("is_core") is True,
        }

    cat = json.loads((ROOT / "store" / "catalog.json").read_text(encoding="utf-8"))
    meta = json.loads((ROOT / "store" / "meta.json").read_text(encoding="utf-8"))
    scrapers = cat.get("scrapers") or []
    cat_by_id = {s["id"]: s for s in scrapers}

    print("=== COUNTS ===")
    print(f"MetaKavita is_core: {len(mk_core)}")
    print(f"Community BaseScraper modules: {len(comm)}")
    print(f"catalog scrapers: {len(scrapers)}")
    print(f"meta.json keys: {len(meta)}")
    print(f"catalog is_core true: {sum(1 for s in scrapers if s.get('is_core'))}")

    print()
    print("=== MK CORE vs COMMUNITY FILES ===")
    missing_files = sorted(set(mk_core) - set(comm))
    extra_core = sorted(sid for sid, d in comm.items() if d["is_core"] and sid not in mk_core)
    print("MK core absent from community files:", missing_files or "OK")
    print("Community is_core but not MK core:", extra_core or "OK (none)")

    for sid, fn in sorted(mk_core.items()):
        d = comm.get(sid)
        if not d:
            issues.append(f"MISSING_FILE {sid}")
            continue
        if d["file"] != fn:
            issues.append(f"FILENAME_MISMATCH {sid}: community={d['file']} mk={fn}")
        if not d["is_core"]:
            issues.append(f"NOT_TAGGED_CORE {sid} ({d['file']})")

    print()
    print("=== CATALOG / META / SHA / DOCS ===")
    for sid, fn in sorted(mk_core.items()):
        e = cat_by_id.get(sid)
        if not e:
            issues.append(f"MISSING_CATALOG {sid}")
            continue
        if not e.get("is_core"):
            issues.append(f"CATALOG_NOT_CORE {sid}")
        if "core" not in (e.get("tags") or []):
            issues.append(f"CATALOG_NO_CORE_TAG {sid}")
        if sid not in meta:
            issues.append(f"MISSING_META {sid}")
        path = ROOT / e["file"]
        if not path.is_file():
            issues.append(f"CATALOG_FILE_MISSING {sid} {e['file']}")
            continue
        digest = hashlib.sha256(to_lf(path.read_bytes())).hexdigest()
        cat_sha = ((e.get("install") or {}).get("sha256") or "").lower()
        if digest != cat_sha:
            issues.append(f"SHA_MISMATCH {sid}")
        docs = ROOT / (e.get("docs") or f"docs/scrapers/{Path(e['file']).stem}.md")
        if not docs.is_file():
            issues.append(f"MISSING_DOC {sid}")

    for sid, e in sorted(cat_by_id.items()):
        if sid not in meta:
            issues.append(f"CATALOG_WITHOUT_META {sid}")
        if not (ROOT / e["file"]).is_file():
            issues.append(f"CATALOG_ORPHAN_FILE {sid}")

    print()
    print("=== REMOTE (GitHub main) ===")
    try:
        remote = json.load(urllib.request.urlopen(f"{RAW}/store/catalog.json", timeout=30))
        remote_ids = {s["id"] for s in remote.get("scrapers") or []}
        remote_core = {s["id"] for s in remote.get("scrapers") or [] if s.get("is_core")}
        print(f"remote catalog count={len(remote_ids)} remote_core={len(remote_core)}")
        print("local vs remote id diff:", sorted(set(cat_by_id) - remote_ids) or "OK synced")
        print("MK core missing on remote:", sorted(set(mk_core) - remote_core) or "OK")
        body = urllib.request.urlopen(f"{RAW}/mangabaka.py", timeout=20).read().decode(
            "utf-8", "replace"
        )
        print("remote mangabaka is_core:", "is_core = True" in body)
        print("remote mangabaka abs import:", "from scrapers.base import" in body)
        print("remote mangabaka cover allowlist:", "images.mangabaka.dev" in body)
    except Exception as exc:
        issues.append(f"REMOTE_FETCH_FAIL {exc}")

    print()
    print("=== ISSUES ===")
    if issues:
        for item in issues:
            print(" !", item)
        print(f"FAIL ({len(issues)} issues)")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
