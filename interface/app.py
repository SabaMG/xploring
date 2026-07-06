# -*- coding: utf-8 -*-
"""Interface interactive — DataValueXploring.

Pensée pour l'utilisateur MÉTIER (ingénieur voirie / décideur) : où intervenir,
quoi installer, avec quel gain attendu — et un onglet technique pour l'analyste.

Lancer :  streamlit run interface/app.py
Prérequis : python interface/prepare_data.py  (une fois, génère interface/data/)
"""
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

INFRA = ["junction", "crossing", "stop", "traffic_signal", "railway", "station",
         "roundabout", "bump", "give_way", "no_exit", "traffic_calming", "amenity"]
INFRA_FR = {"junction": "carrefour", "crossing": "passage piéton", "stop": "stop",
            "traffic_signal": "feux", "railway": "passage à niveau", "station": "station",
            "roundabout": "rond-point", "bump": "dos d'âne", "give_way": "cédez-le-passage",
            "no_exit": "impasse", "traffic_calming": "modération trafic", "amenity": "équipement public"}
WEATHER_NUM = ["temperature_f", "humidity_pct", "visibility_mi", "wind_speed_mph", "pressure_in"]
NUM_CONTROLS = WEATHER_NUM + ["hour", "dow", "month"]
CAT_CONTROLS = ["weather_bucket", "state", "is_night"]
ALL_FEATURES = INFRA + NUM_CONTROLS + CAT_CONTROLS
DEPLOYABLE = ["traffic_signal", "crossing", "stop", "traffic_calming"]
RECO_LABEL = {"traffic_signal": "Installer des feux",
              "crossing": "Sécuriser un passage piéton",
              "stop": "Poser stop / cédez-le-passage",
              "traffic_calming": "Modération de trafic (ralentisseurs)"}
RECO_COLOR = {"Installer des feux": "#e67e22",
              "Sécuriser un passage piéton": "#2ecc71",
              "Poser stop / cédez-le-passage": "#3498db",
              "Modération de trafic (ralentisseurs)": "#9b59b6",
              "Sécuriser le passage à niveau": "#e74c3c",
              "Investiguer facteur humain (vitesse/contrôles)": "#7f8c8d",
              "Déjà équipé — étude géométrie/abords": "#34495e"}
ALGOS = {
    "HistGradientBoosting": "Le plus précis (recommandé) — capte les interactions complexes",
    "LogisticRegression":   "Le plus lisible — chaque équipement a un coefficient interprétable",
    "RandomForest":         "Robuste — bon compromis précision / stabilité",
    "DecisionTree":         "Règles simples — entièrement transparent, moins précis",
}
SEED = 42

STATE_NAMES = {
    "AL": "Alabama", "AR": "Arkansas", "AZ": "Arizona", "CA": "Californie",
    "CO": "Colorado", "CT": "Connecticut", "DC": "District de Columbia",
    "DE": "Delaware", "FL": "Floride", "GA": "Géorgie", "IA": "Iowa",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiane", "MA": "Massachusetts", "MD": "Maryland",
    "ME": "Maine", "MI": "Michigan", "MN": "Minnesota", "MO": "Missouri",
    "MS": "Mississippi", "MT": "Montana", "NC": "Caroline du Nord",
    "ND": "Dakota du Nord", "NE": "Nebraska", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "Nouveau-Mexique", "NV": "Nevada",
    "NY": "New York", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvanie", "RI": "Rhode Island", "SC": "Caroline du Sud",
    "SD": "Dakota du Sud", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VA": "Virginie", "VT": "Vermont", "WA": "État de Washington",
    "WI": "Wisconsin", "WV": "Virginie-Occidentale", "WY": "Wyoming",
}
def state_label(c):
    return "États-Unis (entier)" if c == "US" else f"{STATE_NAMES.get(c, c)} ({c})"

st.set_page_config(page_title="DataValueXploring — aide à la décision voirie", layout="wide")

def make_map(cells):
    """Carte folium PRÉ-CENTRÉE sur les cellules H3 (centre+zoom calculés en Python,
    indépendamment du JS) — évite la vue monde quand Leaflet s'initialise mal."""
    import math
    import h3 as _h3
    import folium
    pts = []
    for c in cells:
        try:
            pts.append(list(_h3.cell_to_latlng(c)))
        except Exception:
            pass
    if pts:
        las = [q[0] for q in pts]; lns = [q[1] for q in pts]
        center = [(min(las) + max(las)) / 2, (min(lns) + max(lns)) / 2]
        span = max(max(las) - min(las), (max(lns) - min(lns)) * 0.8, 0.05)
        zoom = int(max(5, min(12, math.log2(360 / span))))
        m = folium.Map(location=center, zoom_start=zoom, tiles="CartoDB positron")
    else:
        m = folium.Map(tiles="CartoDB positron")
    return m, pts

def fix_map_in_tab(m, pts):
    """Corrige l'initialisation Leaflet dans un onglet caché (taille 0 -> vue monde) :
    invalide la taille et recadre sur les points, plusieurs fois après le chargement."""
    import folium
    if not pts:
        return
    lats = [p_[0] for p_ in pts]; lngs = [p_[1] for p_ in pts]
    bounds = [[min(lats), min(lngs)], [max(lats), max(lngs)]]
    m.get_root().html.add_child(folium.Element(
        f"<script>var _n=0;var _t=setInterval(function(){{try{{"
        f"{m.get_name()}.invalidateSize();"
        f"{m.get_name()}.fitBounds({bounds});"
        f"}}catch(e){{}} if(++_n>20) clearInterval(_t);}},600);</script>"))


# ----------------------------------------------------------------- chargement
@st.cache_data(show_spinner="Chargement des données préparées…")
def load_data():
    need = ["accidents_sample.parquet", "zones.parquet", "quand_hour.parquet",
            "quand_weather.parquet", "quand_month.parquet"]
    missing = [f for f in need if not os.path.exists(os.path.join(DATA, f))]
    if missing:
        st.error(f"Artefacts manquants ({missing}). Lancer d'abord : "
                 "`python interface/prepare_data.py`")
        st.stop()
    return (pd.read_parquet(os.path.join(DATA, "accidents_sample.parquet")),
            pd.read_parquet(os.path.join(DATA, "zones.parquet")),
            {d: pd.read_parquet(os.path.join(DATA, f"quand_{d}.parquet"))
             for d in ["hour", "weather", "month"]},
            pd.read_parquet(os.path.join(DATA, "zones_year.parquet")),
            pd.read_parquet(os.path.join(DATA, "quand_year.parquet")))

sample, zones, quand, zones_year, quand_year = load_data()

def _span_years(state_key):
    """Durée couverte par les données (années), estimée par les mois observés."""
    d = sample if state_key is None else sample[sample["state"] == state_key]
    return max(d.groupby(["year", "month"]).size().shape[0] / 12.0, 1e-9)
STATES = ["US"] + sorted(zones["state"].dropna().unique().tolist())

# ----------------------------------------------------------------- sidebar
st.sidebar.title("DataValueXploring")
st.sidebar.caption("Aide à la décision : **où** rénover, **quoi** installer, "
                   "avec quel **gain attendu**.")

code = st.sidebar.selectbox("Territoire analysé", STATES, format_func=state_label,
                            index=STATES.index("CA") if "CA" in STATES else 0)
STATE = None if code == "US" else code
etat = state_label(code)

st.sidebar.divider()
st.sidebar.subheader("Moteur d'analyse (modèle)")
model_name = st.sidebar.selectbox(
    "Méthode", list(ALGOS), format_func=lambda k: ALGOS[k].split(" — ")[0],
    help="\n\n".join(f"**{k}** : {v}" for k, v in ALGOS.items()))
st.sidebar.caption(ALGOS[model_name])
with st.sidebar.expander("Quelle méthode choisir ?"):
    st.markdown(
        "- **Pour décider** (plan d'action) : gardez *HistGradientBoosting* — le plus précis, "
        "donc les effets ajustés les plus fiables.\n"
        "- **Pour expliquer** à un élu : la *régression logistique* donne des coefficients lisibles.\n"
        "- **Le point clé** : si plusieurs méthodes désignent les **mêmes équipements**, "
        "la recommandation est robuste — testez-en deux !")

train_scope = st.sidebar.radio("Entraîné sur", ["US entier (générique)", "Ce territoire uniquement"],
    help="Le modèle générique (recommandé) apprend sur tout le pays et s'applique partout ; "
         "le modèle local capte les spécificités du territoire mais avec moins de données.")

use_zone_hist = st.sidebar.toggle(
    "Historique du lieu (mode ciblage)", value=False,
    help="Ajoute le taux de graves passé de chaque zone comme variable. "
         "Améliore nettement le CIBLAGE (×1,7  ×2,1 vs plancher) mais peut DILUER "
         "l'attribution des effets aux équipements (l'historique contient déjà leur effet). "
         "Désactivé = configuration identique au notebook de référence et au pipeline CLI.")

with st.sidebar.expander("Réglages avancés (analyste)"):
    max_rows = st.slider("Lignes d'entraînement max", 50_000, 800_000, 300_000, 50_000)
    threshold = st.slider("Seuil de décision « grave »", 0.05, 0.95, 0.50, 0.05)
    balanced = st.checkbox("class_weight='balanced'", value=True)
    if model_name == "HistGradientBoosting":
        # défauts issus du sweep : mode notebook -> 300/0.1 (optimal à bruit près, cohérent
        # avec le rendu) ; mode ciblage (historique du lieu) -> 800/0.05 (PR-AUC 0.184 vs 0.179)
        hp = {"max_iter": st.slider("max_iter", 100, 1000, 800 if use_zone_hist else 300, 50),
              "learning_rate": st.select_slider("learning_rate", [0.01, 0.03, 0.05, 0.1, 0.2],
                                                0.05 if use_zone_hist else 0.1)}
    elif model_name == "RandomForest":
        hp = {"n_estimators": st.slider("n_estimators", 50, 400, 200, 50),
              "max_depth": st.select_slider("max_depth", [6, 10, 14, 18, 24], 18),
              "min_samples_leaf": st.select_slider("min_samples_leaf", [1, 5, 20, 50], 20)}
    elif model_name == "DecisionTree":
        hp = {"max_depth": st.select_slider("max_depth", [3, 4, 6, 8, 10, 14], 6)}
    else:
        hp = {"C": st.select_slider("C (inverse régularisation)", [0.01, 0.1, 1.0, 10.0], 1.0)}

# ----------------------------------------------------------------- entraînement
@st.cache_resource(show_spinner="Entraînement du modèle…")
def train(model_name, hp_tuple, balanced, scope_state, max_rows, zone_hist=False):
    from sklearn.compose import ColumnTransformer
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler, OneHotEncoder
    from sklearn.linear_model import LogisticRegression
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
    from sklearn.metrics import average_precision_score, roc_auc_score
    from sklearn.utils.class_weight import compute_sample_weight

    import h3 as _h3
    hp = dict(hp_tuple)
    d = sample if scope_state is None else sample[sample["state"] == scope_state]
    tr_full, te = d[d["year"] < 2022], d[d["year"] >= 2022]
    tr = tr_full.sample(max_rows, random_state=SEED) if len(tr_full) > max_rows else tr_full
    if len(te) > max_rows // 4: te = te.sample(max_rows // 4, random_state=SEED)

    # Historique du LIEU (amélioration v2) : taux de graves de la zone, calculé sur le
    # TRAIN uniquement (anti-fuite), lissage bayésien ; zones inconnues -> taux global.
    def _zone_feats(res, name):
        ref = tr_full.copy()
        ref["_z"] = [_h3.latlng_to_cell(a, b, res) for a, b in zip(ref.start_lat, ref.start_lng)]
        g = ref.groupby("_z")["grave"].agg(["mean", "count"])
        prior, k = ref["grave"].mean(), 30
        rate = (g["mean"] * g["count"] + prior * k) / (g["count"] + k)
        for df in (tr, te):
            z = [_h3.latlng_to_cell(a, b, res) for a, b in zip(df.start_lat, df.start_lng)]
            df[name] = pd.Series(z, index=df.index).map(rate).fillna(prior)
            df[name + "_n"] = pd.Series(z, index=df.index).map(g["count"]).fillna(0)
    tr, te = tr.copy(), te.copy()
    ZONE_FEATS = []
    if zone_hist:
        _zone_feats(7, "zone_hist7"); _zone_feats(5, "zone_hist5")
        ZONE_FEATS = ["zone_hist7", "zone_hist7_n", "zone_hist5", "zone_hist5_n"]
    feats = ALL_FEATURES + ZONE_FEATS
    num_cols = NUM_CONTROLS + ZONE_FEATS
    X_tr, y_tr = tr[feats], tr["grave"]
    X_te, y_te = te[feats], te["grave"]

    prep = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), num_cols),
        ("cat", Pipeline([("imp", SimpleImputer(strategy="most_frequent")),
                          ("oh", OneHotEncoder(handle_unknown="ignore", min_frequency=20,
                                               sparse_output=False))]), CAT_CONTROLS),
        ("infra", "passthrough", INFRA)])
    clfs = {"HistGradientBoosting": lambda: HistGradientBoostingClassifier(random_state=SEED, **hp),
            "RandomForest": lambda: RandomForestClassifier(random_state=SEED, n_jobs=-1, **hp),
            "DecisionTree": lambda: DecisionTreeClassifier(random_state=SEED, **hp),
            "LogisticRegression": lambda: LogisticRegression(max_iter=2000, **hp)}
    pipe = Pipeline([("prep", prep), ("clf", clfs[model_name]())])
    sw = compute_sample_weight("balanced", y_tr) if balanced else None
    try: pipe.fit(X_tr, y_tr, clf__sample_weight=sw)
    except TypeError: pipe.fit(X_tr, y_tr)
    proba = pipe.predict_proba(X_te)[:, 1]
    return {"pipe": pipe, "proba": proba, "y_te": y_te.values, "X_te": X_te,
            "n_tr": len(tr), "n_te": len(te),
            "pr_auc": float(average_precision_score(y_te, proba)),
            "roc_auc": float(roc_auc_score(y_te, proba)),
            "baseline_pr": float(y_te.mean())}

hp_t = tuple(sorted(hp.items()))
scope = STATE if train_scope == "Ce territoire uniquement" else None
res = train(model_name, hp_t, balanced, scope, max_rows, use_zone_hist)

# --------------------------------------------------- effets & recommandations
@st.cache_data(show_spinner="Calcul des effets ajustés…")
def adjusted_effects(model_name, hp_t, balanced, scope, max_rows, zone_hist=False, cap=30_000):
    rr = train(model_name, hp_t, balanced, scope, max_rows, zone_hist)
    X = rr["X_te"]
    if len(X) > cap: X = X.sample(cap, random_state=SEED)
    out = {}
    for el in INFRA:
        X0, X1 = X.copy(), X.copy(); X0[el] = 0; X1[el] = 1
        out[el] = float(rr["pipe"].predict_proba(X1)[:, 1].mean()
                        - rr["pipe"].predict_proba(X0)[:, 1].mean())
    return pd.Series(out).sort_values()

@st.cache_data(show_spinner="Construction du plan d'action…")
def build_plan(state_key, model_name, hp_t, balanced, scope, max_rows,
               topn, zone_hist=False, lift_min=1.5, presence_min=0.05, min_n=200):
    rr = train(model_name, hp_t, balanced, scope, max_rows, zone_hist)
    zz = (zones if state_key is None else zones[zones["state"] == state_key]) \
        .sort_values("charge", ascending=False).head(topn).reset_index(drop=True)
    zz["rang"] = zz.index + 1
    tot_n = zones["n_accidents"].sum() if state_key is None else \
        zones.loc[zones["state"] == state_key, "n_accidents"].sum()
    zsrc = zones if state_key is None else zones[zones["state"] == state_key]
    nat = {e: zsrc["n_" + e].sum() / max(tot_n, 1) for e in INFRA}

    def cond_adj(H, P):
        sub = rr["X_te"][rr["X_te"][H] == 1]
        if len(sub) < min_n: return np.nan
        if len(sub) > 30_000: sub = sub.sample(30_000, random_state=SEED)
        X0, X1 = sub.copy(), sub.copy(); X0[P] = 0; X1[P] = 1
        return float(rr["pipe"].predict_proba(X1)[:, 1].mean()
                     - rr["pipe"].predict_proba(X0)[:, 1].mean())
    cond = {H: {P: cond_adj(H, P) for P in DEPLOYABLE if P != H} for H in INFRA}

    rows = []
    for _, r in zz.iterrows():
        present = {e: r["n_" + e] / max(r["n_accidents"], 1) for e in INFRA}
        shares = {e: present[e] / nat[e] if nat[e] > 0 else 0 for e in INFRA}
        H = max(shares, key=shares.get)
        if shares[H] < lift_min:
            reco, impact, why = "Investiguer facteur humain (vitesse/contrôles)", 0.0, \
                "aucun défaut d'infrastructure ne domine dans cette zone"
        else:
            opts = sorted([(P, v) for P, v in cond[H].items() if pd.notna(v) and v < 0],
                          key=lambda x: x[1])
            missing = [(P, v) for P, v in opts if present[P] < presence_min]
            if not missing:
                reco, impact, why = "Déjà équipé — étude géométrie/abords", 0.0, \
                    f"aléa « {INFRA_FR[H]} » mais les mesures efficaces sont déjà en place"
            else:
                P, v = missing[0]
                reco = "Sécuriser le passage à niveau" if H == "railway" else RECO_LABEL[P]
                impact = abs(v) * r["n_accidents"]
                why = (f"aléa dominant « {INFRA_FR[H]} » (×{shares[H]:.1f} vs moyenne) ; "
                       f"« {INFRA_FR[P]} » absent alors qu'il réduit la gravité de "
                       f"{abs(v)*100:.1f} pts dans ce contexte")
        rows.append({"rang": int(r["rang"]), "h3_cell": r["h3_cell"],
                     "accidents": int(r["n_accidents"]), "gravité_moy": round(r["avg_severity"], 2),
                     "aléa_dominant": INFRA_FR.get(H, H) if shares[H] >= lift_min else "diffus",
                     "recommandation": reco, "justification": why,
                     "graves_évités_estimés": round(impact, 1)})
    plan = pd.DataFrame(rows).sort_values("graves_évités_estimés", ascending=False)
    span = _span_years(state_key)
    plan["graves_évités_par_an"] = (plan["graves_évités_estimés"] / span).round(1)
    return plan

# ----------------------------------------------------------------- entête
st.title(f"Aide à la décision voirie — {etat}")
with st.expander("Guide de lecture — que fait cet outil, dans quel ordre le lire ?"):
    st.markdown(
        "**Ce que l'outil calcule :** un modèle apprend à estimer, pour chaque accident "
        "historique, la probabilité qu'il soit grave à partir de son seul contexte "
        "(météo, heure, lieu, équipements). Cette prédiction n'est pas le produit : elle sert à "
        "**mesurer l'effet net de chaque équipement** sur la gravité, à contexte égal — "
        "c'est cette mesure qui fonde les recommandations.\n\n"
        "**Ordre de lecture :**\n"
        "1. **Où** — le diagnostic : les zones qui concentrent le risque, et la validation "
        "temporelle (les zones désignées hier concentrent bien les graves d'aujourd'hui) ;\n"
        "2. **Plan d'action** — la prescription : pour chaque zone, l'aménagement qui manque "
        "et le gain attendu par an ;\n"
        "3. **Quand** — le complément : les risques liés à l'heure et à la météo, qui relèvent "
        "de mesures temporaires, pas de travaux ;\n"
        "4. **Modèle** — la preuve : la qualité du moteur d'analyse et les effets ajustés qui "
        "justifient les recommandations.\n\n"
        "*Les estimations sont associationnelles (pas de preuve causale) : elles servent à "
        "prioriser les études terrain.*")
q = res['pr_auc'] / max(res['baseline_pr'], 1e-9)
k1, k2, k3 = st.columns(3)
zs = zones if STATE is None else zones[zones["state"] == STATE]
k1.metric("Zones analysées", f"{len(zs):,}")
k2.metric("Fiabilité du moteur d'analyse", f"×{q:.1f}",
          help="Capacité du modèle à repérer les accidents graves, comparée au hasard "
               f"(PR-AUC {res['pr_auc']:.3f} vs plancher {res['baseline_pr']:.3f}). "
               "×1 = n'apprend rien ; plus c'est haut, plus les effets estimés sont fiables.")
k3.metric("Détection des graves (ROC-AUC)", f"{res['roc_auc']:.2f}",
          help="0,5 = hasard, 1 = parfait.")
if q < 1.3:
    st.warning("Le moteur apprend peu sur ce périmètre (probablement trop peu de données "
               "locales). Pour un plan d'action fiable, repassez sur **US entier (générique)**.")

tab_ou, tab_plan, tab_quand, tab_tech = st.tabs([
    "1. Où — le diagnostic",
    "2. Plan d'action — la prescription",
    "3. Quand — le complément temporaire",
    "4. Modèle — la preuve (analyste)"])

# ================================================================= PLAN D'ACTION
with tab_plan:
    st.markdown("#### Ce que le gestionnaire de voirie doit faire, zone par zone")
    st.caption("Pour chaque zone prioritaire : le défaut d'infrastructure dominant, "
               "l'aménagement recommandé (celui qui manque **et** qui réduit la gravité "
               "dans ce contexte, à météo/heure égales), et le nombre d'accidents graves "
               "potentiellement évités (estimation, à confirmer par visite terrain).")
    topn = st.slider("Nombre de zones au plan", 10, 100, 30, 10, key="plan_topn")
    if use_zone_hist:
        st.warning(" « Historique du lieu » est activé : bon pour le ciblage, mais il peut "
                   "**diluer les effets attribués aux équipements** (il contient déjà leur "
                   "effet passé). Pour un plan d'action fidèle au notebook, désactivez-le.")
    plan = build_plan(STATE, model_name, hp_t, balanced, scope, max_rows, topn, use_zone_hist)

    cA, cB = st.columns([3, 2])
    with cA:
        import h3 as h3lib
        import folium
        m, pts = make_map(plan["h3_cell"])
        imax = max(plan["graves_évités_estimés"].max(), 1e-9)
        for _, r in plan.iterrows():
            try:
                la, ln = h3lib.cell_to_latlng(r["h3_cell"])
                col = RECO_COLOR.get(r["recommandation"], "#7f8c8d")
                tip = (f"<b>#{r['rang']}</b> — {r['accidents']:,} accidents · "
                       f"gravité {r['gravité_moy']}<br>Aléa : <b>{r['aléa_dominant']}</b><br>"
                       f" <b>{r['recommandation']}</b><br>"
                       f"≈ {r['graves_évités_par_an']:.0f} graves évités / an")
                folium.Polygon(list(h3lib.cell_to_boundary(r["h3_cell"])), color=col, weight=1,
                               fill=True, fill_color=col, fill_opacity=0.25).add_to(m)
                folium.CircleMarker([la, ln], radius=6 + 12 * r["graves_évités_estimés"] / imax,
                                    color="#222", weight=1, fill=True, fill_color=col,
                                    fill_opacity=0.9, tooltip=folium.Tooltip(tip)).add_to(m)
                folium.map.Marker(
                    [la, ln], icon=folium.DivIcon(
                        html=f"<div style='font-size:9px;font-weight:bold;color:#222;"
                             f"transform:translate(-4px,-7px)'>{r['rang']}</div>")).add_to(m)
            except Exception:
                pass
        if pts: m.fit_bounds(pts)
        fix_map_in_tab(m, pts)
        items = "".join(
            f"<div style='margin:1px 0'><span style='background:{c};width:11px;height:11px;"
            f"display:inline-block;margin-right:5px;border-radius:2px'></span>{a}</div>"
            for a, c in RECO_COLOR.items() if a in set(plan["recommandation"]))
        legend = ("<div style='position:absolute;bottom:12px;left:12px;z-index:9999;"
                  "background:white;color:#222;padding:8px 10px;border:1px solid #999;"
                  "border-radius:4px;font-size:11px'><b>Aménagement recommandé</b>"
                  "<br><i>taille du point = gain attendu · numéro = rang</i>" + items + "</div>")
        m.get_root().html.add_child(folium.Element(legend))
        st.components.v1.html(m._repr_html_(), height=520)

    with cB:
        recap = (plan.groupby("recommandation")
                     .agg(zones=("rang", "count"),
                          graves_évités=("graves_évités_estimés", "sum"))
                     .sort_values("graves_évités", ascending=False).round(0))
        st.markdown("**Répartition des interventions**")
        st.dataframe(recap, use_container_width=True)
        st.metric("Gain total estimé (ex-ante)",
                  f"≈ {plan['graves_évités_par_an'].sum():,.0f} graves évités / an",
                  help=f"Soit ≈ {plan['graves_évités_estimés'].sum():,.0f} sur une période "
                       f"comparable aux {_span_years(STATE):.1f} années de données. "
                       "Hypothèse : trafic et conditions stables.")
        st.download_button("Télécharger le plan d'action (CSV)",
                           plan.to_csv(index=False).encode("utf-8"),
                           file_name=f"plan_action_{etat.replace(' ', '_')}.csv",
                           mime="text/csv")

    st.markdown("**Plan détaillé (trié par gain attendu)**")
    st.dataframe(plan[["rang", "accidents", "gravité_moy", "aléa_dominant",
                       "recommandation", "graves_évités_par_an", "justification"]],
                 use_container_width=True, height=330, hide_index=True)
    st.info("Estimations **associationnelles** (pas de preuve causale — pas d'avant/après "
            "disponible). À utiliser pour **prioriser les études terrain**, pas comme garantie.")

# ================================================================= OÙ
with tab_ou:
    st.markdown("#### Où le risque se concentre-t-il ?")
    left, right = st.columns([3, 2])
    topn2 = right.slider("Zones affichées (top charge)", 10, 150, 50, 10, key="ou_topn")
    zz = zs.sort_values("charge", ascending=False).reset_index(drop=True)
    top = zz.head(topn2).copy(); top["rang"] = top.index + 1

    with left:
        import h3 as h3lib
        import folium
        import branca.colormap as bcm
        m, pts = make_map(top["h3_cell"])
        cmap = bcm.LinearColormap(["#2ecc71", "#f1c40f", "#e74c3c"],
                                  vmin=float(top["avg_severity"].min()),
                                  vmax=float(top["avg_severity"].max()),
                                  caption="Gravité moyenne de la zone")
        cmap.add_to(m)
        nmax = top["charge"].max()
        for _, r in top.iterrows():
            try:
                la, ln = h3lib.cell_to_latlng(r["h3_cell"])
                col = cmap(r["avg_severity"])
                dominant = max(INFRA, key=lambda e: r["n_" + e] / max(r["n_accidents"], 1))
                tip = (f"<b>#{int(r['rang'])}</b> — {int(r['n_accidents']):,} accidents<br>"
                       f"gravité moyenne {r['avg_severity']:.2f}<br>"
                       f"élément le plus présent : {INFRA_FR[dominant]}")
                folium.Polygon(list(h3lib.cell_to_boundary(r["h3_cell"])), color=col, weight=1,
                               fill=True, fill_color=col, fill_opacity=0.25).add_to(m)
                folium.CircleMarker([la, ln], radius=5 + 13 * float(r["charge"]) / nmax,
                                    color="#222", weight=1, fill=True, fill_color=col,
                                    fill_opacity=0.9, tooltip=folium.Tooltip(tip)).add_to(m)
            except Exception:
                pass
        if pts: m.fit_bounds(pts)
        fix_map_in_tab(m, pts)
        legend = ("<div style='position:absolute;bottom:12px;left:12px;z-index:9999;"
                  "background:white;color:#222;padding:8px 10px;border:1px solid #999;"
                  "border-radius:4px;font-size:11px'><b>Lecture</b><br>"
                  "taille = volume d'accidents (charge)<br>couleur = gravité moyenne</div>")
        m.get_root().html.add_child(folium.Element(legend))
        st.components.v1.html(m._repr_html_(), height=470)

    with right:
        ch = zz["charge"].values; cum = np.cumsum(ch) / ch.sum()
        fig, ax = plt.subplots(figsize=(5, 3.2))
        x = np.arange(1, len(ch) + 1) / len(ch) * 100
        ax.plot(x, cum * 100, color="#c0392b")
        share = cum[min(topn2, len(cum)) - 1] * 100
        ax.axvline(topn2 / len(ch) * 100, ls="--", c="grey", lw=1,
                   label=f"top {topn2} = {share:.0f}% du risque")
        ax.set_xlim(0, 15); ax.set_xlabel("% des zones (classées)")
        ax.set_ylabel("% du risque cumulé"); ax.set_title("Concentration du risque")
        ax.legend(fontsize=8)
        st.pyplot(fig, use_container_width=True)
        st.success(f"**{topn2} zones** (sur {len(zz):,}) portent **{share:.0f} %** du risque : "
                   "concentrer les travaux sur ces zones a un effet de levier maximal.")
        tt = top[["rang", "n_accidents", "avg_severity", "charge"]].copy()
        tt.columns = ["rang", "accidents", "gravité moy.", "charge"]
        st.dataframe(tt.round(2).head(15), height=240, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("####  La prévision d'hier s'est-elle réalisée ? (validation temporelle)")
    v1, v2 = st.columns(2)
    zy = zones_year if STATE is None else zones_year[zones_year["state"] == STATE]
    past = (zy[zy["year"] <= 2019].groupby("h3_cell")["charge"].sum()
            .sort_values(ascending=False))
    fut = zy[zy["year"] >= 2020]
    with v1:
        if len(past) and fut["graves"].sum() > 0:
            top_past = set(past.head(topn2).index)
            captured = fut.loc[fut["h3_cell"].isin(top_past), "graves"].sum()
            share = captured / fut["graves"].sum()
            weight = topn2 / max(fut["h3_cell"].nunique(), 1)
            st.metric(f"Backtest — zones désignées avec les données ≤ 2019",
                      f"{share*100:.0f} % des graves 2020-2023",
                      delta=f"×{share/max(weight,1e-9):.0f} vs leur poids ({weight*100:.2f} % des zones)")
            st.caption("On rejoue la méthode comme si on était fin 2019 : les zones qu'elle "
                       "désignait ont bien concentré les accidents graves des années suivantes "
                       " le classement **prédit le futur**, ce n'est pas une photo du passé.")
        else:
            st.info("Pas assez de données pour le backtest sur ce territoire.")
    with v2:
        qy = quand_year[quand_year["state"] == (STATE if STATE is not None else "US")]
        qy = qy.sort_values("year")
        qy = qy[(qy["year"] >= 2016) & (qy["year"] <= 2023)]
        fig, ax = plt.subplots(figsize=(5, 2.8))
        ax.bar(qy["year"], qy["graves"], color="#c0392b", alpha=0.85)
        ax.set_title("Accidents graves par année (territoire)")
        ax.set_xlabel("(2016 et 2023 = années partielles ; la hausse reflète aussi "
                      "l'amélioration de la collecte)", fontsize=7)
        st.pyplot(fig, use_container_width=True)

# ================================================================= QUAND
with tab_quand:
    st.markdown("#### Quand renforcer la vigilance (mesures temporaires, pas de travaux)")
    key = STATE if STATE is not None else "US"
    c1, c2, c3 = st.columns(3)
    for col, dim, titre in [(c1, "hour", "Heure de la journée"),
                            (c2, "weather", "Conditions météo"), (c3, "month", "Mois")]:
        q_ = quand[dim]; qq = q_[q_["state"] == key]
        if qq.empty: qq = q_[q_["state"] == "US"]
        dimcol = [c for c in qq.columns if c not in ("state", "n", "part_grave")][0]
        qq = qq.sort_values(dimcol)
        fig, ax = plt.subplots(figsize=(4.4, 3))
        if dim == "weather":
            qq = qq.sort_values("part_grave")
            ax.barh(qq[dimcol].astype(str), qq["part_grave"] * 100, color="#2980b9")
            ax.set_xlabel("% d'accidents graves")
        else:
            ax.plot(qq[dimcol], qq["part_grave"] * 100, color="#8e44ad", marker="o", ms=3)
            ax.set_xlabel(dimcol); ax.set_ylabel("% d'accidents graves")
        ax.set_title(titre)
        col.pyplot(fig, use_container_width=True)
    st.info("Ces variations relèvent de **mesures dynamiques** — panneaux à messages "
            "variables, limitations temporaires, patrouilles ciblées — pas de travaux. "
            "Le budget rénovation reste sur le risque **structurel** (onglets précédents).")

# ================================================================= TECHNIQUE
with tab_tech:
    from sklearn.metrics import confusion_matrix, precision_recall_curve
    _ht = " (+ historique du lieu — mode ciblage)" if use_zone_hist else " (features du notebook)"
    st.caption(f"Modèle : {model_name}{_ht} · train {res['n_tr']:,} lignes (< 2022) · "
               f"test {res['n_te']:,} (2022-23) · PR-AUC {res['pr_auc']:.3f} "
               f"(plancher {res['baseline_pr']:.3f}) · ROC-AUC {res['roc_auc']:.3f}")
    st.info("**Comment juger ce modèle ?** La gravité d'un accident dépend surtout de facteurs "
            "absents des données (vitesse réelle, alcool, état du conducteur) : viser une "
            "prédiction quasi-parfaite est impossible, quel que soit l'algorithme. "
            "Le bon critère est le **pouvoir de ciblage** ci-dessous : concentrer les graves "
            "dans le haut du classement — c'est ce qui rend la priorisation et les effets "
            "ajustés fiables. La matrice de confusion à seuil fixe est l'angle de lecture "
            "le plus défavorable ; elle est fournie pour l'analyste.")

    # ---- pouvoir de ciblage (lecture métier) ----
    order = np.argsort(-res["proba"]); yy = res["y_te"][order]
    frac = np.arange(1, len(yy) + 1) / len(yy)
    capture = np.cumsum(yy) / max(yy.sum(), 1)
    c10 = float(capture[int(0.10 * len(yy)) - 1]); c20 = float(capture[int(0.20 * len(yy)) - 1])
    g1, g2 = st.columns([3, 2])
    with g1:
        fig, ax = plt.subplots(figsize=(5.6, 3.4))
        ax.plot(frac * 100, capture * 100, color="#16324f", label="modèle")
        ax.plot([0, 100], [0, 100], ls="--", c="grey", lw=1, label="hasard")
        ax.scatter([10, 20], [c10 * 100, c20 * 100], color="#c0392b", zorder=5)
        ax.annotate(f"{c10*100:.0f} %", (10, c10 * 100), textcoords="offset points",
                    xytext=(6, -2), fontsize=9, color="#c0392b")
        ax.set_xlabel("% des accidents ciblés (classés par risque prédit)")
        ax.set_ylabel("% des accidents graves capturés")
        ax.set_title("Pouvoir de ciblage (courbe de gain)"); ax.legend(fontsize=8)
        st.pyplot(fig, use_container_width=True)
    with g2:
        st.metric("En auditant les 10 % les plus risqués", f"{c10*100:.0f} % des graves capturés",
                  delta=f"×{c10/0.10:.1f} vs hasard")
        st.metric("En auditant les 20 % les plus risqués", f"{c20*100:.0f} % des graves capturés",
                  delta=f"×{c20/0.20:.1f} vs hasard")
        st.caption("C'est la lecture utile pour un DOT : avec un budget d'audit limité, "
                   "le modèle concentre les accidents graves en tête de liste.")
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        pred = (res["proba"] >= threshold).astype(int)
        cm = confusion_matrix(res["y_te"], pred); tn, fp, fn, tp = cm.ravel()
        fig, ax = plt.subplots(figsize=(4, 3.2))
        ax.imshow(cm, cmap="Reds")
        for i in range(2):
            for j in range(2):
                ax.text(j, i, f"{cm[i,j]:,}", ha="center", va="center",
                        color="white" if cm[i, j] > cm.max() / 2 else "black")
        ax.set_xticks([0, 1], ["non grave", "grave"]); ax.set_yticks([0, 1], ["non grave", "grave"])
        ax.set_xlabel("prédit"); ax.set_ylabel("réel")
        ax.set_title(f"Matrice de confusion (seuil {threshold:.2f})")
        st.pyplot(fig, use_container_width=False)
        prec = tp / max(tp + fp, 1)
        st.markdown(f"Rappel « grave » : **{tp/max(tp+fn,1):.2f}** · précision : {prec:.2f} "
                    f"(**×{prec/max(res['baseline_pr'],1e-9):.1f}** vs taux de base "
                    f"{res['baseline_pr']:.2f}) · graves ratés : {fn:,} · fausses alertes : {fp:,}")
    with c2:
        p, r, _ = precision_recall_curve(res["y_te"], res["proba"])
        rec_now = tp / max(tp + fn, 1); prec_now = tp / max(tp + fp, 1)
        fig, ax = plt.subplots(figsize=(4.6, 3.4))
        ax.plot(r, p, color="#16324f", label=f"{model_name} (AP={res['pr_auc']:.3f})")
        ax.axhline(res["baseline_pr"], ls="--", c="grey", lw=1,
                   label=f"plancher ({res['baseline_pr']:.2f})")
        ax.scatter([rec_now], [prec_now], s=90, color="#c0392b", zorder=5,
                   label=f"vos réglages (seuil {threshold:.2f})")
        ax.annotate(f"seuil {threshold:.2f}", (rec_now, prec_now),
                    textcoords="offset points", xytext=(8, 8), fontsize=9, color="#c0392b")
        ax.set_xlabel("rappel"); ax.set_ylabel("précision"); ax.legend(fontsize=8)
        ax.set_title("Courbe précision-rappel — votre point de fonctionnement")
        st.pyplot(fig, use_container_width=False)
        st.caption("La matrice de gauche N'EST QUE ce point rouge : changer le seuil ou "
                   "class_weight déplace le point **le long de la même courbe** — "
                   "le modèle (la courbe) ne change pas.")

    st.divider()
    st.markdown("**Effets ajustés (g-computation)** — fondement des recommandations du plan d'action")
    adj = adjusted_effects(model_name, hp_t, balanced, scope, max_rows, use_zone_hist)
    fig, ax = plt.subplots(figsize=(8, 4))
    labels = [INFRA_FR[i] for i in adj.index]
    ax.barh(labels, adj.values * 100,
            color=["#27ae60" if v < 0 else "#c0392b" for v in adj.values])
    ax.axvline(0, color="#333", lw=0.8)
    ax.set_xlabel("Δ probabilité de gravité (points de %) — vert = protecteur")
    st.pyplot(fig, use_container_width=True)
    st.info("Une moyenne brute « avec/sans feux » donnerait l'inverse (les feux sont là où "
            "c'est dense) : ces effets sont **ajustés** — météo, heure, État maintenus constants "
            "par le modèle. Associationnels, pas causaux.")
