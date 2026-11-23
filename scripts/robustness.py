import numpy as np
import pandas as pd

d = pd.read_csv("dashboard/team_seasons_final.csv")
rng = np.random.default_rng(7)


def boot(a, b, teams, reps=5000):
    u = np.unique(teams)
    groups = [np.where(teams == t)[0] for t in u]
    out = np.empty(reps)
    for i in range(reps):
        pick = rng.integers(0, len(u), len(u))
        idx = np.concatenate([groups[k] for k in pick])
        out[i] = np.corrcoef(a[idx], b[idx])[0, 1]
    return np.percentile(out, [2.5, 97.5])


def demean(s, x):
    s = pd.Series(s)
    return (s - s.groupby(x.team.values).transform("mean")
              - s.groupby(x.season.values).transform("mean") + s.mean()).values


for g in ["All plays", "Close games"]:
    x = d[d.sample_group == g].reset_index(drop=True)
    teams = x.team.values
    y = x.epa_adj.values
    print(f"{g.upper()}  ({len(x)} team-seasons from {x.team.nunique()} teams)")
    print("   correlation with opponent-adjusted EPA/play")
    print("   variable        plain r  [95% team-bootstrap interval]    within-team r  [95% interval]")
    for col in ["guess_full", "gain_ll", "lean", "scramble_rate"]:
        v = x[col].values
        r = np.corrcoef(v, y)[0, 1]
        lo, hi = boot(v, y, teams)
        vw, yw = demean(v, x), demean(y, x)
        rw = np.corrcoef(vw, yw)[0, 1]
        lw, hw = boot(vw, yw, teams)
        print(f"   {col:<14} {r:+.3f}   [{lo:+.2f}, {hi:+.2f}]               {rw:+.3f}        [{lw:+.2f}, {hw:+.2f}]")
    print()

print("PERSISTENCE ACROSS SEASONS (all plays): correlation of a team's value in one season with the next")
a = d[d.sample_group == "All plays"]
for col in ["guess_full", "lean", "epa_adj"]:
    p = a.pivot(index="team", columns="season", values=col)
    rs = [p[s].corr(p[s + 1]) for s in [2022, 2023, 2024]]
    xs = np.concatenate([(p[s] - p[s].mean()).values for s in [2022, 2023, 2024]])
    ys = np.concatenate([(p[s + 1] - p[s + 1].mean()).values for s in [2022, 2023, 2024]])
    print(f"   {col:<12} 22to23 {rs[0]:+.2f}   23to24 {rs[1]:+.2f}   24to25 {rs[2]:+.2f}   pooled {np.corrcoef(xs, ys)[0, 1]:+.2f}")
