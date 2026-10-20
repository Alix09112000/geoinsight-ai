"""Vérifie l'analyse régionale sans appels aux services extérieurs."""
import pytest
from shapely.geometry import Polygon

from app.regional_bi import (
    comparer_regions, superficie_geodesique_km2, tableau_regions,
)


def feature(code, nom, geom):
    return {
        "type": "Feature",
        "properties": {"code": code, "nom": nom},
        "geometry": geom.__geo_interface__,
    }


def test_surface_wgs84_reelle_et_positive():
    # Un carré 1°x1° près de l'équateur représente environ 12 300 km².
    geom = Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)])
    km2 = superficie_geodesique_km2(geom.__geo_interface__)
    assert 12_000 < km2 < 13_000


def test_trou_du_polygone_n_est_pas_compte():
    ring = [(0, 0), (2, 0), (2, 2), (0, 2), (0, 0)]
    hole = [(0.5, 0.5), (1.5, 0.5), (1.5, 1.5), (0.5, 1.5), (0.5, 0.5)]
    sans = superficie_geodesique_km2(Polygon(ring).__geo_interface__)
    avec = superficie_geodesique_km2(Polygon(ring, [hole]).__geo_interface__)
    assert 0 < avec < sans


def test_tableau_et_comparaison():
    geom_a = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    geom_b = Polygon([(0, 0), (2, 0), (2, 2), (0, 2)])
    lignes = tableau_regions([
        feature("02", "Région B", geom_b),
        feature("01", "Région A", geom_a),
    ])
    assert [row["Code régional"] for row in lignes] == ["01", "02"]
    result = comparer_regions(lignes, "02", "01")
    assert result["Superficie A (km²)"] > result["Superficie B (km²)"]
    assert result["Écart de superficie (km²)"] > 0


def test_codes_dupliques_refuses():
    square = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    with pytest.raises(ValueError, match="dupliqué"):
        tableau_regions([
            feature("01", "A", square),
            feature("01", "A bis", square),
        ])


def test_territoires_absents_et_identiques_refuses():
    square = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    lignes = tableau_regions([feature("01", "A", square)])
    with pytest.raises(ValueError):
        comparer_regions(lignes, "01", "01")
    with pytest.raises(ValueError):
        comparer_regions(lignes, "01", "99")
