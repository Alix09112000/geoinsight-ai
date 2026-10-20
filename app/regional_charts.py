"""Graphiques territoriaux légers, sans Altair ni dépendance JavaScript.

Les barres commencent à zéro, les noms restent complets et les chiffres
proviennent exclusivement des données passées par l'application.
"""
from html import escape
import math

from app.socioeconomic import INDICATEURS, format_indicateur


def _nombre(value):
    try:
        val = float(value)
    except (ValueError, TypeError) as error:
        raise ValueError("Valeur numérique indisponible.") from error
    if not math.isfinite(val) or val < 0:
        raise ValueError("Valeur numérique invalide.")
    return val


def graphique_barres(rows, label_key, value_key, title, formatter=None, year=None):
    """HTML autonome : zéro réel, tri décroissant, étiquettes complètes.

    Les libellés sont échappés pour sécuriser les données importées en CSV.
    """
    points = []
    for row in rows:
        label = str(row.get(label_key) or "").strip()
        if not label:
            raise ValueError("Nom de territoire manquant.")
        value = _nombre(row.get(value_key))
        text = (formatter(value) if formatter is not None
                else f"{value:,.1f}".replace(",", " ").replace(".", ","))
        points.append((label, value, str(text)))
    if not points:
        raise ValueError("Aucune donnée à représenter.")

    points.sort(key=lambda p: (-p[1], p[0]))
    largest = max(val for _, val, _ in points)
    scale = largest if largest > 0 else 1.0

    parts = [
        '<section class="gi-bars" role="figure" aria-label="' + escape(title, quote=True) + '">',
        '<div class="gi-bars-heading">' + escape(title) +
        (f' · {int(year)}' if year is not None else '') + '</div>',
        '<div class="gi-bars-axis">0 — échelle proportionnelle à la valeur</div>',
    ]
    for label, val, display in points:
        percent = 100.0 * val / scale
        safe_label = escape(label, quote=True)
        safe_display = escape(display, quote=True)
        parts.append(
            '<div class="gi-bars-row">'
            '<div class="gi-bars-name" title="' + safe_label + '">' + safe_label + '</div>'
            '<div class="gi-bars-track" title="' + safe_label + ' : ' + safe_display + '">'
            '<span class="gi-bars-fill" style="width:' + f'{percent:.4f}%' + '"></span>'
            '</div>'
            '<div class="gi-bars-value">' + safe_display + '</div>'
            '</div>'
        )
    parts.append('</section>')
    return "\n".join(parts)


def graphique_indicateur_regions(rows, champ):
    """Graphique régional pour un indicateur ISQ connu (année/unités exactes)."""
    if champ not in INDICATEURS:
        raise ValueError("Indicateur régional inconnu.")
    titre, _unite, annee = INDICATEURS[champ]
    return graphique_barres(
        rows, "nom_region", champ, titre,
        formatter=lambda val: format_indicateur(val, champ),
        year=annee,
    )
