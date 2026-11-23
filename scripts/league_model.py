import warnings
import numpy as np
import pandas as pd
import duckdb
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
con = duckdb.connect()

df = con.sql(r"""
with p as (
    select season, week, game_id, play_id, drive, posteam as team,
           down, ydstogo, yardline_100, qtr, game_seconds_remaining, score_differential,
           coalesce(posteam_timeouts_remaining, 3) as to_left,
           coalesce(shotgun, 0) as shotgun, coalesce(no_huddle, 0) as no_huddle,
           case when play_type = 'pass' then 1 else 0 end as is_pass,
           epa, yards_gained
    from read_parquet('data/play_by_play_*.parquet', union_by_name=true)
    where play_type in ('pass', 'run') and down is not null and posteam is not null
      and qtr <= 4 and epa is not null
),
j as (
    select p.*,
           coalesce(q.offense_formation = 'PISTOL', false) as pistol,
           coalesce(try_cast(nullif(regexp_extract(q.offense_personnel, '(\d+) RB', 1), '') as integer), 0) as n_rb,
           coalesce(try_cast(nullif(regexp_extract(q.offense_personnel, '(\d+) TE', 1), '') as integer), 0) as n_te,
           coalesce(try_cast(nullif(regexp_extract(q.offense_personnel, '(\d+) WR', 1), '') as integer), 0) as n_wr
    from p
    join read_parquet('data/participation_*.parquet', union_by_name=true) q
      on p.game_id = q.nflverse_game_id and p.play_id = q.play_id
    where q.offense_personnel is not null
)
select *,
       lag(is_pass) over (partition by game_id, team, drive order by play_id) as prev_pass,
       lag(yards_gained) over (partition by game_id, team, drive order by play_id) as prev_yards
from j
""").df()

df = df[(df.n_rb + df.n_te + df.n_wr).between(4, 6)].reset_index(drop=True)
df["formation"] = np.where(df.pistol.astype(bool), "pistol",
                           np.where(df.shotgun == 1, "shotgun", "under_center"))
df["personnel"] = df.n_rb.astype(str) + "RB-" + df.n_te.astype(str) + "TE-" + df.n_wr.astype(str) + "WR"
share = df.personnel.value_counts(normalize=True)
df["personnel"] = np.where(df.personnel.map(share) >= 0.01, df.personnel, "other")
df["dist_bucket"] = pd.cut(df.ydstogo, [0, 3, 6, 10, 100],
                           labels=["1-3", "4-6", "7-10", "11+"]).astype(str)
df["down_c"] = df.down.astype(int).astype(str)
df["prev_pass"] = pd.to_numeric(df.prev_pass, errors="coerce").astype("float64")
df["prev_yards"] = pd.to_numeric(df.prev_yards, errors="coerce").astype("float64")
for col in ["yardline_100", "game_seconds_remaining", "score_differential", "ydstogo", "to_left"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
df = df.dropna(subset=["yardline_100", "game_seconds_remaining", "score_differential", "ydstogo"]).reset_index(drop=True)
df["prev"] = np.where(df.prev_pass.isna(), "none", np.where(df.prev_pass == 1, "pass", "run"))
df["prev_yards"] = df.prev_yards.fillna(0).clip(-10, 30)
df["ytg"] = df.ydstogo.clip(upper=15)
df["score_c"] = df.score_differential.clip(-21, 21)

base_num = ["ytg", "yardline_100", "qtr", "game_seconds_remaining", "score_c", "to_left"]


def matrix(cats, nums):
    X = pd.get_dummies(df[cats].astype(str), dtype=float)
    return pd.concat([X, df[nums].astype(float)], axis=1).values


XB = matrix(["down_c", "dist_bucket"], base_num)
XF = matrix(["down_c", "dist_bucket", "formation", "personnel", "prev"],
            base_num + ["no_huddle", "prev_yards"])


def crossfit(X, y, wk):
    correct = lean_correct = n = 0
    for par in (0, 1):
        tr = (wk % 2) != par
        te = (wk % 2) == par
        if tr.sum() < 50 or te.sum() < 50:
            continue
        ytr = y[tr]
        maj = int(ytr.mean() >= 0.5)
        lean_correct += (y[te] == maj).sum()
        if ytr.min() == ytr.max():
            pred = np.full(te.sum(), ytr[0])
        else:
            sc = StandardScaler().fit(X[tr])
            m = LogisticRegression(C=0.3, max_iter=2000).fit(sc.transform(X[tr]), ytr)
            pred = m.predict(sc.transform(X[te]))
        correct += (pred == y[te]).sum()
        n += te.sum()
    if n == 0:
        return None
    return correct / n, lean_correct / n, n


subsets = {
    "All plays": np.ones(len(df), dtype=bool),
    "Close games": ((df.qtr <= 3) & (df.score_differential.abs() <= 7)).values,
}
rows = []
for name, mask in subsets.items():
    d = df[mask].reset_index(drop=True)
    Xb, Xf = XB[mask], XF[mask]
    for (season, team), idx in d.groupby(["season", "team"]).indices.items():
        y = d.is_pass.values[idx]
        wk = d.week.values[idx]
        full = crossfit(Xf[idx], y, wk)
        base = crossfit(Xb[idx], y, wk)
        if full is None or base is None:
            continue
        rows.append(dict(sample_group=name, season=int(season), team=team,
                         plays=len(idx), test_plays=int(full[2]),
                         epa_per_play=d.epa.values[idx].mean(), pass_rate=y.mean(),
                         lean=full[1], guess_base=base[0], guess_full=full[0]))

R = pd.DataFrame(rows)
R["gain"] = R.guess_full - R.lean
R["formation_lift"] = R.guess_full - R.guess_base
R["rank_full"] = R.groupby(["sample_group", "season"]).guess_full.rank(ascending=False, method="min").astype(int)


def c(a, b):
    return np.corrcoef(a, b)[0, 1]


for name in subsets:
    r = R[R.sample_group == name]
    y = r.epa_per_play.values
    print(f"{name.upper()}  ({len(r)} team-seasons, avg {r.plays.mean():.0f} plays each)")
    print(f"   average guess: down/distance/clock only {r.guess_base.mean():.3f}   "
          f"with formation, personnel, tempo, previous play {r.guess_full.mean():.3f}   "
          f"always the usual call {r.lean.mean():.3f}")
    print(f"   correlation with EPA/play:  guess_full {c(r.guess_full, y):+.3f}   guess_base {c(r.guess_base, y):+.3f}   "
          f"gain {c(r.gain, y):+.3f}   formation_lift {c(r.formation_lift, y):+.3f}   lean {c(r.lean, y):+.3f}")
    X = np.column_stack([np.ones(len(r)), r.lean.values, r.gain.values])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ b
    r2 = 1 - (res ** 2).sum() / ((y - y.mean()) ** 2).sum()
    print(f"   per +0.10 lean: {b[1]*0.1:+.3f} EPA/play   per +0.10 gain: {b[2]*0.1:+.3f} EPA/play   R2 = {r2:.2f}")
    print(f"   SANITY: lowest guess {r.guess_full.min():.3f}, below 0.5: {(r.guess_full < 0.5).sum()}, "
          f"avg(lean - best raw pass rate) = {np.mean(r.lean - np.maximum(r.pass_rate, 1 - r.pass_rate)):+.3f}\n")

print("EAGLES (guess_full, guess_base, league average of guess_full, rank of 32; 1 = easiest to guess)")
for name in subsets:
    print(f"  {name}")
    for _, e in R[(R.team == "PHI") & (R.sample_group == name)].sort_values("season").iterrows():
        lg = R[(R.sample_group == name) & (R.season == e.season)].guess_full.mean()
        print(f"   {int(e.season)}  full {e.guess_full:.3f}  base {e.guess_base:.3f}  league {lg:.3f}  rank {int(e.rank_full)}")

out = R.copy()
out["is_eagles"] = out.team == "PHI"
for col in ["epa_per_play", "lean", "guess_base", "guess_full", "gain", "formation_lift"]:
    out[col] = out[col].round(4)
out[["sample_group", "season", "team", "is_eagles", "plays", "test_plays", "epa_per_play",
     "lean", "guess_base", "guess_full", "gain", "formation_lift"]].sort_values(
    ["sample_group", "season", "team"]).to_csv("dashboard/team_seasons_formation.csv", index=False)
print("\nWrote dashboard/team_seasons_formation.csv")
