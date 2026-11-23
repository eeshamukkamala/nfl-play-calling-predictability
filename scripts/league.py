import duckdb
con = duckdb.connect()
con.execute("""
create table tm as
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
      and posteam is not null and qtr <= 4 and epa is not null
),
team as (
    select season, team, count(*) as plays, avg(epa) as epa_play,
           greatest(avg(is_pass), 1 - avg(is_pass)) as acc1
    from plays group by 1, 2
),
buckets as (
    select season, team, down, dist, count(*) as n,
           greatest(sum(is_pass), count(*) - sum(is_pass)) as correct
    from plays group by 1, 2, 3, 4
),
level2 as (
    select season, team, sum(correct) * 1.0 / sum(n) as acc2
    from buckets group by 1, 2
)
select t.season, t.team, t.plays, t.epa_play, t.acc1, l.acc2, l.acc2 - t.acc1 as gain
from team t join level2 l using (season, team)
""")

print("1. DO PREDICTABILITY AND SUCCESS MOVE TOGETHER? (192 team-seasons)")
print("   Correlation with EPA per play. Negative = predictable teams did worse.\n")
print(con.sql("""
select count(*) as team_seasons,
       round(corr(acc2, epa_play), 3) as corr_guessability,
       round(corr(gain, epa_play), 3) as corr_gain,
       round(corr(acc1, epa_play), 3) as corr_lean_only
from tm"""))

print("\n2. SAME QUESTION IN GROUPS: team-seasons split into four, least to most predictable (by gain)\n")
print(con.sql("""
select q as group_1_least_4_most, count(*) as n,
       round(avg(gain), 3) as avg_gain,
       round(avg(epa_play), 3) as avg_epa_per_play
from (select *, ntile(4) over (order by gain) as q from tm)
group by 1 order by 1"""))

print("\n3. THE EAGLES\n")
print(con.sql("""
select season, round(acc2, 3) as guessability, round(gain, 3) as gain,
       round(epa_play, 3) as epa_per_play
from tm where team = 'PHI' order by season"""))

import numpy as np
rows = con.sql("select season, team, epa_play, acc1, gain from tm order by 1, 2").fetchall()
y = np.array([r[2] for r in rows])
X = np.column_stack([np.ones(len(rows)), [r[3] for r in rows], [r[4] for r in rows]])
b, *_ = np.linalg.lstsq(X, y, rcond=None)
pred = X @ b
res = y - pred
r2 = 1 - (res ** 2).sum() / ((y - y.mean()) ** 2).sum()
print("\n4. EPA PER PLAY AFTER ACCOUNTING FOR PREDICTABILITY\n")
print(f"   Per +0.10 in lean: {b[1]*0.1:+.3f} EPA/play.  Per +0.10 in gain: {b[2]*0.1:+.3f} EPA/play.  R2 = {r2:.2f}")
print("\n   Eagles: actual, predicted from predictability alone, difference, rank of 192\n")
for r, p, e in zip(rows, pred, res):
    if r[1] == "PHI":
        print(f"   {r[0]}  actual {r[2]:+.3f}  predicted {p:+.3f}  difference {e:+.3f}  rank {int((res > e).sum()) + 1}")
print("\n   Top 5 team-seasons beyond what predictability explains:")
for i in np.argsort(-res)[:5]:
    print(f"   {rows[i][0]} {rows[i][1]}  {res[i]:+.3f}")
