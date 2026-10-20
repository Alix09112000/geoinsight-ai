## Design dashboard — maquette approuvée

L'interface Streamlit suit désormais la maquette de référence : bandeau compact bleu marine, barre latérale claire, quatre KPI, grande carte interactive et fiche du territoire à droite. Les deux fonds **Plan (OpenStreetMap)** et **Satellite (Esri World Imagery)** sont fonctionnels. La vue des quartiers conserve les choroplèthes, les données de population 2021, les comparaisons et les exports CSV.

Les éléments absents de cette version (recherche universelle, 3D réelle, prédiction IA) ne sont pas présentés comme opérationnels. La reproduction pixel par pixel nécessiterait un front-end dédié comme React/MapLibre ; ce chantier reste distinct de la version Streamlit publique.

# GeoInsight AI — Business Intelligence géospatiale du Québec

**Vision :** analyser, comparer et modéliser les territoires de toute la **province de Québec** (régions administratives, MRC, municipalités, quartiers), avec les données ouvertes et des méthodes géostatistiques.

## Installation (Windows)

```powershell
py -3.11 -m pip install -r requirements.txt
py -3.11 -m etl.ingest_quartiers
py -3.11 -m streamlit run app/main.py
```

Ouvrir http://localhost:8501

## Fonctionnalités
- Carte Folium/OpenStreetMap avec filtre par quartier et zoom automatique.
- Superficies des quartiers mesurées géodésiquement sur WGS84.
- Tableau, graphiques et export CSV.
- Import de données socioéconomiques par quartier avec colonnes obligatoires `quartier,source,annee` et indicateurs optionnels `population,revenu_median`.
- Base de données PostgreSQL/PostGIS optionnelle (voir `docker-compose.yml`, `.env.example` et `sql/`).

Les fichiers `data/quartiers.geojson` et `data/indicateurs_quartiers.csv` ne sont **pas versionnés**. Générer le premier avec l'ETL et fournir uniquement des statistiques réellement établies pour le second. Attention aux limites de l'interpolation entre aires de diffusion et quartiers municipaux. **Aucun modèle prédictif n'est encore entraîné.**

Source : Ville de Québec / Données Québec. Projet expérimental, sans affiliation officielle avec la Ville.

## Déploiement web (Streamlit Community Cloud)

1. Ouvrir https://share.streamlit.io et se connecter avec GitHub.
2. Créer une nouvelle application depuis `Alix09112000/geoinsight-ai`, branche `main`.
3. Sélectionner le fichier d'entrée `app/main.py` puis déployer.
4. L'application télécharge les quartiers au premier démarrage; aucune base externe n'est obligatoire pour la version cartographique.

Lien public attribué après le déploiement, sur un sous-domaine `streamlit.app`.

## Feuille de route provinciale

1. Vue provinciale : polygones des 17 régions administratives depuis le service REST officiel du MRNF (affichage simplifié).\n2. Vue locale : quartiers de la ville de Québec.
3. Intégrer ensuite les limites des MRC et municipalités de la province.
4. Ajouter des indicateurs socioéconomiques harmonisés et leurs métadonnées.
4. Comparer les territoires à échelles comparables, avec estimation des incertitudes.
5. Développer la prédiction spatiale et la validation par blocs spatiaux.

Le périmètre du projet est la **province de Québec**; l’application ne prétend pas encore offrir une couverture provinciale complète.

## Geospatial BI — quartiers de la ville de Québec

La vue « Quartiers de Québec » permet désormais :

- Carte choroplèthe interactive par **population (2021)** ou **densité (hab./km²)**, avec légende et fiches au clic.
- Graphiques par quartier, export CSV des indicateurs et comparaison de deux quartiers.
- Jeu de données de référence `data/indicateurs_quartiers_2021.csv`, chargé automatiquement en l'absence d'un fichier fourni par l'utilisateur. Un CSV déposé dans l'interface prévaut sur le fichier de référence.
- Les superficies sont géodésiques (WGS84) et les densités sont calculées `population / superficie_du_polygone`, qui peut comprendre des plans d'eau.

**Provenance et limites :** les populations par quartier sont les valeurs du jeu de référence saisi pour le Recensement 2021, renvoyant aux [portraits officiels de la Ville de Québec](https://www.ville.quebec.qc.ca/apropos/portrait/quelques_chiffres/quartiers/index.aspx). La somme des populations de quartiers (549 470) diffère de 10 habitants du total municipal publié (549 460), ce qui est compatible avec les règles d'arrondi du recensement. Ces valeurs n'ont pas été contrôlées une à une contre les 35 rapports lors de cette intégration; une validation documentaire complète reste à réaliser avant toute utilisation décisionnelle à enjeu.

Les indicateurs manquants ne sont pas estimés. Les cartes choroplèthes sont descriptives et ne constituent pas des prédictions.

## Carte limitée à la province de Québec

Les vues Région → MRC → Municipalité → Quartier appliquent un **masque extérieur opaque** basé sur l'union des 17 régions administratives officielles du MRNF. Les fonds **Plan** et **Satellite** restent visibles sur le territoire québécois ; les régions limitrophes (Ontario, Nouveau-Brunswick, États-Unis, etc.) sont visuellement masquées. La navigation cartographique est bornée autour du Québec.

Le masque est construit dans `app/quebec_mask.py`, mis en cache quotidiennement dans Streamlit et couvert par `tests/test_quebec_mask.py`. Si le calcul topologique échoue, la carte s'affiche sans fond cartographique plutôt que de montrer les territoires voisins. Les limites simplifiées servent à l'affichage, non à établir des superficies légales.

## Analyse régionale descriptive (nouveau chantier BI)

Dans la vue provinciale, déplier **« 📊 Analyse comparative des 17 régions »** sous la carte :

- Comparer les superficies géodésiques cartographiques estimées des 17 régions et voir le classement graphique.
- Choisir deux régions et afficher l'écart de superficie.
- Exporter les valeurs calculées dans un fichier CSV avec les codes régionaux.
- Les géométries sont celles du service cartographique MRNF, simplifiées et réparées pour le navigateur. Calcul géodésique WGS84 avec anneaux extérieurs/intérieurs orientés correctement.
- Il ne s'agit **pas** de superficies administratives officielles certifiées. Les plans d'eau et simplifications cartographiques modifient les surfaces; aucune population ou statistique économique n'est déduite des seuls polygones.

Les prochains indicateurs (population par région, revenus, emploi, entreprises) seront intégrés uniquement après contrôle de leurs sources, millésimes et correspondances administratives.
