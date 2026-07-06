# -*- coding: utf-8 -*-
"""DataValueXploring — pipeline d'analyse paramétrable (produit client).

Usage :
    python pipeline/run_pipeline.py --config pipeline/config.yaml

Exécute les analyses activées dans le fichier de configuration (QUAND, OÙ,
QUOI, SYNTHÈSE) et écrit figures, CSV décisionnels, carte et rapport de
synthèse dans le dossier de sortie. Même logique que le notebook de référence
(`rendu/notebook.ipynb`) — le notebook explique, la pipeline industrialise.
"""
import argparse, json, os, sys, time, warnings
warnings.filterwarnings("ignore")
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yaml

INFRA = ["junction", "crossing", "stop", "traffic_signal", "railway", "station",
         "roundabout", "bump", "give_way", "no_exit", "traffic_calming", "amenity"]
WEATHER_NUM = ["temperature_f", "humidity_pct", "visibility_mi", "wind_speed_mph", "pressure_in"]
NUM_CONTROLS = WEATHER_NUM + ["hour", "dow", "month"]
CAT_CONTROLS = ["weather_bucket", "state", "is_night"]
ALL_FEATURES = INFRA + NUM_CONTROLS + CAT_CONTROLS
DEPLOYABLE = ["traffic_signal", "crossing", "stop", "traffic_calming"]
LABELS = {"traffic_signal": "installer des feux", "crossing": "sécuriser passage piéton",
          "stop": "stop / cédez-le-passage", "traffic_calming": "modération de trafic"}
SEED = 42

T0 = time.time()
def log(msg): print(f"[{time.time()-T0:6.0f}s] {msg}", flush=True)

# ---------------------------------------------------------------- config
def load_config(path):
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    out = os.path.expanduser(cfg["sorties"]["dossier"])
    os.makedirs(out, exist_ok=True)
    return cfg, out

def outpath(cfg, out, name):
    return os.path.join(out, cfg["sorties"].get("prefixe", "") + name)

# ---------------------------------------------------------------- données
def load_clean(cfg):
    from pyspark.sql import SparkSession, functions as F
    from pyspark.sql.types import (StructType, StructField, StringType, IntegerType,
                                   DoubleType, BooleanType, TimestampType)
    spark = (SparkSession.builder.master("local[*]").appName("dvx_pipeline")
             .config("spark.driver.memory", cfg["spark"].get("memoire", "6g"))
             .config("spark.sql.session.timeZone", "UTC").getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")

    csv = os.path.expanduser(str(cfg["donnees"].get("csv") or ""))
    if not csv or not os.path.exists(csv):
        import kagglehub
        p = kagglehub.dataset_download("sobhanmoosavi/us-accidents")
        csv = next(os.path.join(p, f) for f in os.listdir(p) if f.endswith(".csv"))
    log(f"données : {csv}")

    names = ["ID","Source","Severity","Start_Time","End_Time","Start_Lat","Start_Lng",
             "End_Lat","End_Lng","Distance(mi)","Description","Street","City","County",
             "State","Zipcode","Country","Timezone","Airport_Code","Weather_Timestamp",
             "Temperature(F)","Wind_Chill(F)","Humidity(%)","Pressure(in)","Visibility(mi)",
             "Wind_Direction","Wind_Speed(mph)","Precipitation(in)","Weather_Condition",
             "Amenity","Bump","Crossing","Give_Way","Junction","No_Exit","Railway",
             "Roundabout","Station","Stop","Traffic_Calming","Traffic_Signal","Turning_Loop",
             "Sunrise_Sunset","Civil_Twilight","Nautical_Twilight","Astronomical_Twilight"]
    types = {"Severity": IntegerType()}
    for n in ["Start_Time","End_Time","Weather_Timestamp"]: types[n] = TimestampType()
    for n in ["Start_Lat","Start_Lng","End_Lat","End_Lng","Distance(mi)","Temperature(F)",
              "Wind_Chill(F)","Humidity(%)","Pressure(in)","Visibility(mi)",
              "Wind_Speed(mph)","Precipitation(in)"]: types[n] = DoubleType()
    for n in ["Amenity","Bump","Crossing","Give_Way","Junction","No_Exit","Railway",
              "Roundabout","Station","Stop","Traffic_Calming","Traffic_Signal",
              "Turning_Loop"]: types[n] = BooleanType()
    schema = StructType([StructField(n, types.get(n, StringType())) for n in names])
    raw = spark.read.option("header", True).schema(schema).csv(csv)
    raw = raw.toDF(*[c.lower().replace("(","_").replace(")","").replace("%","pct")
                     for c in raw.columns])

    c = F.lower(F.coalesce(F.col("weather_condition"), F.lit("")))
    bucket = (F.when(c.contains("snow")|c.contains("sleet")|c.contains("wintry")|c.contains("ice"),"Snow")
               .when(c.contains("rain")|c.contains("drizzle")|c.contains("shower")|c.contains("thunder"),"Rain")
               .when(c.contains("fog")|c.contains("mist")|c.contains("haze"),"Fog")
               .when(c.contains("cloud")|c.contains("overcast"),"Cloud")
               .when(c.contains("clear")|c.contains("fair"),"Clear").otherwise("Other"))
    seuil = int(cfg["parametres"]["seuil_grave"])
    df = (raw.drop("end_lat","end_lng","wind_chill_f")
             .dropna(subset=["severity","start_lat","start_lng"])
             .withColumn("grave",(F.col("severity")>=seuil).cast("int"))
             .withColumn("hour",F.coalesce(F.hour("start_time"),F.lit(0)))
             .withColumn("dow",F.dayofweek("start_time"))
             .withColumn("month",F.month("start_time"))
             .withColumn("year",F.year("start_time"))
             .withColumn("is_night",F.coalesce((F.col("sunrise_sunset")==F.lit("Night")).cast("int"),F.lit(0)))
             .withColumn("weather_bucket",bucket))
    for col in INFRA:
        df = df.withColumn(col, F.coalesce(F.col(col), F.lit(False)).cast("int"))
    df = df.cache()
    # garde-fous (mêmes invariants que le notebook)
    assert df.filter(F.col("start_lat").isNull()).count() == 0
    log(f"nettoyage : {df.count():,} lignes (part grave "
        f"{df.agg(F.mean('grave')).first()[0]*100:.1f} %)")
    return spark, df

# ---------------------------------------------------------------- QUAND
def run_quand(cfg, out, df):
    from pyspark.sql import functions as F
    log("QUAND : patterns temporels/météo")
    hourly = df.groupBy("hour").agg(F.count("*").alias("n"), F.mean("grave").alias("pg")) \
               .orderBy("hour").toPandas()
    wx = df.groupBy("weather_bucket").agg(F.count("*").alias("n"), F.mean("grave").alias("pg")) \
           .orderBy(F.desc("n")).toPandas()
    fig, ax = plt.subplots(1, 3, figsize=(15, 4))
    ax[0].bar(hourly["hour"], hourly["n"], color="#16324f"); ax[0].set_title("Volume par heure")
    ax[1].plot(hourly["hour"], hourly["pg"]*100, color="#8e44ad", marker="o", ms=3)
    ax[1].set_title("% graves par heure")
    w = wx.sort_values("pg")
    ax[2].barh(w["weather_bucket"], w["pg"]*100, color="#2980b9"); ax[2].set_title("% graves par météo")
    plt.tight_layout(); fig.savefig(outpath(cfg, out, "quand.png"), dpi=130); plt.close(fig)
    return {"heure_max_grave": int(hourly.loc[hourly["pg"].idxmax(), "hour"]),
            "pct_max": round(float(hourly["pg"].max()*100), 1)}

# ---------------------------------------------------------------- OÙ
def run_ou(cfg, out, df):
    from pyspark.sql import functions as F
    import h3
    p = cfg["parametres"]; state = cfg["donnees"]["territoire"]
    log(f"OÙ : zones prioritaires ({state})")
    terr = (df.filter(F.col("state") == state)
              .select("start_lat","start_lng","severity","year",*INFRA)).toPandas()
    if terr.empty:
        log(f"  !! aucun accident pour le territoire {state} — section sautée")
        return None, None
    res = int(p["h3_resolution"])
    terr["h3_cell"] = [h3.latlng_to_cell(a, b, res)
                       for a, b in zip(terr["start_lat"], terr["start_lng"])]
    aggmap = {"severity": ["count","mean","sum"], **{e: "sum" for e in INFRA}}
    zone = terr.groupby("h3_cell").agg(aggmap)
    zone.columns = ["n_accidents","avg_severity","charge"] + ["n_"+e for e in INFRA]
    zone = zone.reset_index().sort_values("charge", ascending=False).reset_index(drop=True)
    zone["rank"] = zone.index + 1
    topn = int(p["zones_prioritaires"]); top = zone.head(topn).copy()

    ch = zone["charge"].values; cum = np.cumsum(ch)/ch.sum()
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(np.arange(1, len(ch)+1)/len(ch)*100, cum*100, color="#c0392b")
    ax.axvline(topn/len(ch)*100, ls="--", c="grey",
               label=f"top {topn} = {cum[topn-1]*100:.0f}% de la charge")
    ax.set_xlim(0, 15); ax.set_xlabel("% des zones"); ax.set_ylabel("% charge cumulée")
    ax.set_title(f"Concentration du risque — {state}"); ax.legend(fontsize=8)
    plt.tight_layout(); fig.savefig(outpath(cfg, out, "ou_concentration.png"), dpi=130); plt.close(fig)

    import folium
    m = folium.Map(tiles="CartoDB positron"); pts = []
    cmax = top["charge"].max()
    for _, r in top.iterrows():
        la, ln = h3.cell_to_latlng(r["h3_cell"]); pts.append([la, ln])
        folium.Polygon(list(h3.cell_to_boundary(r["h3_cell"])), color="#c0392b", weight=1,
                       fill=True, fill_opacity=0.15+0.55*float(r["charge"])/cmax,
                       tooltip=f"#{int(r['rank'])} — {int(r['n_accidents']):,} accidents "
                               f"(charge {r['charge']:.0f})").add_to(m)
    if pts: m.fit_bounds(pts)
    m.save(outpath(cfg, out, "ou_carte.html"))
    top.to_csv(outpath(cfg, out, "ou_zones_prioritaires.csv"), index=False)
    log(f"  {len(zone):,} zones — top {topn} exporté (part de charge "
        f"{cum[topn-1]*100:.1f} %)")
    return zone, terr

# ---------------------------------------------------------------- QUOI
def make_model(cfg):
    from sklearn.dummy import DummyClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
    algo = cfg["modele"]["algorithme"]; hp = cfg["modele"].get("hyperparametres") or {}
    table = {"dummy": lambda: DummyClassifier(strategy="most_frequent"),
             "logistic": lambda: LogisticRegression(max_iter=2000, **hp),
             "tree": lambda: DecisionTreeClassifier(random_state=SEED, **hp),
             "random_forest": lambda: RandomForestClassifier(random_state=SEED, n_jobs=-1, **hp),
             "hist_gradient_boosting": lambda: HistGradientBoostingClassifier(random_state=SEED, **hp)}
    if algo not in table:
        sys.exit(f"config: algorithme inconnu '{algo}' (choix: {list(table)})")
    return algo, table[algo]()

def run_quoi(cfg, out, df):
    from pyspark.sql import functions as F
    from sklearn.compose import ColumnTransformer
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler, OneHotEncoder
    from sklearn.metrics import (average_precision_score, roc_auc_score,
                                 confusion_matrix, precision_recall_curve)
    from sklearn.utils.class_weight import compute_sample_weight

    mc = cfg["modele"]; cut = int(mc["split_temporel"]["train_avant"])
    scope = cfg["donnees"].get("perimetre_entrainement", "us")
    base = df if scope == "us" else df.filter(F.col("state") == cfg["donnees"]["territoire"])
    log(f"QUOI : modèle {mc['algorithme']} (périmètre {scope}, split < {cut})")

    def cap(sdf, n):
        tot = sdf.count()
        return (sdf if tot <= n else sdf.sample(False, n/tot, seed=SEED)).toPandas()
    cols = ALL_FEATURES + ["grave", "year"]
    tr = cap(base.filter(F.col("year") < cut).select(*cols), int(mc["lignes_max"]))
    te = cap(base.filter(F.col("year") >= cut).select(*cols), int(mc["lignes_max"]) // 4)
    X_tr, y_tr = tr[ALL_FEATURES], tr["grave"]; X_te, y_te = te[ALL_FEATURES], te["grave"]

    prep = ColumnTransformer([
        ("num", Pipeline([("i", SimpleImputer(strategy="median")), ("s", StandardScaler())]), NUM_CONTROLS),
        ("cat", Pipeline([("i", SimpleImputer(strategy="most_frequent")),
                          ("o", OneHotEncoder(handle_unknown="ignore", min_frequency=20,
                                              sparse_output=False))]), CAT_CONTROLS),
        ("infra", "passthrough", INFRA)])
    algo, clf = make_model(cfg)
    pipe = Pipeline([("prep", prep), ("clf", clf)])
    sw = compute_sample_weight("balanced", y_tr) if mc.get("class_weight_balanced") else None
    try: pipe.fit(X_tr, y_tr, clf__sample_weight=sw)
    except TypeError: pipe.fit(X_tr, y_tr)
    proba = pipe.predict_proba(X_te)[:, 1]
    metrics = {"algorithme": algo, "n_train": len(tr), "n_test": len(te),
               "pr_auc": round(float(average_precision_score(y_te, proba)), 4),
               "roc_auc": round(float(roc_auc_score(y_te, proba)), 4),
               "plancher_pr_auc": round(float(y_te.mean()), 4)}
    cm = confusion_matrix(y_te, (proba >= 0.5).astype(int))
    tn, fp, fn, tp = cm.ravel()
    metrics["rappel_grave@0.5"] = round(tp/max(tp+fn, 1), 3)
    log(f"  PR-AUC {metrics['pr_auc']} (plancher {metrics['plancher_pr_auc']}) · "
        f"ROC {metrics['roc_auc']} · rappel {metrics['rappel_grave@0.5']}")

    p, r, _ = precision_recall_curve(y_te, proba)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4))
    ax[0].imshow(cm, cmap="Reds")
    for i in range(2):
        for j in range(2):
            ax[0].text(j, i, f"{cm[i,j]:,}", ha="center", va="center",
                       color="white" if cm[i,j] > cm.max()/2 else "black")
    ax[0].set_xticks([0,1], ["non grave","grave"]); ax[0].set_yticks([0,1], ["non grave","grave"])
    ax[0].set_title("Matrice de confusion (seuil 0,5)")
    ax[1].plot(r, p, color="#16324f"); ax[1].axhline(metrics["plancher_pr_auc"], ls="--", c="grey")
    ax[1].set_xlabel("rappel"); ax[1].set_ylabel("précision"); ax[1].set_title("Précision-rappel")
    plt.tight_layout(); fig.savefig(outpath(cfg, out, "quoi_metriques.png"), dpi=130); plt.close(fig)

    eff = mc.get("effets") or {}
    adj = None
    if eff.get("g_computation", True):
        capn = int(eff.get("echantillon_gcomp", 50_000))
        Xg = X_te.sample(min(capn, len(X_te)), random_state=SEED)
        vals = {}
        for el in INFRA:
            X0, X1 = Xg.copy(), Xg.copy(); X0[el] = 0; X1[el] = 1
            vals[el] = float(pipe.predict_proba(X1)[:,1].mean() - pipe.predict_proba(X0)[:,1].mean())
        adj = pd.Series(vals).sort_values()
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.barh(adj.index, adj.values*100,
                color=["#27ae60" if v < 0 else "#c0392b" for v in adj.values])
        ax.axvline(0, color="#333", lw=.8)
        ax.set_xlabel("Δ probabilité de gravité (pts de %) — effets ajustés (g-computation)")
        plt.tight_layout(); fig.savefig(outpath(cfg, out, "quoi_effets_ajustes.png"), dpi=130); plt.close(fig)
        log("  effets ajustés (g-computation) exportés")

    if eff.get("odds_ratios", True):
        try:
            import statsmodels.api as sm
            n_or = min(300_000, len(X_tr))
            Xs = X_tr.sample(n_or, random_state=SEED); ys = y_tr.loc[Xs.index].astype(float)
            num = Xs[NUM_CONTROLS].apply(lambda s: s.fillna(s.median()))
            num = (num - num.mean()) / num.std()
            design = pd.concat([Xs[INFRA].astype(float), num,
                                pd.get_dummies(Xs[CAT_CONTROLS].astype(str),
                                               drop_first=True, dtype=float)], axis=1)
            logit = sm.Logit(ys.values, sm.add_constant(design.values)).fit(
                disp=0, method="lbfgs", maxiter=400)
            names = ["const"] + list(design.columns)
            params = pd.Series(logit.params, index=names)
            ci = pd.DataFrame(np.asarray(logit.conf_int()), index=names, columns=["lo","hi"])
            ors = pd.DataFrame({"OR": np.exp(params[INFRA]),
                                "lo": np.exp(ci.loc[INFRA,"lo"]),
                                "hi": np.exp(ci.loc[INFRA,"hi"])}).sort_values("OR")
            fig, ax = plt.subplots(figsize=(8, 4.5))
            yp = np.arange(len(ors))
            ax.errorbar(ors["OR"], yp, xerr=[ors["OR"]-ors["lo"], ors["hi"]-ors["OR"]],
                        fmt="o", color="#2c3e50", ecolor="#7f8c8d", capsize=3)
            ax.axvline(1, ls="--", c="#c0392b", lw=1)
            ax.set_yticks(yp, ors.index); ax.set_xscale("log")
            ax.set_xlabel("odds ratio ajusté (IC 95 %) — <1 protecteur")
            plt.tight_layout(); fig.savefig(outpath(cfg, out, "quoi_odds_ratios.png"), dpi=130); plt.close(fig)
            ors.round(4).to_csv(outpath(cfg, out, "quoi_odds_ratios.csv"))
            log("  odds ratios exportés")
        except ImportError:
            log("  statsmodels absent — odds ratios sautés")
    return metrics, pipe, X_te, adj

# ---------------------------------------------------------------- SYNTHÈSE
def run_synthese(cfg, out, zone, pipe, X_te):
    p = cfg["parametres"]
    log("SYNTHÈSE : recommandations par zone")
    topn = int(p["zones_prioritaires"]); prio = zone.head(topn).copy()
    charge_tot = zone["charge"].sum()
    for e in INFRA:
        zone["charge_"+e] = 0  # part pondérée approx. par comptages (proxy léger CLI)
    nat = {e: zone["n_"+e].sum() / max(zone["n_accidents"].sum(), 1) for e in INFRA}

    def hazard(r):
        shares = {e: (r["n_"+e]/max(r["n_accidents"],1)) / nat[e] if nat[e] > 0 else 0 for e in INFRA}
        top = max(shares, key=shares.get)
        return (top, shares[top]) if shares[top] >= float(p["lift_min"]) else ("diffus", shares[top])
    prio[["dominant","lift"]] = prio.apply(lambda r: pd.Series(hazard(r)), axis=1)

    def cond_adj(H, P):
        sub = X_te[X_te[H] == 1]
        if len(sub) < int(p["min_effectif"]): return np.nan
        if len(sub) > 50_000: sub = sub.sample(50_000, random_state=SEED)
        X0, X1 = sub.copy(), sub.copy(); X0[P] = 0; X1[P] = 1
        return float(pipe.predict_proba(X1)[:,1].mean() - pipe.predict_proba(X0)[:,1].mean())
    cond = {H: {P: cond_adj(H, P) for P in DEPLOYABLE if P != H} for H in INFRA}

    def recommend(r):
        present = {e: r["n_"+e]/max(r["n_accidents"],1) for e in INFRA}
        H = r["dominant"]
        if H == "diffus":
            return pd.Series({"amenagement": "investiguer facteur humain", "impact_graves_evites": 0.0})
        ranked = sorted([(P, v) for P, v in cond[H].items() if pd.notna(v) and v < 0],
                        key=lambda x: x[1])
        missing = [(P, v) for P, v in ranked if present[P] < float(p["presence_min"])]
        if not missing:
            return pd.Series({"amenagement": "déjà équipé — revoir géométrie", "impact_graves_evites": 0.0})
        P, v = missing[0]
        lab = "sécuriser le passage à niveau" if H == "railway" else LABELS[P]
        return pd.Series({"amenagement": lab, "impact_graves_evites": abs(v) * r["n_accidents"]})
    prio[["amenagement","impact_graves_evites"]] = prio.apply(recommend, axis=1)
    prio = prio.sort_values("impact_graves_evites", ascending=False)
    cols = ["rank","h3_cell","n_accidents","avg_severity","charge","dominant","lift",
            "amenagement","impact_graves_evites"]
    prio[cols].round(3).to_csv(outpath(cfg, out, "synthese_recommandations.csv"), index=False)
    log(f"  {topn} zones — impact total estimé "
        f"{prio['impact_graves_evites'].sum():.0f} graves évités (ex-ante)")
    return prio

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Pipeline DataValueXploring")
    ap.add_argument("--config", required=True, help="chemin du fichier YAML")
    cfg, out = load_config(ap.parse_args().config)
    a = cfg["analyses"]
    log(f"config chargée — analyses actives : "
        f"{[k for k, v in a.items() if v]} → sorties dans {out}")

    spark, df = load_clean(cfg)
    resume = {"territoire": cfg["donnees"]["territoire"], "analyses": {}}
    zone = pipe = X_te = None
    if a.get("quand"):
        resume["analyses"]["quand"] = run_quand(cfg, out, df)
    if a.get("ou") or a.get("synthese"):
        zone, _ = run_ou(cfg, out, df)
    if a.get("quoi") or a.get("synthese"):
        metrics, pipe, X_te, _ = run_quoi(cfg, out, df)
        resume["analyses"]["quoi"] = metrics
    if a.get("synthese") and zone is not None and pipe is not None:
        prio = run_synthese(cfg, out, zone, pipe, X_te)
        resume["analyses"]["synthese"] = {
            "zones": int(len(prio)),
            "impact_total_graves_evites": round(float(prio["impact_graves_evites"].sum()), 1)}
    with open(outpath(cfg, out, "resume.json"), "w", encoding="utf-8") as f:
        json.dump(resume, f, ensure_ascii=False, indent=2)
    log(f"PIPELINE OK — résumé : {outpath(cfg, out, 'resume.json')}")
    spark.stop()

if __name__ == "__main__":
    main()
