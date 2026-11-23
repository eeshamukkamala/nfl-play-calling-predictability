import duckdb
import os

os.makedirs("dashboard", exist_ok=True)
con = duckdb.connect()


def build(name, extra):
    con.execute(f"""
create or replace table {name} as
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


build("tm_all", "")
build("tm_close", "and qtr <= 3 and abs(score_differential) <= 7")

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

print(con.sql("select sample_group, count(*) as rows, round(corr(gain, epa_per_play), 3) as corr_gain from read_csv('dashboard/team_seasons.csv') group by 1"))
