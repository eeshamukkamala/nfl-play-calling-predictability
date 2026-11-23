import duckdb
import numpy as np
import os

os.makedirs("dashboard", exist_ok=True)
con = duckdb.connect()


def build(name, extra):
    con.execute(f"""
create or replace table {name} as
with plays as (
    select season, posteam as team, week, down,
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
halves as (select 0 as test_par union all select 1),
train_b as (
    select p.season, p.team, h.test_par, p.down, p.dist,
           count(*) as n, avg(p.is_pass) as pr
    from plays p join halves h on p.week % 2 <> h.test_par
    group by 1, 2, 3, 4, 5
),
train_t as (
    select p.season, p.team, h.test_par, avg(p.is_pass) as pr
    from plays p join halves h on p.week % 2 <> h.test_par
    group by 1, 2, 3
),
tst as (
    select p.season, p.team, h.test_par, p.down, p.dist, p.is_pass
    from plays p join halves h on p.week % 2 = h.test_par
),
scored as (
    select t.season, t.team,
           case when (b.pr > 0.5 and t.is_pass = 1)
                  or (b.pr < 0.5 and t.is_pass = 0) then 1.0 else 0.0 end as hit_sit,
           case when (tt.pr > 0.5 and t.is_pass = 1)
                  or (tt.pr < 0.5 and t.is_pass = 0) then 1.0 else 0.0 end as hit_lean
    from tst t
    join train_b b on t.season = b.season and t.team = b.team
                  and t.test_par = b.test_par and t.down = b.down and t.dist = b.dist
    join train_t tt on t.season = tt.season and t.team = tt.team
                   and t.test_par = tt.test_par
    where b.n >= 5 and b.pr <> 0.5 and tt.pr <> 0.5
),
acc as (
    select season, team, count(*) as scored_plays,
           avg(hit_sit) as acc2, avg(hit_lean) as acc1
    from scored group by 1, 2
),
e as (
    select season, team, count(*) as plays,
           avg(epa) as epa_play, avg(is_pass) as pass_rate
    from plays group by 1, 2
)
select e.season, e.team, e.plays, acc.scored_plays, e.epa_play, e.pass_rate,
       acc.acc1, acc.acc2, acc.acc2 - acc.acc1 as gain
from e join acc using (season, team)
""")


def report(name, label):
    rows = con.sql(f"select season, team, plays, epa_play, acc1, acc2, gain, pass_rate "
                   f"from {name} order by season, team").fetchall()
    y = np.array([r[3] for r in rows])
    lean = np.array([r[4] for r in rows])
    guess = np.array([r[5] for r in rows])
    gain = np.array([r[6] for r in rows])
    pr = np.array([r[7] for r in rows])
    plays = [r[2] for r in rows]
    print(label)
    print(f"   team-seasons: {len(rows)}   plays per team-season: avg {np.mean(plays):.0f}, min {min(plays)}")
    print(f"   correlation with EPA/play:  guessability {np.corrcoef(guess, y)[0,1]:+.3f}   "
          f"gain {np.corrcoef(gain, y)[0,1]:+.3f}   lean {np.corrcoef(lean, y)[0,1]:+.3f}")
    X = np.column_stack([np.ones(len(rows)), lean, gain])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ b
    res = y - pred
    r2 = 1 - (res ** 2).sum() / ((y - y.mean()) ** 2).sum()
    print(f"   per +0.10 lean: {b[1]*0.1:+.3f} EPA/play   per +0.10 gain: {b[2]*0.1:+.3f} EPA/play   R2 = {r2:.2f}")
    print(f"   SANITY: lowest guessability {guess.min():.3f}, team-seasons below 0.5: {(guess < 0.5).sum()}, "
          f"avg(lean - max(pass rate, 1 - pass rate)) = {np.mean(lean - np.maximum(pr, 1 - pr)):+.3f}\n")
    return rows, pred, res


build("tm_all", "")
build("tm_close", "and qtr <= 3 and abs(score_differential) <= 7")

report("tm_all", "ALL PLAYS, learned from the other half of the weeks")
rows, pred, res = report("tm_close", "CLOSE GAMES ONLY, learned from the other half of the weeks")

print("CHECKS ON THE ODD ROWS (all plays): team, season, raw pass rate, lean, guessability")
for r in con.sql("select team, season, pass_rate, acc1, acc2 from tm_all "
                 "where (team = 'LA' and season = 2020) or (team = 'CHI' and season = 2020) "
                 "or (team = 'CLE' and season = 2024)").fetchall():
    print(f"   {r[0]} {r[1]}  pass rate {r[2]:.3f}  lean {r[3]:.3f}  guessability {r[4]:.3f}")

print("\nEAGLES IN CLOSE GAMES: actual EPA, predicted, difference, rank of", len(rows))
for r, p, e in zip(rows, pred, res):
    if r[1] == "PHI":
        print(f"   {r[0]}  plays {r[2]:<4} gain {r[6]:+.3f}  actual {r[3]:+.3f}  "
              f"predicted {p:+.3f}  difference {e:+.3f}  rank {int((res > e).sum()) + 1}")

con.execute("""
copy (
    select 'All plays' as sample_group, season, team, team = 'PHI' as is_eagles,
           plays, scored_plays, round(epa_play, 4) as epa_per_play,
           round(acc1, 4) as lean, round(acc2, 4) as guessability, round(gain, 4) as gain
    from tm_all
    union all
    select 'Close games', season, team, team = 'PHI',
           plays, scored_plays, round(epa_play, 4),
           round(acc1, 4), round(acc2, 4), round(gain, 4)
    from tm_close
    order by 1, 2, 3
) to 'dashboard/team_seasons.csv' (header, delimiter ',')
""")
print("\nWrote dashboard/team_seasons.csv")
