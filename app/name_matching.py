"""Harmonisation déterministe des noms de quartiers de la Ville de Québec.

Les variantes de tirets, apostrophes, espaces et accents sont prises en compte.
Les noms de quartiers numérotés entre parenthèses sont des libellés municipaux
(voir les portraits des quartiers de la Ville de Québec).
Aucun rapprochement flou automatique : les inconnus sont signalés.
"""
import re
import unicodedata

ALIASES = {
    "quartier43": "bourgroyal",
    "quartier45": "saintcharlesborromee",
    "quartier46": "saintrodrigue",
    "quartier52": "saintmichel",
    "laeroport": "aeroport",
    "quartierdelaeroport": "aeroport",
}


def normaliser_nom(nom):
    texte = unicodedata.normalize("NFKD", str(nom).strip().casefold())
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    # Un portrait peut nommer « Quartier 4-3 (Bourg-Royal) »,
    # tandis que le CSV de recensement indique seulement « Bourg-Royal ».
    match = re.fullmatch(r"quartier\s+[0-9\s\-–—]+\s*\(([^()]*)\)", texte)
    if match:
        texte = match.group(1)
    cle = re.sub(r"[^a-z0-9]", "", texte)
    return ALIASES.get(cle, cle)


def rapprochement(csv_noms, geo_noms):
    geo_map = {}
    for nom in geo_noms:
        cle = normaliser_nom(nom)
        if cle in geo_map and geo_map[cle] != nom:
            raise ValueError(f"Clé géographique ambiguë : {cle!r}")
        geo_map[cle] = nom
    associes, manquants = {}, []
    for nom in csv_noms:
        cle = normaliser_nom(nom)
        if cle in geo_map:
            associes[nom] = geo_map[cle]
        else:
            manquants.append(nom)
    return associes, manquants
