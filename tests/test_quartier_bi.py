"""Tests du moteur choroplèthe GeoInsight AI."""
from app.quartier_bi import preparer_couche, score_disponibilite


def _normalise(n):
    return str(n).casefold().replace(" ", "")


ZONES = [
    {"quartier": "Vanier", "geometry": {"type": "Polygon", "coordinates": [
        [[-71.3, 46.8], [-71.2, 46.8], [-71.2, 46.9], [-71.3, 46.8]]
    ]}},
    {"quartier": "Saint-Roch", "geometry": {"type": "Polygon", "coordinates": [
        [[-71.2, 46.8], [-71.1, 46.8], [-71.1, 46.9], [-71.2, 46.8]]
    ]}},
]

INDICATEURS = [
    {"quartier": "Vanier", "population": 13495, "superficie_km2": 3.5},
    {"quartier": "Saint-Roch", "population": None, "superficie_km2": 1.7},
]


def test_population_ne_remplit_pas_les_donnees_manquantes():
    coll, valeurs = preparer_couche(ZONES, INDICATEURS, _normalise, "population")
    assert valeurs == [13495.]
    assert coll["features"][0]["properties"]["Population"] == "13 495"
    assert coll["features"][1]["properties"]["valeur"] is None
    assert coll["features"][1]["properties"]["Densité"] == "Non disponible"


def test_densite_utilise_population_et_superficie():
    coll, valeurs = preparer_couche(ZONES, INDICATEURS, _normalise, "densite_hab_km2")
    assert len(valeurs) == 1
    assert abs(valeurs[0] - (13495/3.5)) < 1e-7
    assert "hab./km²" in coll["features"][0]["properties"]["Densité"]


def test_pas_de_zero_division_et_validation_du_champ():
    indicateurs = [{"quartier": "Vanier", "population": 10, "superficie_km2": 0}]
    coll, valeurs = preparer_couche(ZONES[:1], indicateurs, _normalise, "densite_hab_km2")
    assert valeurs == []
    assert coll["features"][0]["properties"]["valeur"] is None
    import pytest
    with pytest.raises(ValueError):
        preparer_couche(ZONES, INDICATEURS, _normalise, "revenu_median")


def test_couverture():
    assert score_disponibilite(INDICATEURS, "population") == 1
