"""La synchro core doit refuser une source en retard sur les copies locales.

`sync_core_from_metakavita.py` est fait pour écraser : l'image est la source de
vérité. Le danger n'est donc pas qu'il écrase, c'est qu'il écrase depuis la
MAUVAISE source, sans rien dire. Un `git checkout` de la branche d'intégration
qui échoue sans qu'on le remarque suffit : le script recopie alors des versions
antérieures par-dessus les copies à jour, annonce « copied » pour chacune, le
catalogue se régénère, les tests passent, et la régression n'atteint que
l'utilisateur. C'est arrivé, sur sept fichiers d'un coup.
"""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync_core_from_metakavita.py"


def _load():
    spec = importlib.util.spec_from_file_location("sync_core", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["sync_core"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_declared_version_reads_the_class_attribute():
    m = _load()
    assert m._declared_version('class X:\n    version = "1.2.3"\n') == (1, 2, 3)
    assert m._declared_version('class X:\n    version = "1.10.0"\n') == (1, 10, 0)
    # Une constante de module n'est pas l'attribut de classe (4 espaces).
    assert m._declared_version('version = "9.9.9"\n') is None
    assert m._declared_version("class X:\n    pass\n") is None


def test_version_ordering_is_numeric_not_lexicographic():
    """« 1.10.0 » est postérieur à « 1.9.0 », ce qu'un tri de chaînes rate."""
    m = _load()
    assert m._declared_version('    version = "1.9.0"\n') < m._declared_version(
        '    version = "1.10.0"\n'
    )


@pytest.mark.skipif(
    not (Path(os.environ.get("METAKAVITA_ROOT", "/nonexistent")) / "scrapers").is_dir(),
    reason="METAKAVITA_ROOT absent",
)
def test_a_stale_source_is_refused_and_writes_nothing(tmp_path):
    """Une source rétrogradée doit faire échouer le script sans rien écrire."""
    m = _load()
    real = Path(os.environ["METAKAVITA_ROOT"]) / "scrapers"
    fake = tmp_path / "scrapers"
    shutil.copytree(real, fake)

    # Rétrograder une seule entrée suffit à déclencher le refus.
    target = next(
        f for f in (m.MISSING + m.EXISTING_CORE) if (fake / f).is_file()
    )
    text = (fake / target).read_text(encoding="utf-8")
    downgraded = re.sub(
        r'^(\s{4}version\s*=\s*")[0-9.]+(")',
        r"\g<1>0.0.1\g<2>",
        text,
        count=1,
        flags=re.M,
    )
    assert downgraded != text, f"impossible de rétrograder {target}"
    (fake / target).write_text(downgraded, encoding="utf-8")

    before = {
        f: (ROOT / f).read_bytes()
        for f in (m.MISSING + m.EXISTING_CORE)
        if (ROOT / f).is_file()
    }

    env = {**os.environ, "METAKAVITA_ROOT": str(tmp_path)}
    env.pop("SYNC_ALLOW_DOWNGRADE", None)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)], env=env, capture_output=True, text=True
    )

    assert proc.returncode == 1, f"le script aurait dû refuser :\n{proc.stdout}"
    assert "REFUS" in proc.stderr
    assert target in proc.stderr
    for f, content in before.items():
        assert (ROOT / f).read_bytes() == content, (
            f"{f} a été écrit malgré le refus"
        )
