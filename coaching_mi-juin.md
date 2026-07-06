# Coaching mi-juin — DataValueXploring
### Étape roadmap : *« Analyse des résultats, prise de recul, mise en valeur »*

**Projet :** réduire durablement les accidents de la route par la rénovation d'infrastructure.
**Rôle incarné :** agence de voirie / DOT d'une collectivité.
**Données :** *US Accidents* (Kaggle), Feb 2016 → Mar 2023, **7,73 M accidents**, 49 États.
**Date :** 22/06/2026.

---

## 0. Où on en est sur la roadmap

| Jalon | Date prévue | État |
|---|---|---|
| Lancement SAÉ | 22/04 | ✅ |
| Analyse préliminaire (faisable / deuils / spécificité du rôle) | ~08/05 | ✅ |
| Choix techniques + 1ʳᵉ pipeline fonctionnelle | ~24/05 | ✅ |
| **Analyse des résultats, prise de recul, mise en valeur** | **mi-juin** | **◀ nous sommes ici** |
| Livraison & présentation | début juillet | ⏳ |

**Depuis le dernier coaching**, on est passé de « pipeline qui tourne » à **« pipeline qui produit des résultats exploitables, validés et explicables »**, le tout dans **un notebook unique reproductible** (`rendu/notebook.ipynb`) qui s'exécute de bout en bout sans intervention sur les 7,73 M lignes (données auto-téléchargées via `kagglehub`).

---

## 1. Rappel du cadrage (1 min)

On décline le fil rouge *« où et quoi rénover avec un budget limité ? »* en 3 questions :

| Question | Nature | Méthode |
|---|---|---|
| **OÙ** rénover en priorité ? | descriptif | agrégation géospatiale H3 + exposition OSM |
| **QUOI** installer sur place ? | **ML (moteur de preuve)** | modèle de gravité → SHAP → prescription conditionnelle |
| **QUAND** activer des mesures temporaires ? | descriptif | patterns temporels / météo / événements |

> **Principe directeur :** on ne livre **pas** un prédicteur. On entraîne un modèle de gravité **comme microscope** : on l'interroge (SHAP) pour savoir *quels éléments structurels aggravent* → donc *quoi corriger*. **La prédiction est le moyen ; l'explication est le livrable.**

---

## 2. Mise en valeur des résultats

### 2.1 OÙ — le risque est très concentré et **stable dans le temps**
- Sur la Californie (démo) : **1,74 M accidents → 58 857 zones** (H3 rés. 8, ~0,7 km²).
- **Concentration :** les **50 zones prioritaires** (0,08 % des zones) concentrent **5,3 % de la charge** totale → ~**62× leur part équitable**. Rénover quelques zones a un effet de levier réel.
- **Validation de robustesse (nouveau) :** en coupant 2016-2019 vs 2020-2023, la corrélation de rang des scores est **Spearman ρ = 0,776**, et **les 50 zones prioritaires restent toutes dans le top 5 %** sur la 2ᵉ période → le risque est **structurel**, pas du bruit conjoncturel.
- **Exposition OSM** (« dangereux ou juste fréquenté ? ») : pour le top des zones, on récupère la longueur de voirie + nb d'intersections et on calcule **accidents/km**. Le re-classement fait **remonter de vrais points noirs concentrés** masqués par le volume (ex. une zone passe **+11 rangs** après normalisation).

### 2.2 QUOI — modèle de gravité honnête, puis explication
**Comparaison de 5 modèles** (même split temporel, même métrique) — *on ne se fie pas à l'accuracy (trompeuse à 80/20)* :

| Modèle | PR-AUC | ROC-AUC | Rappel « grave » |
|---|---|---|---|
| Dummy (plancher) | 0,064 | 0,500 | 0,00 |
| Régression logistique | 0,110 | 0,635 | 0,63 |
| Arbre de décision | 0,079 | 0,560 | 0,68 |
| Random Forest | 0,115 | 0,646 | 0,63 |
| **HistGradientBoosting** ✅ | **0,125** | **0,676** | 0,57 |

- Tous **battent le plancher** ; meilleur = HistGB (**×2 vs plancher**). Performance **modeste et assumée** : prédire la gravité d'un accident à partir du seul contexte infra/météo/heure est intrinsèquement difficile (vitesse réelle, comportement = absents). **C'est cohérent avec notre thèse : le modèle est un révélateur de leviers, pas un oracle.**
- **Analyse des erreurs (nouveau) :** matrice de confusion + courbes PR. Au seuil 0,5, **44 % des accidents graves sont ratés** (faux négatifs) → on explique l'arbitrage seuil ↔ fausses alertes (un grave raté = un point noir non détecté).
- **Convergence inter-modèles (nouveau) :** logistique, arbre, forêt et SHAP **classent les leviers d'infra dans le même ordre** → diagnostic robuste, indépendant du choix de modèle.

### 2.3 QUAND — des résultats contre-intuitifs (valeur différenciante)
- **Météo :** part de graves dans une fourchette étroite (~16–23 %). **Le brouillard affiche la part la plus basse (16 %)** — à l'opposé du *common knowledge* — probablement par conduite prudente ; pluie/ciel couvert légèrement au-dessus (~22–23 %).
- **Jours fériés :** la sévérité **ne s'emballe pas** (sév. moyenne quasi plate 2,18–2,25) ; **Noël/Nouvel An est même plus bas** (15,5 % vs 19,5 % en période normale).
- **Lecture métier :** la météo et le calendrier relèvent du risque **conjoncturel** → mesures **dynamiques** (panneaux à messages variables), pas la rénovation structurelle. On les **visualise**, on ne les met pas au cœur du modèle.

### 2.4 Synthèse décisionnelle (le livrable pour le décideur)
- `zones_prioritaires.csv` + carte Folium : **par zone**, où + quoi installer + **impact estimé**, **trié par impact** = ordre d'intervention.
- **Recommandations variées** (pas un aménagement unique partout) grâce à l'effet **conditionnel** : sécuriser passage piéton, passage à niveau, stop/cédez, modération de trafic, installer feux… + zones « facteur humain » signalées honnêtement.

---

## 3. Prise de recul — ce qui marche / ce qui ne marche pas

**Ce qui marche**
- Priorisation **objective et défendable** (indépendante des accidents médiatisés).
- **Convergence des preuves** : aléa local (lift descriptif) ↔ contributions SHAP (modèle) ↔ stabilité temporelle.
- L'exposition OSM corrige le biais « beaucoup d'accidents = beaucoup de routes ».

**Ce qui ne marche pas / reste incertain**
- **Pouvoir prédictif modéré** (PR-AUC 0,125) — assumé : on prédit pour expliquer, pas pour prédire.
- **Piège d'interprétation maîtrisé :** en SHAP global, feux/passages/stops ressortent *aggravants* — **artefact de confusion** (ils marquent les carrefours denses). D'où une prescription fondée sur l'**effet conditionnel** `Δ(mesure | aléa local)`, pas l'effet moyen.
- **Zones « diffuses »** sans levier infra dominant → renvoyées au facteur humain (affiché, pas masqué).

**Deuils & limites assumés**
- **Pas de causalité** (pas de panel avant/après) → associations, pas preuves d'efficacité.
- **Biais de reporting** MapQuest/Bing (couverture inégale ; Top 3 États ≈ 41 % du dataset).
- Pas de profil conducteur ni de coût réel (`severity` = seul proxy).
- **Exposition OSM partielle (13/50 zones)** : l'API Overpass nous a throttlés → le reste est classé par volume (dégradation propre, documentée). Coverable plus tard.

---

## 4. Auto-évaluation vs grille critériée

| Compétence | Niveau visé | Appui |
|---|---|---|
| **Concevoir** | **Dépasse** | enjeu → data/ML cadré, arbitrages & deuils explicites, démarche EDA→modèle→validation→valorisation. |
| **Formaliser** | **Dépasse** | valeur actionnable (CSV+carte+impact), EDA riche avec signaux non triviaux. |
| **Produire** | **Attendu solide** | Spark, code factorisé, reproductible, **tests d'intégrité + anti-fuite**, métriques honnêtes, erreurs analysées. *Restes :* tests `pytest`/Docker, OSM complet. |

---

## 5. Prochaines étapes → livraison (début juillet)
1. **OSM complet** sur les 50 zones (quand Overpass coopère) pour une exposition exhaustive.
2. (Bonus « Dépasse » côté Produire) **suite `pytest`** sur fonctions extraites + **Dockerfile** (Java/Spark encapsulés).
3. (Optionnel) **K-fold temporelle** en complément du split unique.
4. Préparer la **soutenance** : dérouler le fil OÙ → QUOI → QUAND + la décision terrain *« que fait le DOT lundi matin »*.

**Question pour le coach :** on a privilégié la **profondeur d'analyse et l'explicabilité** (cœur de la valeur métier) plutôt que l'industrialisation (tests formels / Docker). Est-ce le bon arbitrage au regard des attendus, ou faut-il rééquilibrer vers le volet « Produire » d'ici la livraison ?
