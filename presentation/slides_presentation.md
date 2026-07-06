# Présentation finale - DataValueXploring (20 min + Q&A)

> Contenu prêt à monter dans PowerPoint / Google Slides.
> Chaque slide : **titre**, **contenu**, **visuel** (fichier dans `assets/`), **notes orateur**, **timing**.
> Rythme : ~14 slides pour 20 min ≈ 1 min 25 / slide. Les slides A1–A4 en annexe pour le Q&A.

---

## Slide 1 - Titre *(30 s)*
**Réduire les accidents par la rénovation d'infrastructure**
*Pipeline d'aide à la décision pour une agence de voirie - données US Accidents (7,73 M accidents)*
- Équipe, date
- **Visuel :** screenshot de la carte (`assets/carte_zones_prioritaires.html` ouvert dans un navigateur, zoom Los Angeles)

**Notes :** une phrase d'accroche : « Un gestionnaire de voirie a un budget limité et des milliers de carrefours. On lui dit lesquels rénover, quoi y installer, et ce que ça devrait rapporter. »

---

## Slide 2 - Le problème métier *(1 min 30)*
**« Où et quoi rénover, avec un budget de travaux limité ? »**
- Rôle incarné : **agence de voirie / DOT** d'une collectivité
- Aujourd'hui : priorisation **réactive** (accidents médiatisés, remontées terrain)
- Notre apport : priorisation **data-driven, explicable, défendable**
- Périmètre d'action : **l'infrastructure** (feux, passages, stops, modération) - pas la météo, pas le conducteur

**Notes :** insister sur le choix du rôle = ce qui rend le projet actionnable vs analyses génériques (« la pluie est dangereuse » n'aide personne à décider).

---

## Slide 3 - Les données (et leurs pièges) *(1 min 30)*
**US Accidents (Kaggle) - Feb 2016 -> Mar 2023**
- **7,73 M accidents**, 46 colonnes, 49 États
- Collecte via API trafic (MapQuest/Bing) -> **biais de reporting assumé** : peu de lignes ≠ peu d'accidents
- Top 3 États ≈ 41 % du volume -> on ne compare jamais les États entre eux, on raisonne **à l'intérieur** d'un territoire
- **Visuel :** `assets/02_a1_couverture_biais…png` (top 15 États)

**Notes :** montrer qu'on connaît les limites de nos données AVANT de montrer des résultats - crédibilité.

---

## Slide 4 - Le cadrage : 3 questions, 3 natures *(2 min)*
| Question | Nature | Méthode |
|---|---|---|
| **OÙ** rénover ? | descriptif | agrégation H3 + exposition OSM |
| **QUOI** installer ? | **ML - moteur de preuve** | modèle de gravité -> SHAP -> prescription |
| **QUAND** agir temporairement ? | descriptif | patterns temporels/météo |

**Le principe clé : la prédiction est le moyen, l'explication est le livrable.**
- On n'utilise PAS de ML là où l'agrégation suffit (« OÙ ») - pas de modèle « par habitude »
- On entraîne un modèle de gravité **pour l'interroger** (quels éléments aggravent -> quoi corriger)

**Notes :** c'est LA slide méthodo. Anticiper la question « pourquoi un prédicteur si vous ne prédisez pas ? » -> 1) tâche évaluable (métriques honnêtes), 2) contrôle des confondants, 3) la convergence entre modèles devient une preuve de robustesse.

---

## Slide 5 - Architecture de la pipeline *(1 min)*
```
Setup -> Chargement (Spark, schéma explicite) -> Nettoyage explicite & testé
  ├─ A. EDA (volumétrie, biais, sévérité, « QUAND »)
  ├─ B. OÙ   : scoring H3 + exposition OSM -> zones prioritaires
  ├─ C. QUOI : 5 modèles comparés -> SHAP -> leviers
  ├─ D. Synthèse décisionnelle (où + quoi + impact estimé)
  └─ E. Analyse critique
```
- **PySpark** pour les 7,73 M lignes (pandas saturerait) ; pandas/sklearn une fois le volume réduit
- **Run All sans intervention** : données auto-téléchargées, seeds fixés, versions figées, Docker fourni

**Notes :** mentionner les tests (intégrité + anti-fuite dans le notebook, pytest sur le livrable).

---

## Slide 6 - OÙ : le risque est très concentré *(1 min 30)*
- Californie (démo - le code est générique, variable `STATE`) : **1,74 M accidents -> 58 857 zones** H3 (~0,7 km², l'échelle d'un carrefour)
- **50 zones (0,08 %) = 5,3 % de la charge totale** -> **62× leur part équitable**
- Rénover quelques carrefours a un effet de levier disproportionné
- **Visuel :** `assets/08_b_où_rénover…png` (courbe de concentration + scatter volume×gravité)

**Notes :** « charge » = Σ sévérités = volume pondéré par la gravité. 100 accidents légers ≠ 100 graves.

---

## Slide 7 - OÙ : deux validations qui rendent le classement défendable *(2 min)*
**1. Stabilité temporelle** - les points noirs sont-ils du bruit ?
- Scores recalculés sur 2016-2019 vs 2020-2023 : **Spearman ρ = 0,776**
- **Les 50 zones prioritaires restent toutes dans le top 5 %** -> risque **structurel**, pas conjoncturel
- **Visuel :** `assets/09_b2_validation…png`

**2. Exposition routière (OSM)** - dangereux, ou juste fréquenté ?
- Longueur de voirie par zone -> **accidents/km** -> re-classement
- Exemple réel : une zone gagne **+11 rangs** une fois normalisée = point noir concentré masqué par le volume

**Notes :** anticiper « pourquoi H3 ? » -> cellules équi-surface (un comptage = une densité comparable), résolution 8 = échelle carrefour.

---

## Slide 8 - QUOI : comparaison honnête de 5 modèles *(2 min)*
| Modèle | PR-AUC | ROC-AUC | Rappel « grave » |
|---|---|---|---|
| Dummy (plancher) | 0,064 | 0,500 | 0,00 |
| Régression logistique | 0,110 | 0,635 | 0,63 |
| Arbre de décision | 0,079 | 0,560 | 0,68 |
| Random Forest | 0,115 | 0,646 | 0,63 |
| **HistGradientBoosting** OK : | **0,125** | **0,676** | 0,57 |

- **Pas d'accuracy** (à 80/20, prédire « non-grave » partout = 80 % sans rien apprendre)
- **Split temporel** (train < 2022, test 2022-23) : on prédit l'avenir avec le passé
- Tous battent le plancher ; HistGB = **×2 vs plancher**

**Notes :** performance modeste **assumée** : la gravité dépend de facteurs absents (vitesse réelle, alcool). Notre critère de succès n'est pas la perf brute mais la fiabilité de l'explication. Anticiper « pourquoi pas SMOTE ? » -> class_weight, on ne fabrique pas de données.

---

## Slide 9 - QUOI : les effets ajustés (la réponse claire) *(2 min)*
**Deux lectures indépendantes, même question : « effet net de chaque équipement, à contexte égal ? »**
- **Odds ratios** (rég. logistique + IC 95 %) : passage piéton OR≈0,41 , stop OR≈0,27 , feux OR≈0,39
  -> **protecteurs, significatifs** ; carrefour OR≈1,2 , voie ferrée OR≈1,7 -> **aggravants**
- **G-computation** (modèle non-linéaire) : « éteindre/allumer » l'équipement à contexte constant ->
  passage piéton **−20 pts** de probabilité de gravité, stop **−19 pts**…
- **Concordance des deux lectures : 10/12 équipements** -> diagnostic robuste
- **Visuels :** `assets/11_c3_effets_ajustés…png` (forest plot OR) + `assets/12_c3_effets_ajustés…png` (barres g-computation)

**Notes :** insister : une moyenne brute « avec/sans feux » dirait l'inverse (les feux sont là où c'est dense) - les effets **ajustés** renversent la lecture. C'est LA valeur du modèle : contrôler les confondants. SHAP conservé en annexe comme 3ᵉ contrôle de robustesse - expliquer si question : requête d'intervention (g-comp) ≠ requête d'attribution (SHAP), les signes peuvent différer, c'est documenté.

---

## Slide 10 - QUOI : de l'explication à la prescription *(1 min 30)*
**Par zone prioritaire :**
```
aléa local dominant (lift)            ex. « junction » sur-représenté ×2,3
× mesure protectrice MANQUANTE        ex. pas de stop dans la zone
× efficace QUAND cet aléa est présent Δ_ajusté(stop | junction) = −19,9 pts (modèle, confondants contrôlés)
-> recommandation + impact estimé = |Δ_ajusté| × volume = accidents GRAVES potentiellement évités
```
Exemple réel : zone #2 (2 543 accidents, aléa carrefour) -> « stop / cédez-le-passage », **≈ 505 graves évités** (ex-ante)
- Résultat : recommandations **variées et locales** (passage piéton, stop, modération, feux, passage à niveau…)
- Les zones sans levier infra -> « **investiguer facteur humain** » (affiché honnêtement, pas masqué)

**Notes :** anticiper « c'est causal ? » -> NON, associations. L'impact est ex-ante, sert à **prioriser**. La mesure réelle = pilote + différence de différences (slide 13).

---

## Slide 11 - QUAND : les contre-intuitifs *(1 min 30)*
- **Le brouillard a la part d'accidents graves la plus basse (16 %)** - comme le temps clair ; pluie/couvert ~22-23 %
- **Les fêtes ne s'emballent pas** : Noël/Nouvel An = 15,5 % de graves vs 19,5 % en période normale
- Lecture : météo/calendrier = risque **conjoncturel** -> mesures **dynamiques** (panneaux), pas du béton
- **Visuels :** `assets/06_a3_quand…png` (météo) + `assets/07_a4_quand…png` (fêtes)

**Notes :** la valeur différenciante = contredire le common knowledge avec des données. Hypothèse brouillard : conduite plus prudente. On le dit comme hypothèse, pas comme fait.

---

## Slide 12 - Le livrable décisionnel *(1 min 30)*
**Ce que le DOT ouvre lundi matin :**
- `zones_prioritaires.csv` : 50 zones **triées par impact estimé** = ordre d'intervention
- Carte interactive : couleur = aménagement recommandé, taille = risque réel (par km)
- **Visuel :** screenshot carte + extrait du tableau (3-4 lignes du CSV)

**Exemple concret :** « Zone #1 - 2 861 accidents, aléa dominant = carrefour, passage piéton absent -> sécuriser le passage piéton, impact estimé ≈ … »

**Notes :** c'est ici que la valeur métier devient palpable. Une ligne du CSV = une décision de travaux argumentée.

---

## Slide 13 - Limites & recul *(1 min 30)*
**Ce qu'on ne prétend PAS :**
- **Pas de causalité** (pas d'avant/après installation) -> signaux de priorisation, pas preuves d'efficacité
- Biais de reporting, pas de profil conducteur, `severity` = seul proxy du coût
- Exposition OSM partielle (top zones ; API Overpass instable - cache local fourni)

**Comment mesurer l'impact réel (perspective) :**
- Pilote 5-10 zones + **différence de différences** (traitées vs témoins, avant/après)
- KPI : accidents graves évités, **coût par accident grave évité**

**Notes :** annoncer les limites nous-mêmes = crédibilité. La grille valorise explicitement « deuils énoncés ».

---

## Slide 14 - Conclusion : la valeur créée *(1 min)*
> **On transforme un budget limité en liste d'interventions priorisée, justifiée et explicable.**
- **OÙ** : 50 zones validées (concentration ×62, stabilité ρ=0,78, exposition)
- **QUOI** : aménagement adapté par zone + impact estimé
- **QUAND** : mesures dynamiques vs travaux - bien séparés
- Reproductible de bout en bout : Run All, tests, versions figées, Docker

**Notes :** finir sur « que fait le DOT lundi matin » et ouvrir sur le pilote terrain.

---
---

# Annexes (à garder après la slide de fin, pour le Q&A)

## Annexe A - Nettoyage & prétraitement
- **Visuel :** `assets/01_a0_valeurs_manquantes…png`
- Tableau des décisions : end_lat/lng abandonnés (44 % NA), wind_chill supprimé (redondant), imputation médiane, booléens NA=absent, binarisation sévérité (classe 2 = 80 %)

## Annexe B - Sévérité selon l'infrastructure (descriptif)
- **Visuel :** `assets/04_a2bis_sévérité…png` - le signal descriptif qui recoupe le SHAP

## Annexe C - Analyse des erreurs du modèle
- **Visuel :** `assets/10_c2bis_analyse_des_erreurs…png` (matrice de confusion + courbes PR)
- Au seuil 0,5 : 44 % des graves ratés -> arbitrage seuil <-> fausses alertes

## Annexe D - Entrées du modèle
- 12 booléens d'infra (leviers interprétés) + contrôles (météo num., heure/jour/mois, bucket météo, État, nuit)
- Anti-fuite : ni severity ni grave dans les features (testé par assertion)

---

# Questions du jury à anticiper (préparer les réponses à l'oral)

1. **« Pourquoi un modèle si vous ne voulez pas prédire ? »** -> tâche évaluable + contrôle des confondants + convergence = preuve. Le modèle est un microscope.
2. **« PR-AUC 0,125 c'est faible, non ? »** -> ×2 vs plancher = signal réel ; la perf absolue est bornée par les variables absentes (vitesse, alcool) ; notre livrable est l'explication, validée par convergence + stabilité.
3. **« C'est causal ? »** -> Non, associationnel, assumé. Protocole diff-in-diff proposé pour la suite.
4. **« Pourquoi binaire et pas multiclasse ? »** -> classe 2 = 80 %, métriques illisibles en multiclasse ; binaire = message décisionnel clair.
5. **« Pourquoi Spark ? »** -> 7,73 M lignes ; agrégations/split en Spark, sklearn sur échantillon (800k) car SHAP ne scale pas ; MLlib mentionné comme alternative.
6. **« Une moyenne brute dit que les feux aggravent ?! »** -> oui, artefact de confusion (les feux marquent les carrefours denses). Les effets **ajustés** (OR + g-computation, confondants contrôlés) renversent la lecture : les équipements régulateurs sont protecteurs. C'est LA démonstration de l'utilité du modèle vs une simple moyenne.
7. **« Ça marche ailleurs qu'en Californie ? »** -> oui : entraînement US entier, `STATE` paramétrable, rien de codé en dur.
8. **« Comment vous testez ? »** -> 3 niveaux : assertions dans le notebook (intégrité + anti-fuite), pytest sur le livrable (invariants métier du CSV), Run All reproductible (+ Docker).
