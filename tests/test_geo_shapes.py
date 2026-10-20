"""Régressions : régions découpées, trous conservés, géométries invalides."""
from shapely.geometry import Polygon, shape

from app.geo_shapes import construire_regions


def test_trou_interieur_non_rempli():
    shell = [(-78, 50), (-68, 50), (-68, 58), (-78, 58), (-78, 50)]
    hole = [(-75, 53), (-73, 53), (-73, 55), (-75, 55), (-75, 53)]
    polygon = Polygon(shell, [hole])
    features = [{"properties": {"RES_CO_REG": "10"}, "geometry": polygon.__geo_interface__}]
    result = construire_regions(features, {"10": "Nord-du-Québec"}, tolerance=0)
    assert len(result) == 1
    output = shape(result[0]["geometry"])
    assert output.is_valid
    assert abs(output.area - polygon.area) < 1e-6
    assert len(output.geoms[0].interiors) == 1


def test_morceaux_dupliques_regroupes():
    polys = [
        Polygon([(-70, 50), (-69, 50), (-69, 51), (-70, 51), (-70, 50)]),
        Polygon([(-71, 50), (-70, 50), (-70, 51), (-71, 51), (-71, 50)]),
    ]
    features = [{"properties": {"RES_CO_REG": "09"}, "geometry": p.__geo_interface__}
                for p in polys]
    result = construire_regions(features, {"09": "Côte-Nord"}, tolerance=0)
    assert len(result) == 1
    assert shape(result[0]["geometry"]).is_valid
    assert abs(shape(result[0]["geometry"]).area - 2) < 1e-6


def test_auto_intersection_reparee():
    crossed = {"type": "Polygon", "coordinates": [
        [(-70, 50), (-69, 51), (-70, 51), (-69, 50), (-70, 50)]
    ]}
    result = construire_regions(
        [{"properties": {"RES_CO_REG": "03"}, "geometry": crossed}],
        {"03": "Capitale-Nationale"}, tolerance=0
    )
    assert len(result) == 1
    assert shape(result[0]["geometry"]).is_valid
