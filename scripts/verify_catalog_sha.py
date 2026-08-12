#!/usr/bin/env python3
"""Check every store/catalog.json digest against the bytes the Store will serve.

raw.githubusercontent.com returns the git blob, which is LF. A Windows clone
with core.autocrlf=true has CRLF on disk, so hashing the working copy publishes
digests that MetaKavita can never reproduce (`StoreError: sha256 mismatch`).
This runs offline: it hashes the LF-normalized working copy, and — when git is
available — proves that normalization is byte-for-byte what git stores.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def to_lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def git_blob_oid(path: Path) -> str | None:
    """OID git would record for `path`, filters applied. None if git is absent."""
    try:
        out = subprocess.run(
            ["git", "hash-object", "--path", str(path.relative_to(ROOT)), str(path)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def local_blob_oid(payload: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(payload) + payload).hexdigest()


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    catalog = json.loads((ROOT / "store" / "catalog.json").read_text(encoding="utf-8"))
    entries = catalog.get("scrapers") or []
    ok, bad = 0, []
    git_checked, git_disagreed = 0, []

    for entry in entries:
        sid = entry["id"]
        install = entry.get("install") or {}
        path = ROOT / entry["file"]
        if not path.is_file():
            bad.append(f"{sid}: missing file {entry['file']}")
            continue

        raw = path.read_bytes()
        payload = to_lf(raw)
        digest = hashlib.sha256(payload).hexdigest()
        expected = (install.get("sha256") or "").lower()

        problems = []
        if digest != expected:
            cause = "unknown"
            if hashlib.sha256(raw).hexdigest() == expected:
                cause = "catalog hashed the CRLF working copy"
            problems.append(f"sha256 {expected[:12]}… != {digest[:12]}… ({cause})")
        if install.get("bytes") != len(payload):
            problems.append(f"bytes {install.get('bytes')} != {len(payload)}")

        oid = git_blob_oid(path)
        if oid:
            git_checked += 1
            if oid != local_blob_oid(payload):
                git_disagreed.append(sid)

        if problems:
            bad.append(f"{sid} ({entry['file']}): " + "; ".join(problems))
        else:
            ok += 1

    print(f"entries : {len(entries)}")
    print(f"sha OK  : {ok}")
    print(f"sha KO  : {len(bad)}")
    for item in bad:
        print("  !", item)

    if git_checked:
        print(
            f"git     : {git_checked}/{len(entries)} files confirmed byte-identical "
            "to the blob git will store"
        )
        for sid in git_disagreed:
            print(f"  ! {sid}: LF normalization differs from git's own filters")
    else:
        print("git     : unavailable, LF normalization not cross-checked")

    return 1 if bad or git_disagreed else 0


if __name__ == "__main__":
    raise SystemExit(main())
