"""Garde-fou de catalogue : aucun scraper communautaire n'émet de requête nue.

Le correctif de cadence est facile à défaire sans s'en apercevoir — il suffit
d'ajouter un `session.get(...)` de plus dans un `_search` existant, ou de
recopier un scraper voisin écrit avant la conversion. Le symptôme n'apparaît
pas en développement : il apparaît chez l'utilisateur, sous forme d'une IP
bannie par le fournisseur. Ce test relit donc le catalogue à la source.

Il n'importe aucun scraper : l'analyse est purement syntaxique, elle tourne
sans MetaKavita sur le `PYTHONPATH` et sans le moindre accès réseau.

Les fichiers marqués `is_core = True` sont exclus : ce sont des copies
conformes des scrapers de l'image MetaKavita, régénérées par
`scripts/sync_core_from_metakavita.py`. Les corriger ici créerait une
divergence que la prochaine synchronisation effacerait sans bruit.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Receveurs d'un appel sortant. Un `hit.get("url")` sur un dictionnaire porte le
# même nom de méthode qu'un `session.get(url)` : seule l'identité du receveur
# permet de distinguer une lecture de dictionnaire d'une requête HTTP.
_HTTP_CLIENTS = {"session", "requests", "client", "http", "s"}

# Fonctions du motif de compatibilité : ce sont les seules autorisées à appeler
# `client.get` / `client.post` en direct, puisque c'est précisément leur rôle.
_HELPER_NAMES = {"_throttled_get", "_throttled_post"}


def _scraper_modules() -> list[tuple[str, ast.Module, ast.ClassDef]]:
    """Les fichiers du catalogue qui définissent un scraper, avec leur classe."""
    out = []
    for path in sorted(ROOT.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            bases = {getattr(b, "id", None) or getattr(b, "attr", None) for b in node.bases}
            if "BaseScraper" in bases:
                out.append((path.name, tree, node))
                break
    return out


def _class_attr(cls: ast.ClassDef, name: str):
    for stmt in cls.body:
        if not isinstance(stmt, ast.Assign):
            continue
        for target in stmt.targets:
            if isinstance(target, ast.Name) and target.id == name:
                try:
                    return ast.literal_eval(stmt.value)
                except Exception:
                    return None
    return None


def _receiver_name(func: ast.Attribute) -> str:
    value = func.value
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        return value.attr
    return ""


def _raw_http_calls(tree: ast.Module) -> list[int]:
    """Numéros de ligne des requêtes qui ne passent pas par le motif cadencé.

    Les helpers sont retirés avant l'analyse plutôt que filtrés pendant :
    `ast.walk` aplatit l'arbre, et un simple `continue` sur le nœud du helper
    laisserait quand même passer les appels de son corps.
    """
    lines = []
    body = [
        node
        for node in tree.body
        if not (isinstance(node, ast.FunctionDef) and node.name in _HELPER_NAMES)
    ]
    for node in body:
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if not isinstance(func, ast.Attribute) or func.attr not in ("get", "post"):
                continue
            receiver = _receiver_name(func)
            if receiver in _HTTP_CLIENTS or receiver.endswith("_session"):
                lines.append(child.lineno)
    return sorted(lines)


COMMUNITY = [
    (name, tree, cls)
    for name, tree, cls in _scraper_modules()
    if not _class_attr(cls, "is_core")
]


def test_the_catalog_still_has_community_scrapers_to_check():
    """Si l'énumération casse, les tests suivants passeraient à vide."""
    assert len(COMMUNITY) >= 15


@pytest.mark.parametrize("name,tree,cls", COMMUNITY, ids=[c[0] for c in COMMUNITY])
def test_no_uncadenced_outgoing_request(name, tree, cls):
    offenders = _raw_http_calls(tree)
    assert not offenders, (
        f"{name} émet une requête sans passer par la cadence "
        f"(lignes {offenders}). Utilisez `_throttled_get(self, session, url, …)` "
        f"— le `rate_limit` déclaré n'est appliqué qu'une fois par `fetch()` par "
        f"l'appelant, tout le reste de la rafale y échappe."
    )


@pytest.mark.parametrize("name,tree,cls", COMMUNITY, ids=[c[0] for c in COMMUNITY])
def test_http_helper_probes_the_image_before_using_it(name, tree, cls):
    """Le helper doit sonder `_http_get` plutôt que l'appeler à l'aveugle.

    Un appel direct planterait à l'exécution sur toute installation MetaKavita
    antérieure à l'ajout du helper — sans message utile pour l'utilisateur.
    """
    helpers = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in _HELPER_NAMES
    }
    if not helpers:
        pytest.skip(f"{name} n'émet aucune requête sortante")
    for helper in helpers.values():
        source = ast.dump(helper)
        assert "getattr" in source, (
            f"{name}: {helper.name} doit récupérer `_http_get` via `getattr` "
            "pour rester installable sur une image MetaKavita antérieure."
        )


@pytest.mark.parametrize("name,tree,cls", COMMUNITY, ids=[c[0] for c in COMMUNITY])
def test_scrapers_that_make_requests_declare_a_version(name, tree, cls):
    """Sans montée de version, un scraper corrigé n'atteint pas les utilisateurs.

    L'image refuse d'installer une entrée de catalogue dont la version est en
    retard sur la copie déjà présente sous `data/scrapers/`, et le générateur du
    catalogue lit cet attribut de classe — pas une constante de module.
    """
    makes_requests = any(
        isinstance(node, ast.FunctionDef) and node.name in _HELPER_NAMES
        for node in tree.body
    )
    if not makes_requests:
        pytest.skip(f"{name} n'émet aucune requête sortante")
    version = _class_attr(cls, "version")
    assert isinstance(version, str) and version.count(".") == 2, (
        f"{name} doit déclarer `version = \"major.minor.patch\"` en attribut de "
        "classe, sinon le correctif reste bloqué chez les utilisateurs."
    )
