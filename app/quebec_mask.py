"""Masque cartographique : n'afficher les fonds Plan/Satellite qu'au Québec.

La limite utilisée est l'union des 17 régions administratives officielles.
Cette géométrie sert à l'affichage et non au calcul de superficies légales.
"""
from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid


def masque_hors_quebec(regions):
    """Retourne le GeoJSON à opacifier et l'emprise officielle du Québec.

    Les 17 régions doivent être présentes : masquer à partir de la région
    sélectionnée ferait disparaître le reste de la province.
    """
    codes = {str((r.get("properties") or {}).get("code") or "") for r in regions}
    if codes != {f"{n:02d}" for n in range(1, 18)}:
        raise ValueError("Le masque requiert les 17 régions administratives officielles.")

    polygons = []
    for feature in regions:
        geom = shape(feature["geometry"])
        if not geom.is_valid:
            geom = make_valid(geom)
        if geom.is_empty or geom.geom_type not in ("Polygon", "MultiPolygon"):
            raise ValueError("Géométrie régionale manquante ou non polygonale.")
        polygons.append(geom)

    province = unary_union(polygons)
    if not province.is_valid:
        province = make_valid(province)
    if province.is_empty or province.geom_type not in ("Polygon", "MultiPolygon"):
        raise ValueError("Impossible de produire les limites polygonales du Québec.")

    # Le fond de carte est masqué partout, y compris dans les autres provinces.
    # Emprise compatible avec les latitudes affichables en Web Mercator.
    surface = box(-179.99, -85.0, 179.99, 85.0)
    exterieur = surface.difference(province)
    if not exterieur.is_valid:
        exterieur = make_valid(exterieur)
    if exterieur.is_empty:
        raise ValueError("Le masque extérieur du Québec est vide.")
    return mapping(exterieur), province.bounds


def ajouter_masque(carte, geom_masque):
    """Superposition blanche opaque non interactive sur les territoires voisins."""
    import folium

    return folium.GeoJson(
        {"type": "Feature", "properties": {"masque": "hors Québec"},
         "geometry": geom_masque},
        name="Extérieur du Québec (masqué)",
        control=False,
        interactive=False,
        style_function=lambda _: {
            "color": "#f3f2f2", "weight": 0, "opacity": 0,
            "fillColor": "#f3f2f2", "fillOpacity": 1.0,
        },
    ).add_to(carte)
