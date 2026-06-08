# Design — Modèle d'attribution des zones à rénover (nb3)

**Date :** 2026-06-08
**Rôle incarné :** DOT / voirie d'une collectivité territoriale
**Livrable concerné :** Notebook `03_modele_attribution.ipynb` + alimentation du rapport L1
**Statut :** validé (brainstorming), à implémenter

---

## 1. Problème métier

> « Sur quelles zones du territoire concentrer nos prochaines rénovations, et **quel élément** y traiter en priorité ? »

Le DOT n'a pas un budget infini. Il doit (a) choisir **où** intervenir, et (b) savoir **quoi** corriger sur place (équiper un carrefour ? sécuriser un passage ? revoir une bretelle ?). Aujourd'hui cette priorisation est réactive (remontées terrain, accidents médiatisés). On apporte une priorisation **data-driven et explicable**.

## 2. Logique de la pipeline (2 temps)

L'unité d'analyse n'est **pas l'accident** mais la **zone** (cellule H3, résolution 8–9, équi-surface → un comptage par cellule est déjà une densité comparable).

### Étape 1 — Sélection structurelle par le volume *(déjà faite, `02_points_noirs.ipynb`)*
Ranking des cellules H3 par **charge d'accidents pondérée par la gravité**. Justification métier : un fort volume d'accidents au même endroit traduit un problème **structurel** (géométrie, équipement) ; un accident grave isolé dans une zone calme relève plutôt de l'**erreur humaine ponctuelle**, hors du levier d'action du DOT. On filtre donc par le volume (pondéré gravité), pas par la gravité seule.

### Étape 2 — Attribution *(chantier neuf, `03_modele_attribution.ipynb`)*
Pour chaque zone retenue, identifier l'élément d'infrastructure responsable, via **deux méthodes qui doivent raconter la même histoire** :
- **2A — Sur-représentation (descriptif)** : lift de chaque élément vs référence nationale.
- **2B — Modèle de fréquence + SHAP (ML)** : modèle de charge au niveau zone, expliqué localement.

La **convergence 2A ↔ 2B** est elle-même un résultat (cf. §6).

## 3. Pondération par la gravité (transversal)

Chaque accident contribue un **poids = sa sévérité** (échelle 1→4). Partout où on parlait de « nombre d'accidents », on utilise la **charge pondérée** :

```
charge_zone = Σ_{accidents de la zone} severity
```

S'applique à l'étape 1 (déjà : `risk_score ≈ count × avg_severity`), à la cible du modèle 2B, et aux parts de l'étape 2A — pour que les trois soient cohérents et comparables. La pipeline répond ainsi à : *« quel élément génère le plus de charge d'accidents pondérée par la gravité dans cette zone ? »*

## 4. Données & périmètre des « éléments »

- **Source :** US Accidents (Feb 2016 → Mar 2023), 7,73 M lignes. Chargement reproductible via `kagglehub` (comme nb2).
- **Périmètre géo :** modèle entraînable sur tout le US ; **démonstration sur la Californie** (1,74 M lignes, diversité urbain/rural).
- **Éléments candidats = infrastructure uniquement** : `junction`, `crossing`, `stop`, `traffic_signal`, `railway`, `station`, `roundabout`, `bump`, `give_way`, `no_exit`, `traffic_calming`, `amenity`.
- **Exclusion assumée :** météo / heure / luminosité **hors scope de l'attribution**. Raison : on répond à une question de **rénovation structurelle** — on ne rénove pas la pluie. Le risque conjoncturel (mesures dynamiques) est un sujet distinct, non traité ici.

## 5. Méthodes

### 5A — Sur-représentation (lift)
Pour chaque zone prioritaire et chaque élément :
```
lift(élément, zone) = part_pondérée_de_l_élément_dans_la_zone
                      ─────────────────────────────────────────
                      part_pondérée_de_l_élément_au_niveau_national
```
L'élément au lift le plus élevé = suspect dominant. Lisible par un décideur, robuste, difficilement attaquable. Sortie : par zone, le top-élément et son lift.

### 5B — Modèle de fréquence au niveau zone + SHAP
- **Échantillons :** cellules H3 ayant ≥ 1 accident (cf. limite §7).
- **Cible :** `charge_zone` (Σ sévérité) — régression de comptage.
- **Features :** composition infra de la cellule (counts/proportions des éléments) **+ une variable de contrôle de densité** (nb de segments routiers / volume total de la cellule) pour distinguer « junction dangereux » de « simplement beaucoup de routes ».
- **Modèle :** Gradient Boosted Trees (Spark MLlib `GBTRegressor`) — robuste, scalable sur 7,73 M lignes, importances interprétables. RandomForest en repli.
- **Explication :** **SHAP local par zone** → quel élément pousse le plus la charge prédite *de cette zone-là* (pas seulement l'importance globale). Si SHAP indisponible nativement côté Spark, on extrait les features de zone et on applique SHAP via un modèle sklearn équivalent sur l'échantillon agrégé.

## 6. Validation

- **Métrique 2B** : split d'évaluation (held-out), RMSE / MAE sur la charge prédite + R². (Split temporel possible : train < 2022, test 2022–23.)
- **Convergence 2A ↔ 2B** : pour chaque zone, l'élément dominant de A et le driver SHAP de B coïncident-ils ?
  - **Accord** → narratif solide, double preuve.
  - **Désaccord** → signal que l'exposition fausse l'un des deux ; on le documente comme résultat (et non comme bug).
- **Stabilité** : réutiliser l'approche de validation déjà présente dans nb2 (`validation_stabilite.png`) — robustesse du classement aux variations de résolution/échantillon.

## 7. Limite assumée (« deuils »)

Sans données d'exposition externes (réseau OSM, trafic AADT), l'univers du modèle 2B = cellules ayant **déjà ≥ 1 accident**. Le modèle explique donc *« parmi les lieux accidentogènes, quelle composition fait monter la charge »*, et non *« junction vs carrefour parfaitement sûr »*. C'est **cohérent avec l'étape 1** (on ne s'intéresse qu'aux zones à fort volume), mais doit être énoncé honnêtement dans le rapport. L'extension OSM (vrai taux par exposition) est identifiée comme amélioration future, hors scope de cette itération.

## 8. Livrable

Pour chaque zone prioritaire (carte + tableau exporté CSV) :

| Rang | Cellule H3 | Charge pondérée | Nb accidents | Sév. moy. | Élément dominant (2A) | Lift | Driver SHAP (2B) | Accord A/B |
|---|---|---|---|---|---|---|---|---|

Plus : feature importance globale du modèle, et carte Folium des zones colorées par élément dominant. Alimente directement le rapport L1 (reformulation problème → démarche → valeur → limites).

## 9. Sortie & intégration

- Notebook `03_modele_attribution.ipynb` auto-suffisant (kagglehub + `%pip install`, comme nb2), exécutable de bout en bout sans erreur.
- Export CSV des zones attribuées + carte HTML.
- Section dédiée du rapport L1 reprenant §1, §2, §3, §6, §7.
```
