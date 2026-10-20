"""Tests des correspondances entre noms municipaux et CSV de population."""
from app.name_matching import normaliser_nom, rapprochement


def test_typographie():
    assert normaliser_nom("Vieux-Québec–Cap-Blanc–Colline Parlementaire") == normaliser_nom(
        "Vieux Québec - Cap Blanc / Colline Parlementaire"
    )
    assert normaliser_nom("Neufchâtel Est–Lebourgneuf") == normaliser_nom(
        "Neufchâtel-Est—Lebourgneuf"
    )
    assert normaliser_nom("Duberger-Les Saules") == normaliser_nom("Duberger – Les-Saules")
    assert normaliser_nom("Aéroport") == normaliser_nom("L'Aéroport")


def test_quartiers_numerotes():
    assert normaliser_nom("Quartier 4-3 (Bourg-Royal)") == normaliser_nom("Bourg-Royal")
    assert normaliser_nom("Quartier 4-5 (Saint-Charles-Borromée)") == normaliser_nom("Saint-Charles-Borromée")


def test_jointure_non_ambigue():
    matches, missing = rapprochement(
        ["Bourg-Royal", "Aéroport", "Duberger-Les Saules"],
        ["Quartier 4-3 (Bourg-Royal)", "L'Aéroport", "Duberger – Les-Saules"],
    )
    assert missing == []
    assert len(matches) == 3


def test_pas_de_fuzzy_non_valide():
    matches, missing = rapprochement(["Cap Roug"], ["Cap-Rouge"])
    assert not matches
    assert missing == ["Cap Roug"]


def test_doublons_refuses():
    import pytest
    with pytest.raises(ValueError):
        rapprochement(["Bourg-Royal"], ["Bourg-Royal", "Quartier 4-3 (Bourg-Royal)"])
