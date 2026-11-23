import duckdb
import numpy as np

con = duckdb.connect()


def build(name, extra):
    con.execute(f"drop table if exists {name}")
    con.execute(f"""
create table {name} as
with plays as (
    select season, posteam as team, down,
           case when ydstogo <= 3 then '1-3'
                when ydstogo <= 6 then '4-6'
                when ydstogo <= 10 then '7-10'
                else '11+' end as dist,
           case when play_type = 'pass' then 1 else 0 end as is_pass,
           epa
    from read_parquet('data/play_by_play_*.parquet', union_by_name=true)
    where play_type in ('pass', 'run') and down is not null
      and posteam is not null and qtr <= 4 and epa is not null {extra}
),
loo as (
    select season, team, is_pass,
           count(*) over (partition by season, team, down, dist) - 1 as bn,
           sum(is_pass) over (partition by season, team, down, dist) - is_pass as bp,
           count(*) over (partition by season, team) - 1 as tn,
           sum(is_pass) over (partition by season, team) - is_pass as tp
    from plays
),
scored as (
    select season, team,
           case when (bp * 1.0 / bn > 0.5 and is_pass = 1)
                  or (bp * 1.0 / bn < 0.5 and is_pass = 0) then 1.0 else 0.0 end as hit_sit,
           case when (tp * 1.0 / tn > 0.5 and is_pass = 1)
                  or (tp * 1.0 / tn < 0.5 and is_pass = 0) then 1.0 else 0.0 end as hit_lean
    from loo
    where bn >= 5 and bp * 1.0 / bn <> 0.5 and tn > 0 and tp * 1.0 / tn <> 0.5
),
acc as (
    select season, team, count(*) as scored_plays,
           avg(hit_sit) as acc2, avg(hit_lean) as acc1
    from scored group by 1, 2
),
e as (
    select season, team, count(*) as plays, avg(epa) as epa_play
    from plays group by 1, 2
)
select e.season, e.team, e.plays, acc.scored_plays, e.epa_play,
       acc.acc1, acc.acc2, acc.acc2 - acc.acc1 as gain
from e join acc using (season, team)
""")


def report(name, label):
    rows = con.sql(f"select * from {name} order by season, team").fetchall()
    y = np.array([r[4] for r in rows])
    acc1 = np.array([r[5] for r in rows])
    acc2 = np.array([r[6] for r in rows])
    gain = np.array([r[7] for r in rows])
    plays = [r[2] for r in rows]
    print(label)
    print(f"   team-seasons: {len(rows)}   plays per team-season: avg {np.mean(plays):.0f}, min {min(plays)}")
    print(f"   correlation with EPA/play:  guessability {np.corrcoef(acc2, y)[0,1]:+.3f}   gain {np.corrcoef(gain, y)[0,1]:+.3f}   lean {np.corrcoef(acc1, y)[0,1]:+.3f}")
    X = np.column_stack([np.ones(len(rows)), acc1, gain])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ b
    res = y - pred
    r2 = 1 - (res ** 2).sum() / ((y - y.mean()) ** 2).sum()
    print(f"   per +0.10 lean: {b[1]*0.1:+.3f} EPA/play   per +0.10 gain: {b[2]*0.1:+.3f} EPA/play   R2 = {r2:.2f}\n")
    return rows, pred, res


print("A. ALL PLAYS, guesses scored on the plays they came from (earlier result)")
print("   correlation with EPA/play:  guessability +0.031   gain +0.248   lean -0.237")
print("   per +0.10 lean: -0.016 EPA/play   per +0.10 gain: +0.031 EPA/play   R2 = 0.06\n")

build("tm_all", "")
report("tm_all", "B. ALL PLAYS, each guess made from the team's other plays only")

build("tm_close", "and qtr <= 3 and abs(score_differential) <= 7")
rows, pred, res = report("tm_close", "C. CLOSE GAMES ONLY (first three quarters, score within 7), other plays only")

print("EAGLES IN C: actual EPA, predicted from predictability, difference, rank of", len(rows))
for r, p, e in zip(rows, pred, res):
    if r[1] == "PHI":
        print(f"   {r[0]}  plays {r[2]:<4} gain {r[7]:+.3f}  actual {r[4]:+.3f}  predicted {p:+.3f}  difference {e:+.3f}  rank {int((res > e).sum()) + 1}")
