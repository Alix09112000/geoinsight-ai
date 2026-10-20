"""Régressions pour l'affichage du Québec sans provinces voisines."""
import pytest
from shapely.geometry import Point, Polygon, shape

from app.quebec_mask import ajouter_masque, masque_hors_quebec


def _regions():
    """17 régions polygonales factices, sans dépendance aux services Web."""
    results = []
    for n in range(1, 18):
        west = -81 + n
        polygon = Polygon([
            (west, 48), (west + 0.8, 48),
            (west + 0.8, 49), (west, 49), (west, 48),
        ])
        results.append({
            "type": "Feature",
            "properties": {"code": f"{n:02d}", "nom": f"Région {n}"},
            "geometry": polygon.__geo_interface__,
        })
    return results


def test_masque_conserve_toutes_les_regions_et_cache_les_voisins():
    mask_geo, bounds = masque_hors_quebec(_regions())
    mask = shape(mask_geo)
    assert mask.is_valid
    assert bounds == (-80.0, 48.0, -63.2, 49.0)
    assert not mask.contains(Point(-79.5, 48.5))
    assert not mask.contains(Point(-71.5, 48.5))
    assert mask.contains(Point(-84, 48.5))
    assert mask.contains(Point(-75, 51))


def test_masque_exige_les_17_regions():
    with pytest.raises(ValueError):
        masque_hors_quebec(_regions()[:-1])


def test_masque_folium_est_opaque_et_non_interactif():
    import folium
    mask_geo, _ = masque_hors_quebec(_regions())
    carte = folium.Map(location=[48.5, -72], zoom_start=5)
    ajouter_masque(carte, mask_geo)
    html = carte.get_root().render()
    assert "fillOpacity" in html
    assert "f7fafc" in html
    assert '"interactive": false' in html or '"interactive":false' in html
