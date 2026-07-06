# Réduire les accidents de la route - pipeline d'aide à la décision (agence de voirie)

Pipeline data **reproductible de bout en bout** qui, à partir du jeu *US Accidents*, dit à une agence de
voirie **où** rénover en priorité, **quoi** y installer, et avec **quel impact estimé** - chaque choix
méthodologique étant explicitement justifié.

> **Rôle incarné :** agence de voirie / DOT d'une collectivité territoriale.
> **But métier :** réduire durablement les accidents par la rénovation structurelle, avec un budget limité.

---

## Ce que produit la pipeline

- `zones_prioritaires.csv` - les zones à rénover, triées par **impact estimé**, avec pour chacune : volume
  d'accidents, charge pondérée gravité, exposition (km de voirie), aléa local dominant, équipement déjà
  présent, **aménagement recommandé**.
- `carte_zones_prioritaires.html` - carte interactive (Folium) : pastilles dimensionnées par le risque réel,
  colorées par type d'aménagement recommandé.

## Principe méthodologique clé

On **ne livre pas un prédicteur de gravité**. On entraîne un modèle de gravité **comme moteur de preuve** :
on vérifie qu'il prédit honnêtement (vraie métrique, validation temporelle), puis on l'**interroge** -
**odds ratios ajustés** (rég. logistique, IC 95 %) et **g-computation** (effets en points de probabilité,
confondants contrôlés) - pour identifier *quels éléments d'infrastructure aggravent les accidents -> donc
quoi corriger* (SHAP conservé en contrôle de robustesse).
**La prédiction est le moyen ; l'explication est le livrable.**

## Architecture

```
Setup -> Chargement (schéma explicite) -> Nettoyage explicite & défensif
   ├─ A. EDA / Visualisation (volumétrie, biais, sévérité, « QUAND »)
   ├─ B. OÙ   : scoring géospatial H3 + exposition routière OSM -> zones prioritaires
   ├─ C. QUOI : modèle de gravité (Dummy -> LogReg -> Arbre -> RandomForest -> GBT)
   │            métrique honnête (PR-AUC, rappel) + split temporel
   │            -> effets ajustés : odds ratios (IC 95%) + g-computation -> leviers
   │            (SHAP conservé comme contrôle de robustesse)
   ├─ D. Synthèse décisionnelle (par zone : où + quoi + impact estimé)
   └─ E. Analyse critique & recul (ce qui marche / ne marche pas, limites, périmètre)
```

## Prérequis

- **Python 3.12**
- **Java 11+** (JDK ; testé sur Java 21) - requis par PySpark
- ~4 Go d'espace disque pour le dataset (téléchargé automatiquement au 1er run)
- Accès réseau au 1er run (téléchargement Kaggle + requêtes OSM ; l'exposition OSM est
  désactivable via `RUN_OSM_EXPOSURE=False` pour un fonctionnement hors-ligne)

## Lancer

```bash
pip install -r requirements.txt
jupyter notebook notebook.ipynb     # puis « Run All »
```

### Ou via Docker (Java + Spark encapsulés, zéro prérequis local)

```bash
docker build -t xploring-rendu .
docker run --rm -m 10g -v "$PWD/out:/app/out" xploring-rendu
# -> notebook exécuté + CSV + carte déposés dans ./out
```

## Protocole de tests

Deux niveaux de validation :
1. **Dans le notebook** : tests d'intégrité du nettoyage + tests anti-fuite du pipeline ML
   (assertions bloquantes - le run s'arrête si les données sont mal préparées).
2. **Sur le livrable** (`tests/`, pytest) : notebook valide et exécuté sans erreur, invariants
   métier du CSV décisionnel (rangs, charge, sévérité, impacts ≥ 0, recommandations variées),
   versions figées, artefacts présents.

```bash
pytest -v tests/
```

Le notebook s'exécute **sans aucune intervention** : les données sont téléchargées automatiquement
(`kagglehub`, ou un CSV local s'il est présent), les graines aléatoires sont fixées, tous les seuils sont des
constantes nommées en tête de notebook.

### Options utiles (constantes en tête du notebook)

| Constante | Effet |
|---|---|
| `STATE` | territoire analysé (défaut `"CA"`). **Le changer suffit à rejouer toute l'analyse ailleurs** -> preuve de généricité. |
| `RUN_OSM_EXPOSURE` | `True/False` - l'exposition OSM nécessite le réseau ; passer à `False` rend le notebook exécutable **hors-ligne** (classement par volume conservé). |
| `MAX_MODEL_ROWS` | plafond de lignes pour la comparaison de modèles (compromis repro/coût ; `None` = tout le dataset). |
| `GRAVE_THRESHOLD` | seuil de la cible binaire (défaut : sévérité ≥ 3 = « grave »). |

## Généricité

Le modèle est **entraîné sur l'ensemble des États-Unis** (le code est agnostique au territoire) ; la
**Californie sert de démonstration** (fort volume, diversité urbain/rural). Toute la logique est paramétrée :
aucun choix n'est codé en dur pour la CA au-delà de la variable `STATE`.

## Justifications & documentation

- **`notebook.ipynb`** - chaque étape est précédée d'un bloc markdown qui dit *pourquoi* (choix de nettoyage,
  de features, de métrique, de modèle).
- **`CLAUDE.md`** - cahier des charges complet : justification approfondie de l'ensemble des choix
  méthodologiques, deuils & hypothèses, et checklist de conformité.

## Limites assumées (« deuils »)

Résultats **corrélationnels, pas causaux** (pas de panel avant/après) , biais de reporting (couverture
inégale) , pas de profil conducteur ni de coût réel (`severity` = seul proxy) , univers = lieux déjà
accidentogènes. Détail et périmètre d'usage dans la partie E du notebook et dans `CLAUDE.md`.
