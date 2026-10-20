"""GeoInsight AI : réparation et agrégation de polygones régionaux.

Les géométries sont réparées AVANT la fusion et la simplification. Les anneaux
intérieurs (trous) sont préservés : jamais de concaténation manuelle des anneaux.
"""
from collections import defaultdict

from shapely.errors import GEOSException
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid


def _polygons(geom):
    """Extraire seulement les surfaces polygonales (pas les lignes parasites)."""
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom] if geom.area > 0 else []
    if isinstance(geom, (MultiPolygon, GeometryCollection)):
        return [part for child in geom.geoms for part in _polygons(child)]
    return []


def _repair_polygon(source):
    geom = shape(source)
    if geom.geom_type not in ("Polygon", "MultiPolygon") or geom.is_empty:
        return []
    try:
        valid = geom if geom.is_valid else make_valid(geom)
    except GEOSException:
        valid = geom.buffer(0)
    return _polygons(valid)


def construire_regions(features, noms_officiels, tolerance=0.005):
    """Regrouper les pièces par code régional, sans casser leurs limites."""
    groups = defaultdict(list)
    for feature in features:
        props = feature.get("properties") or {}
        raw_code = str(props.get("RES_CO_REG") or "").strip()
        geometry = feature.get("geometry")
        if not raw_code.isdigit() or not geometry:
            continue
        code = raw_code.zfill(2)
        if code not in noms_officiels:
            continue
        groups[code].extend(_repair_polygon(geometry))

    results = []
    for code, parts in sorted(groups.items()):
        if not parts:
            continue
        try:
            dissolved = make_valid(unary_union(parts))
        except GEOSException:
            dissolved = make_valid(MultiPolygon(parts))
        pieces = _polygons(dissolved)
        if not pieces:
            continue
        simplified = [p.simplify(tolerance, preserve_topology=True) for p in pieces]
        rendered = MultiPolygon(_polygons(make_valid(MultiPolygon(simplified))))
        if rendered.is_empty:
            continue
        results.append({
            "type": "Feature",
            "properties": {"code": code, "nom": noms_officiels[code]},
            "geometry": mapping(rendered),
        })
    return results
