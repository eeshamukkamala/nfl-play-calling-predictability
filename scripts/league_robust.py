import warnings
import numpy as np
import pandas as pd
import duckdb
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)
rng = np.random.default_rng(11)
con = duckdb.connect()
PBP = "read_parquet('data/play_by_play_*.parquet', union_by_name=true)"
cols = {r[0] for r in con.sql(f"describe select * from {PBP}").fetchall()}
scr = "coalesce(qb_scramble, 0)" if "qb_scramble" in cols else "0"

con.execute(f"""
create table base as
with p as (
    select season, week, game_id, cast(play_id as bigint) as play_id, drive,
           posteam as team, defteam, down, ydstogo, yardline_100, qtr,
           game_seconds_remaining, score_differential,
           coalesce(posteam_timeouts_remaining, 3) as to_left,
           coalesce(shotgun, 0) as shotgun, coalesce(no_huddle, 0) as no_huddle,
           case when play_type = 'pass' or {scr} = 1 then 1 else 0 end as is_pass,
           epa, yards_gained
    from {PBP}
    where season >= 2022 and season_type = 'REG'
      and play_type in ('pass', 'run') and down is not null
      and posteam is not null and defteam is not null and qtr <= 4 and epa is not null
)
select *,
       lag(is_pass, 1) over w as prev1,
       lag(is_pass, 2) over w as prev2,
       lag(yards_gained, 1) over w as prev_yards,
       row_number() over w as drive_play
from p
window w as (partition by game_id, team, drive order by play_id)
""")

allp = con.sql("select season, week, game_id, team, defteam, qtr, score_differential, epa from base").df()
allp["succ"] = (allp.epa > 0).astype(float)

df = con.sql(r"""
select b.*,
       coalesce(q.offense_formation = 'PISTOL', false) as pistol,
       coalesce(try_cast(nullif(regexp_extract(q.offense_personnel, '(\d+) RB', 1), '') as integer), 0) as n_rb,
       coalesce(try_cast(nullif(regexp_extract(q.offense_personnel, '(\d+) TE', 1), '') as integer), 0) as n_te,
       coalesce(try_cast(nullif(regexp_extract(q.offense_personnel, '(\d+) WR', 1), '') as integer), 0) as n_wr,
       cast(f.is_motion as integer) as motion
from base b
join read_parquet('data/participation_*.parquet', union_by_name=true) q
  on b.game_id = q.nflverse_game_id and b.play_id = cast(q.play_id as bigint)
join read_parquet('data/ftn_*.parquet', union_by_name=true) f
  on b.game_id = f.nflverse_game_id and b.play_id = cast(f.nflverse_play_id as bigint)
where q.offense_personnel is not null and f.is_motion is not null
""").df()

for col in ["prev1", "prev2", "prev_yards", "yardline_100", "game_seconds_remaining",
            "score_differential", "ydstogo", "to_left", "motion", "drive_play"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
df = df.dropna(subset=["yardline_100", "game_seconds_remaining", "score_differential", "ydstogo", "motion"])
df = df[(df.n_rb + df.n_te + df.n_wr).between(4, 6)].reset_index(drop=True)
df["week"] = df.week.astype(int)
df["formation"] = np.where(df.pistol.astype(bool), "pistol", np.where(df.shotgun == 1, "shotgun", "under_center"))
df["personnel"] = df.n_rb.astype(str) + "RB-" + df.n_te.astype(str) + "TE-" + df.n_wr.astype(str) + "WR"
share = df.personnel.value_counts(normalize=True)
df["personnel"] = np.where(df.personnel.map(share) >= 0.01, df.personnel, "other")
df["dist_bucket"] = pd.cut(df.ydstogo, [0, 3, 6, 10, 100], labels=["1-3", "4-6", "7-10", "11+"]).astype(str)
df["down_c"] = df.down.astype(int).astype(str)


def lab(s):
    return np.where(s.isna(), "none", np.where(s == 1, "pass", "run"))


df["prev"] = lab(df.prev1)
df["prev_b"] = lab(df.prev2)
df["prev_yards"] = df.prev_yards.fillna(0).clip(-10, 30)
df["drive_play"] = df.drive_play.clip(upper=12)
df["ytg"] = df.ydstogo.clip(upper=15)
df["score_c"] = df.score_differential.clip(-21, 21)
base_num = ["ytg", "yardline_100", "qtr", "game_seconds_remaining", "score_c", "to_left"]
Xd = pd.get_dummies(df[["down_c", "dist_bucket", "formation", "personnel", "prev", "prev_b"]].astype(str), dtype=float)
XF = pd.concat([Xd, df[base_num + ["no_huddle", "prev_yards", "drive_play"]].astype(float)], axis=1).values


def predict(kind, Xtr, ytr, Xte):
    p0 = float(np.clip(ytr.mean(), 0.02, 0.98))
    if ytr.min() == ytr.max():
        return np.full(len(Xte), p0)
    if kind == "logit":
        sc = StandardScaler().fit(Xtr)
        m = LogisticRegression(C=0.3, max_iter=2000).fit(sc.transform(Xtr), ytr)
        p = m.predict_proba(sc.transform(Xte))[:, 1]
    else:
        m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.06, max_iter=120,
                                           min_samples_leaf=20, l2_regularization=1.0, random_state=0).fit(Xtr, ytr)
        p = m.predict_proba(Xte)[:, 1]
    return np.clip(p, 1e-4, 1 - 1e-4)


def splits_oddeven(wk):
    return [((wk % 2) != par, (wk % 2) == par) for par in (0, 1)]


def splits_forward(wk):
    weeks = np.sort(np.unique(wk))
    if len(weeks) < 8:
        return []
    out = []
    for b in [weeks[4:7], weeks[7:10], weeks[10:13], weeks[13:]]:
        if len(b):
            out.append((wk < b.min(), np.isin(wk, b)))
    return out


def evaluate(X, y, wk, splits, kind):
    n = acc = ll = lean_acc = lean_ll = 0.0
    for tr, te in splits:
        if tr.sum() < 50 or te.sum() < 20:
            continue
        ytr, yte = y[tr], y[te]
        p = predict(kind, X[tr], ytr, X[te])
        p0 = float(np.clip(ytr.mean(), 0.02, 0.98))
        n += te.sum()
        acc += ((p >= 0.5) == (yte == 1)).sum()
        ll += -(yte * np.log(p) + (1 - yte) * np.log(1 - p)).sum()
        lean_acc += (yte == int(ytr.mean() >= 0.5)).sum()
        lean_ll += -(yte * np.log(p0) + (1 - yte) * np.log(1 - p0)).sum()
    if n == 0:
        return None
    return dict(acc=acc / n, gl=(lean_ll - ll) / n, lean=lean_acc / n)


schemes = {"lo": ("logit", splits_oddeven), "lf": ("logit", splits_forward),
           "go": ("gbt", splits_oddeven), "gf": ("gbt", splits_forward)}

samples = {"All plays": np.ones(len(df), dtype=bool),
           "Close games": ((df.qtr <= 3) & (df.score_differential.abs() <= 7)).values}
rows = []
for name, mask in samples.items():
    d = df[mask].reset_index(drop=True)
    X = XF[mask]
    groups = list(d.groupby(["season", "team"]).indices.items())
    for i, ((season, team), idx) in enumerate(groups):
        if i % 16 == 0:
            print(f"   fitting {name}: {i}/{len(groups)}", flush=True)
        y = d.is_pass.values[idx].astype(int)
        wk = d.week.values[idx]
        row = dict(sample_group=name, season=int(season), team=team, plays=len(idx))
        ok = True
        for key, (kind, fn) in schemes.items():
            r = evaluate(X[idx], y, wk, fn(wk), kind)
            if r is None:
                ok = False
                break
            row.update({f"acc_{key}": r["acc"], f"gl_{key}": r["gl"], f"lean_{key}": r["lean"]})
        if ok:
            rows.append(row)
R = pd.DataFrame(rows)


def ridge_adjust(d):
    out = []
    for season, x in d.groupby("season"):
        g = x.groupby(["game_id", "team", "defteam"]).agg(n=("epa", "size"), m=("epa", "mean")).reset_index()
        teams = sorted(set(g.team) | set(g.defteam))
        ix = {t: i for i, t in enumerate(teams)}
        T = len(teams)
        X = np.zeros((len(g), 2 * T))
        r = np.arange(len(g))
        X[r, g.team.map(ix).values] = 1.0
        X[r, T + g.defteam.map(ix).values] = 1.0
        m = RidgeCV(alphas=[0.1, 0.3, 1, 3, 10, 30, 100]).fit(X, g.m.values, sample_weight=g.n.values)
        deff = dict(zip(teams, m.coef_[T:]))
        g["opp_def"] = g.defteam.map(deff)
        for t in teams:
            z = g[g.team == t]
            out.append(dict(season=season, team=t, epa_adj_ridge=float(m.intercept_ + m.coef_[ix[t]]),
                            sos_ridge=float(np.average(z.opp_def, weights=z.n)) if len(z) else np.nan,
                            alpha=float(m.alpha_)))
    return pd.DataFrame(out)


old = pd.read_csv("dashboard/team_seasons_final.csv")[["sample_group", "season", "team", "epa_adj", "sos"]]
old = old.rename(columns={"epa_adj": "epa_adj_old", "sos": "sos_old"})
close = (allp.qtr <= 3) & (allp.score_differential.abs() <= 7)
out_frames = []
for name, a in {"All plays": allp, "Close games": allp[close]}.items():
    t = a.groupby(["season", "team"]).agg(epa_raw=("epa", "mean"), success=("succ", "mean")).reset_index()
    t = t.merge(ridge_adjust(a), on=["season", "team"])
    t["sample_group"] = name
    out_frames.append(t)
O = pd.concat(out_frames).merge(old, on=["sample_group", "season", "team"])
M = R.merge(O, on=["sample_group", "season", "team"])


def boot(a, b, teams, reps=2000):
    u = np.unique(teams)
    g = [np.where(teams == t)[0] for t in u]
    out = np.empty(reps)
    for i in range(reps):
        pick = rng.integers(0, len(u), len(u))
        idx = np.concatenate([g[k] for k in pick])
        out[i] = np.corrcoef(a[idx], b[idx])[0, 1]
    return np.nanpercentile(out, [2.5, 97.5])


def demean(s, x):
    s = pd.Series(np.asarray(s, dtype=float))
    return (s - s.groupby(x.team.values).transform("mean")
              - s.groupby(x.season.values).transform("mean") + s.mean()).values


labels = {"acc_lo": "logistic, odd/even weeks (as in README)", "acc_lf": "logistic, forward-only",
          "acc_go": "boosted trees, odd/even weeks", "acc_gf": "boosted trees, forward-only",
          "gl_gf": "gain over usual call (log loss), boosted forward", "lean_lf": "lean (usual call), forward"}
outs = {"epa_adj_ridge": "ridge opponent-adjusted EPA/play", "epa_adj_old": "average-of-opponents adjusted EPA/play",
        "success": "success rate (share of plays with EPA > 0)"}

for name in samples:
    x = M[M.sample_group == name].reset_index(drop=True)
    print(f"\n{name.upper()}  ({len(x)} team-seasons)")
    print("   average accuracy:  " + "   ".join(f"{k} {x[k].mean():.3f}" for k in ["acc_lo", "acc_lf", "acc_go", "acc_gf"])
          + f"   usual call (odd/even {x.lean_lo.mean():.3f}, forward {x.lean_lf.mean():.3f})")
    print("   team-seasons below 0.5: " + ", ".join(f"{k} {(x[k] < 0.5).sum()}" for k in ["acc_lo", "acc_lf", "acc_go", "acc_gf"]))
    print(f"   ridge adjustment vs average-of-opponents: corr of adjusted EPA {x.epa_adj_ridge.corr(x.epa_adj_old):+.2f}, "
          f"corr of schedule {x.sos_ridge.corr(x.sos_old):+.2f}, std of ridge schedule {x.sos_ridge.std():.3f}, alphas {sorted(x.alpha.unique())}")
    for oc, ol in outs.items():
        y = x[oc].values
        print(f"   CORRELATION WITH {ol.upper()}   plain r [95% team-bootstrap]   within-team r [95%]")
        for k, kl in labels.items():
            v = x[k].values
            r = np.corrcoef(v, y)[0, 1]
            lo, hi = boot(v, y, x.team.values)
            vw, yw = demean(v, x), demean(y, x)
            rw = np.corrcoef(vw, yw)[0, 1]
            lw, hw = boot(vw, yw, x.team.values)
            print(f"      {kl:<52} {r:+.3f} [{lo:+.2f}, {hi:+.2f}]    {rw:+.3f} [{lw:+.2f}, {hw:+.2f}]")

a = M[M.sample_group == "All plays"]
print("\nPERSISTENCE ACROSS SEASONS (all plays), pooled")
for k in ["acc_lo", "acc_gf", "epa_adj_ridge"]:
    p = a.pivot(index="team", columns="season", values=k)
    xs = np.concatenate([(p[s] - p[s].mean()).values for s in [2022, 2023, 2024]])
    ys = np.concatenate([(p[s + 1] - p[s + 1].mean()).values for s in [2022, 2023, 2024]])
    print(f"   {k:<14} {np.corrcoef(xs, ys)[0, 1]:+.2f}")

for name in samples:
    x = M[M.sample_group == name].copy()
    for k in ["acc_lo", "acc_lf", "acc_gf"]:
        x[f"rank_{k}"] = x.groupby("season")[k].rank(ascending=False, method="min").astype(int)
    x["rank_epa"] = x.groupby("season").epa_adj_ridge.rank(ascending=False, method="min").astype(int)
    x["rank_sos"] = x.groupby("season").sos_ridge.rank(ascending=False, method="min").astype(int)
    lg = x.groupby("season")[["acc_lo", "acc_lf", "acc_gf"]].mean().add_suffix("_lg")
    print(f"\nEAGLES, {name.upper()}: accuracy (league average, rank of 32, 1 = easiest to guess)")
    for _, e in x[x.team == "PHI"].join(lg, on="season").sort_values("season").iterrows():
        print(f"   {int(e.season)}  odd/even logit {e.acc_lo:.3f} ({e.acc_lo_lg:.3f}, {int(e.rank_acc_lo)})   "
              f"forward logit {e.acc_lf:.3f} ({e.acc_lf_lg:.3f}, {int(e.rank_acc_lf)})   "
              f"forward trees {e.acc_gf:.3f} ({e.acc_gf_lg:.3f}, {int(e.rank_acc_gf)})   "
              f"ridge adj EPA {e.epa_adj_ridge:+.3f} (rank {int(e.rank_epa)}, schedule rank {int(e.rank_sos)})")
    ne = x[(x.team == "NE") & (x.season == 2025)]
    if len(ne):
        e = ne.iloc[0]
        print(f"   NE 2025: raw EPA {e.epa_raw:+.3f}, ridge adj {e.epa_adj_ridge:+.3f} (rank {int(e.rank_epa)}), schedule rank {int(e.rank_sos)} (1 = easiest)")

M.round(4).to_csv("dashboard/team_seasons_robust.csv", index=False)
print("\nWrote dashboard/team_seasons_robust.csv")
