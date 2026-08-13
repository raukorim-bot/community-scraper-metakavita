"""Cadence des requêtes : chemin nominal et repli de compatibilité (hors réseau).

Contexte. Un scraper déclare un `rate_limit`, mais celui-ci n'était appliqué
qu'UNE fois, par l'appelant, avant `fetch()`. Les six à quatorze requêtes émises
à l'intérieur de `fetch()` partaient donc en rafale — c'est ce profil de trafic
qui a fait bannir une IP sur bedetheque.com, le site que vise `bdgest.py`. Les
scrapers passent désormais par `_throttled_get`, qui délègue à
`BaseScraper._http_get` (lequel appelle `throttle_provider()` avant chaque
requête).

Ce que ces tests protègent, et pourquoi les deux moitiés comptent :

1. Quand `_http_get` existe, CHAQUE requête sortante doit être précédée d'un
   passage par la cadence — pas une par `fetch()`, une par requête.
2. Quand il n'existe pas — le scraper est installé sur une image MetaKavita
   antérieure à son ajout — le scraper ne doit ni planter ni repartir en
   rafale. C'est le cas qui n'a aucune chance d'être vu en développement, où
   l'image est toujours à jour, et c'est exactement pour ça qu'il est testé.

Aucune requête réseau : la session est une doublure, l'horloge est simulée.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import bdgest
from bdgest import BdgestScraper


class FakeClock:
    """Horloge simulée : `sleep()` avance le temps au lieu de le passer.

    Mesurer une vraie attente rendrait le test lent (3 s de `rate_limit`) et
    dépendant de la charge de la machine. Ce qu'on veut vérifier n'est pas la
    durée réelle du sommeil mais le fait qu'il soit demandé, et pour la bonne
    valeur.
    """

    def __init__(self, start: float = 1000.0):
        self.now = start
        self.slept: list = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


@pytest.fixture
def throttle_spy(monkeypatch):
    """Compte les passages par la cadence partagée, sans jamais dormir."""
    from services import provider_throttle

    provider_throttle.reset_throttle_state()
    seen: list = []
    monkeypatch.setattr(
        provider_throttle, "throttle_provider", lambda scraper: seen.append(scraper.id)
    )
    return seen


def _ok_response():
    # `len(res.text)` vaut 0 sur un MagicMock : `_search` s'arrête juste après
    # la requête de recherche, ce qui rend le nombre d'appels déterministe.
    return MagicMock(status_code=200)


def test_every_outgoing_request_goes_through_the_shared_throttle(throttle_spy):
    """Chaque `session.get` doit être précédé d'un passage par la cadence.

    L'égalité stricte est le cœur du correctif : un `assert len(spy) >= 1`
    passerait aussi avec l'ancien code, où la cadence n'était honorée qu'une
    fois pour toute la rafale.
    """
    session = MagicMock()
    session.get.return_value = _ok_response()

    BdgestScraper()._search(session, "asterix")

    assert session.get.call_count >= 2, (
        "Le scénario testé doit émettre plusieurs requêtes, sinon il ne prouve "
        "rien sur la rafale."
    )
    assert len(throttle_spy) == session.get.call_count
    assert set(throttle_spy) == {"BDGEST"}


def test_falls_back_cleanly_when_the_image_has_no_http_helper(throttle_spy):
    """Image antérieure à `_http_get` : ni plantage, ni requête non cadencée.

    L'attribut d'instance à `None` masque celui hérité de `BaseScraper` et
    reproduit fidèlement ce que voit `getattr(self, "_http_get", None)` sur une
    installation qui n'a pas le helper.
    """
    scraper = BdgestScraper()
    scraper._http_get = None

    session = MagicMock()
    session.get.return_value = _ok_response()

    scraper._search(session, "asterix")

    assert session.get.call_count >= 2
    assert len(throttle_spy) == session.get.call_count, (
        "Le repli doit passer par la même horloge partagée que le chemin "
        "nominal : un compteur séparé autoriserait deux fois la cadence."
    )


def test_last_resort_counter_paces_when_provider_throttle_is_missing(monkeypatch):
    """Sans même `services.provider_throttle`, le compteur local doit cadencer.

    `None` dans `sys.modules` fait échouer l'import comme sur une image qui n'a
    pas ce module : c'est le seul chemin où le scraper ne peut compter que sur
    lui-même.
    """
    monkeypatch.setitem(__import__("sys").modules, "services.provider_throttle", None)
    clock = FakeClock()
    monkeypatch.setattr(bdgest, "time", clock)
    monkeypatch.setattr(bdgest, "_LAST_CALL", {})

    scraper = SimpleNamespace(id="BDGEST", rate_limit=3.0, http_timeout=20.0)
    session = MagicMock()
    session.get.return_value = _ok_response()

    bdgest._throttled_get(scraper, session, "https://example.invalid/a")
    assert clock.slept == [], "La première requête ne doit rien attendre."

    bdgest._throttled_get(scraper, session, "https://example.invalid/b")
    assert clock.slept == [3.0], (
        "La seconde requête doit attendre le solde du `rate_limit` : sans cela "
        "le repli laisse repartir la rafale qu'on cherche à supprimer."
    )


def test_fallback_applies_the_default_timeout(monkeypatch):
    """Le repli doit aussi porter le `http_timeout`, comme `_http_get`.

    Une requête sans délai peut bloquer un worker indéfiniment quand le
    fournisseur cesse de répondre — l'autre moitié du contrat du helper.
    """
    monkeypatch.setattr(bdgest, "_LAST_CALL", {})
    scraper = SimpleNamespace(id="BDGEST", rate_limit=0.0, http_timeout=17.0)
    session = MagicMock()
    session.get.return_value = _ok_response()

    bdgest._throttled_get(scraper, session, "https://example.invalid/a")
    assert session.get.call_args.kwargs["timeout"] == 17.0

    bdgest._throttled_get(scraper, session, "https://example.invalid/b", timeout=5)
    assert session.get.call_args.kwargs["timeout"] == 5
