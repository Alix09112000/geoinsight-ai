"""Graphiques socioéconomiques régionaux : présentation comparable et non trompeuse.

- Barre horizontale démarrant toujours à zéro
- Classement décroissant (17 régions)
- Noms complets et valeurs avec unités + année
- Aucune modification des chiffres source ISQ
"""
import math

import altair as alt
import pandas as pd

from app.socioeconomic import INDICATEURS, format_indicateur


def graphique_indicateur_regions(rows, champ):
    if champ not in INDICATEURS:
        raise ValueError("Indicateur régional inconnu.")
    titre, unite, annee = INDICATEURS[champ]
    points = []
    for row in rows:
        region = str(row["nom_region"]).strip()
        try:
            value = float(row[champ])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Valeur indisponible pour {region}") from error
        if not region or not math.isfinite(value) or value < 0:
            raise ValueError(f"Valeur invalide pour {region}")
        points.append({
            "region": region,
            "valeur": value,
            "affichage": format_indicateur(value, champ),
            "annee": str(annee),
        })
    if not points:
        raise ValueError("Aucune région à représenter.")
    maximum = max(row["valeur"] for row in points)
    domaine_max = maximum * 1.28 if maximum > 0 else 1
    data = pd.DataFrame(points)
    ordre = alt.SortField(field="valeur", order="descending")
    x = alt.X(
        "valeur:Q",
        title=f"{titre} ({unite})",
        scale=alt.Scale(domain=[0, domaine_max], zero=True),
        axis=alt.Axis(
            labelFontSize=11, titleFontSize=12, grid=True,
            format=".1f" if unite == "%" else "~s",
        ),
    )
    y = alt.Y(
        "region:N",
        sort=ordre,
        title=None,
        axis=alt.Axis(labelLimit=380, labelFontSize=12, labelPadding=8),
    )
    base = alt.Chart(data).encode(x=x, y=y)
    barres = base.mark_bar(color="#087f8c", cornerRadiusEnd=3).encode(
        tooltip=[
            alt.Tooltip("region:N", title="Région"),
            alt.Tooltip("affichage:N", title=titre),
            alt.Tooltip("annee:N", title="Année"),
        ]
    )
    labels = base.mark_text(
        align="left", baseline="middle", dx=6,
        fontSize=11, fontWeight="bold", color="#244b61"
    ).encode(text="affichage:N")
    return (barres + labels).properties(
        height=max(380, len(points) * 31),
        padding={"left": 6, "top": 10, "right": 12, "bottom": 4},
    ).configure_view(stroke=None)
