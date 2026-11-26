import sys
import numpy as np
import pandas as pd
import duckdb
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

pd.set_option("display.width", 200)
use_relabel = 0 if "--no-relabel" in sys.argv else 1
suffix = "" if use_relabel else "_norelabel"
con = duckdb.connect()
PBP = "read_parquet('data/play_by_play_*.parquet', union_by_name=true)"

cols = {r[0] for r in con.sql(f"describe select * from {PBP}").fetchall()}
if "qb_scramble" in cols:
    scr = "coalesce(qb_scramble, 0)"
else:
    scr = "0"
    print("WARNING: no qb_scramble column in the play-by-play files; scrambles cannot be identified.\n")
print("Scrambles relabeled as passes:", "yes" if use_relabel else "NO (--no-relabel)", "\n")

con.execute(f"""
create table base as
with p as (
    select season, week, game_id, cast(play_id as bigint) as play_id, drive,
           posteam as team, defteam, down, ydstogo, yardline_100, qtr,
           game_seconds_remaining, score_differential,
           coalesce(posteam_timeouts_remaining, 3) as to_left,
           coalesce(shotgun, 0) as shotgun, coalesce(no_huddle, 0) as no_huddle,
           case when play_type = 'pass' then 1 else 0 end as pass_raw,
           {scr} as scramble,
           case when play_type = 'pass' or ({scr} = 1 and {use_relabel} = 1) then 1 else 0 end as is_pass,
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

allp = con.sql("select season, week, team, defteam, qtr, score_differential, epa, is_pass, pass_raw, scramble from base").df()

df = con.sql(r"""
select b.*,
       coalesce(q.offense_formation = 'PISTOL', false) as pistol,
       coalesce(try_cast(nullif(regexp_extract(q.offense_personnel, '(\d+) RB', 1), '') as integer), 0) as n_rb,
       coalesce(try_cast(nullif(regexp_extract(q.offense_personnel, '(\d+) TE', 1), '') as integer), 0) as n_te,
       coalesce(try_cast(nullif(regexp_extract(q.offense_personnel, '(\d+) WR', 1), '') as integer), 0) as n_wr,
       cast(f.is_motion as integer) as motion,
       try_cast(f.n_offense_backfield as integer) as backfield,
       cast(f.starting_hash as varchar) as hash,
       cast(f.qb_location as varchar) as qbloc
from base b
join read_parquet('data/participation_*.parquet', union_by_name=true) q
  on b.game_id = q.nflverse_game_id and b.play_id = cast(q.play_id as bigint)
join read_parquet('data/ftn_*.parquet', union_by_name=true) f
  on b.game_id = f.nflverse_game_id and b.play_id = cast(f.nflverse_play_id as bigint)
where q.offense_personnel is not null and f.is_motion is not null
""").df()

num = ["prev1", "prev2", "prev_yards", "yardline_100", "game_seconds_remaining", "score_differential",
       "ydstogo", "to_left", "motion", "backfield", "drive_play"]
for col in num:
    df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
df = df.dropna(subset=["yardline_100", "game_seconds_remaining", "score_differential", "ydstogo", "motion"])
df = df[(df.n_rb + df.n_te + df.n_wr).between(4, 6)].reset_index(drop=True)

cov = pd.DataFrame({"eligible_plays": allp.groupby("season").size(), "modeled_plays": df.groupby("season").size()})
cov["share_modeled"] = (cov.modeled_plays / cov.eligible_plays).round(3)
print("COVERAGE (regular-season run and pass plays)")
print(cov, "\n")

season_tbl = allp.groupby("season").agg(dropbacks=("is_pass", "sum"), scrambles=("scramble", "sum"),
                                        pass_rate_before=("pass_raw", "mean"), pass_rate_after=("is_pass", "mean"))
season_tbl["scrambles_per_100_dropbacks"] = 100 * season_tbl.scrambles / season_tbl.dropbacks
print("SCRAMBLES, LEAGUE-WIDE")
print(season_tbl.round(3), "\n")

df["formation"] = np.where(df.pistol.astype(bool), "pistol",
                           np.where(df.shotgun == 1, "shotgun", "under_center"))
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
df["backfield"] = df.backfield.fillna(1).clip(0, 5)
df["hash"] = df.hash.fillna("unk").astype(str)
df["qbloc"] = df.qbloc.fillna("unk").astype(str)

base_num = ["ytg", "yardline_100", "qtr", "game_seconds_remaining", "score_c", "to_left"]


def matrix(cats, nums):
    X = pd.get_dummies(df[cats].astype(str), dtype=float)
    return pd.concat([X, df[nums].astype(float)], axis=1).values


XB = matrix(["down_c", "dist_bucket"], base_num)
XF = matrix(["down_c", "dist_bucket", "formation", "personnel", "prev", "prev_b"],
            base_num + ["no_huddle", "prev_yards", "drive_play"])
XM = matrix(["down_c", "dist_bucket", "formation", "personnel", "prev", "prev_b", "hash", "qbloc"],
            base_num + ["no_huddle", "prev_yards", "drive_play", "motion", "backfield"])


def crossfit(X, y, wk):
    res = []
    for par in (0, 1):
        tr = (wk % 2) != par
        te = (wk % 2) == par
        if tr.sum() < 50 or te.sum() < 50:
            return None
        ytr, yte = y[tr], y[te]
        p0 = float(np.clip(ytr.mean(), 0.02, 0.98))
        lean_acc = float((yte == int(ytr.mean() >= 0.5)).mean())
        lean_ll = float(-np.mean(yte * np.log(p0) + (1 - yte) * np.log(1 - p0)))
        if ytr.min() == ytr.max():
            p = np.full(te.sum(), p0)
        else:
            sc = StandardScaler().fit(X[tr])
            m = LogisticRegression(C=0.3, max_iter=2000).fit(sc.transform(X[tr]), ytr)
            p = np.clip(m.predict_proba(sc.transform(X[te]))[:, 1], 1e-4, 1 - 1e-4)
        acc = float(((p >= 0.5) == (yte == 1)).mean())
        ll = float(-np.mean(yte * np.log(p) + (1 - yte) * np.log(1 - p)))
        res.append(dict(n=int(te.sum()), acc=acc, ll=ll, lean_acc=lean_acc, lean_ll=lean_ll))
    return res


def comb(res, k):
    n = np.array([r["n"] for r in res])
    return float(np.sum([r[k] * r["n"] for r in res]) / n.sum())


subsets = {
    "All plays": np.ones(len(df), dtype=bool),
    "Close games": ((df.qtr <= 3) & (df.score_differential.abs() <= 7)).values,
}
rows = []
for name, mask in subsets.items():
    d = df[mask].reset_index(drop=True)
    Xb, Xf, Xm = XB[mask], XF[mask], XM[mask]
    for (season, team), idx in d.groupby(["season", "team"]).indices.items():
        y = d.is_pass.values[idx].astype(int)
        wk = d.week.values[idx]
        b = crossfit(Xb[idx], y, wk)
        f = crossfit(Xf[idx], y, wk)
        m = crossfit(Xm[idx], y, wk)
        if b is None or f is None or m is None:
            continue
        rows.append(dict(sample_group=name, season=int(season), team=team, plays=len(idx),
                         guess_base=comb(b, "acc"), guess_full=comb(f, "acc"), guess_motion=comb(m, "acc"),
                         lean=comb(f, "lean_acc"), ll_full=comb(f, "ll"), ll_lean=comb(f, "lean_ll"),
                         f_a0=f[0]["acc"], f_a1=f[1]["acc"], f_l0=f[0]["lean_acc"], f_l1=f[1]["lean_acc"],
                         f_g0=f[0]["lean_ll"] - f[0]["ll"], f_g1=f[1]["lean_ll"] - f[1]["ll"]))

R = pd.DataFrame(rows)
R["gain_acc"] = R.guess_full - R.lean
R["gain_ll"] = R.ll_lean - R.ll_full


def adjust(d):
    pair = d.groupby(["season", "team", "defteam"]).agg(pn=("epa", "size"), ps=("epa", "sum")).reset_index()
    dtot = d.groupby(["season", "defteam"]).agg(dn=("epa", "size"), ds=("epa", "sum")).reset_index()
    pair = pair.merge(dtot, on=["season", "defteam"])
    pair["lo_n"] = pair.dn - pair.pn
    pair = pair[pair.lo_n > 0].copy()
    pair["lo_avg"] = (pair.ds - pair.ps) / pair.lo_n
    pair["exp_sum"] = pair.lo_avg * pair.pn
    a = pair.groupby(["season", "team"]).agg(exp_sum=("exp_sum", "sum"), pn=("pn", "sum"), ps=("ps", "sum")).reset_index()
    a["epa_raw"] = a.ps / a.pn
    a["sos"] = a.exp_sum / a.pn
    a["epa_adj"] = a.epa_raw - a.sos
    return a[["season", "team", "epa_raw", "sos", "epa_adj"]]


close = (allp.qtr <= 3) & (allp.score_differential.abs() <= 7)
adj = {"All plays": adjust(allp), "Close games": adjust(allp[close])}
scr_t = allp.groupby(["season", "team"]).agg(dropbacks=("is_pass", "sum"), scrambles=("scramble", "sum")).reset_index()
scr_t["scramble_rate"] = scr_t.scrambles / scr_t.dropbacks


def c(a, b):
    return np.corrcoef(a, b)[0, 1]


def rel(a0, a1, season):
    x0 = a0 - a0.groupby(season).transform("mean")
    x1 = a1 - a1.groupby(season).transform("mean")
    r = np.corrcoef(x0, x1)[0, 1]
    return r, 2 * r / (1 + r)


out_frames = []
for name in subsets:
    r = (R[R.sample_group == name]
         .merge(adj[name], on=["season", "team"])
         .merge(scr_t[["season", "team", "scramble_rate"]], on=["season", "team"])
         .reset_index(drop=True))
    n = len(r)
    print(f"{name.upper()}  ({n} team-seasons, 2022-2025, avg {r.plays.mean():.0f} plays each)")
    print(f"   average guess: base {r.guess_base.mean():.3f}   full {r.guess_full.mean():.3f}   "
          f"+motion {r.guess_motion.mean():.3f}   always the usual call {r.lean.mean():.3f}")
    for label, a0, a1 in [("guess (accuracy)", r.f_a0, r.f_a1),
                          ("gain (accuracy)", r.f_a0 - r.f_l0, r.f_a1 - r.f_l1),
                          ("gain (log loss)", r.f_g0, r.f_g1)]:
        r1, rsb = rel(a0, a1, r.season)
        print(f"   RELIABILITY, {label}: odd-vs-even weeks r = {r1:+.2f}, full-season estimate {rsb:+.2f}")
    print(f"   SCHEDULE: std of the opponent adjustment {r.sos.std():.3f}; std of raw EPA/play {r.epa_raw.std():.3f}; "
          f"std of adjusted {r.epa_adj.std():.3f}")
    print(f"   noise threshold for a correlation with {n} team-seasons: about +/-{2 / np.sqrt(n):.2f}")
    print("   correlation with EPA/play (raw / opponent-adjusted):")
    for label, v in [("guess_full", r.guess_full), ("gain_ll", r.gain_ll), ("lean", r.lean),
                     ("scramble rate", r.scramble_rate)]:
        print(f"      {label:<14} {c(v, r.epa_raw):+.3f} / {c(v, r.epa_adj):+.3f}")
    print(f"   correlation of scramble rate with guess_full: {c(r.scramble_rate, r.guess_full):+.3f}")
    X = np.column_stack([np.ones(n), r.lean.values, r.gain_ll.values])
    y = r.epa_adj.values
    bb, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ bb
    r2 = 1 - (res ** 2).sum() / ((y - y.mean()) ** 2).sum()
    print(f"   R2 of adjusted EPA on lean + gain_ll: {r2:.2f}")
    print(f"   SANITY: team-seasons with guess below 0.5: {(r.guess_full < 0.5).sum()}\n")

    r["guess_rank"] = r.groupby("season").guess_full.rank(ascending=False, method="min").astype(int)
    r["adj_rank"] = r.groupby("season").epa_adj.rank(ascending=False, method="min").astype(int)
    print("   EAGLES: season | guess_full (league avg, rank of 32, 1 = easiest) | gain_ll | "
          "scramble rate (league avg) | schedule adj | EPA raw -> adjusted (rank, 1 = best)")
    for _, e in r[r.team == "PHI"].sort_values("season").iterrows():
        sub = r[r.season == e.season]
        print(f"      {int(e.season)}  {e.guess_full:.3f} ({sub.guess_full.mean():.3f}, {int(e.guess_rank)})  "
              f"{e.gain_ll:+.3f}  {e.scramble_rate:.3f} ({sub.scramble_rate.mean():.3f})  {e.sos:+.3f}  "
              f"{e.epa_raw:+.3f} -> {e.epa_adj:+.3f} ({int(e.adj_rank)})")
    print()
    out_frames.append(r)

final = pd.concat(out_frames)
final["is_eagles"] = final.team == "PHI"
keep = ["sample_group", "season", "team", "is_eagles", "plays", "epa_raw", "sos", "epa_adj", "scramble_rate",
        "lean", "guess_base", "guess_full", "guess_motion", "gain_acc", "gain_ll", "guess_rank", "adj_rank"]
final[keep].round(4).sort_values(["sample_group", "season", "team"]).to_csv(
    f"dashboard/team_seasons_final{suffix}.csv", index=False)
print(f"Wrote dashboard/team_seasons_final{suffix}.csv")
