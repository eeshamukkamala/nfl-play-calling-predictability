import duckdb
import pandas as pd

con = duckdb.connect()
PBP = "read_parquet('data/play_by_play_*.parquet', union_by_name=true)"
cols = {r[0] for r in con.sql(f"describe select * from {PBP}").fetchall()}
need = {"home_score", "away_score", "home_team", "away_team"}
if not need <= cols:
    raise SystemExit(f"Missing columns: {sorted(need - cols)}")

con.execute(f"""
create table g as
select season, game_id, any_value(home_team) as home, any_value(away_team) as away,
       max(home_score) as hs, max(away_score) as aws
from {PBP} where season_type = 'REG' group by 1, 2
""")
con.execute("""
create table tg as
select season, home as team, away as opp,
       case when hs > aws then 1.0 when hs = aws then 0.5 else 0.0 end as w from g
union all
select season, away, home,
       case when aws > hs then 1.0 when hs = aws then 0.5 else 0.0 end from g
""")
con.execute("create table rec as select season, team, sum(w) as wins, count(*) as games from tg group by 1, 2")
w = con.sql("""
select a.season, a.team, avg((r.wins - (1.0 - a.w)) / (r.games - 1)) as opp_wp
from tg a join rec r on a.season = r.season and a.opp = r.team
group by 1, 2
""").df()

ours = pd.read_csv("dashboard/team_seasons_final.csv")
ours = ours[ours.sample_group == "All plays"][["season", "team", "sos", "epa_raw", "epa_adj"]]
m = w.merge(ours, on=["season", "team"])
m["wp_rank"] = m.groupby("season").opp_wp.rank(ascending=True, method="min").astype(int)
m["sos_rank"] = m.groupby("season").sos.rank(ascending=False, method="min").astype(int)

print("CORRELATION BETWEEN THE TWO MEASURES (expected negative: easy schedule = low opponent win % and high sos)")
for s, x in m.groupby("season"):
    print(f"   {s}: {x.opp_wp.corr(x.sos):+.2f}")
print(f"   all four seasons: {m.opp_wp.corr(m.sos):+.2f}\n")

print("2025 (wp_rank and sos_rank: 1 = easiest schedule of 32)")
x = m[m.season == 2025].sort_values("wp_rank")
print(x[["team", "opp_wp", "wp_rank", "sos", "sos_rank"]].round(3).head(8).to_string(index=False))
print("   ...")
print(x[x.team.isin(["PHI", "NE", "NYJ", "CLE", "TEN", "LA"])][["team", "opp_wp", "wp_rank", "sos", "sos_rank"]].round(3).to_string(index=False))
