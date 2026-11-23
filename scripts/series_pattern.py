import duckdb

con = duckdb.connect()
src = "read_parquet('data/play_by_play_*.parquet', union_by_name=true)"

con.execute(f"""
create table m as
with p as (
    select season, posteam as team, game_id, drive, play_id, down, play_type, yards_gained,
           sum(case when down = 1 then 1 else 0 end)
               over (partition by game_id, posteam, drive order by play_id) as series
    from {src}
    where season_type = 'REG' and posteam is not null and down is not null
      and play_type in ('run', 'pass', 'punt', 'field_goal')
),
s as (
    select season, team, game_id, drive, series,
           arg_min(play_type, play_id) filter (where down = 1) as d1,
           arg_min(play_type, play_id) filter (where down = 2) as d2,
           arg_min(play_type, play_id) filter (where down = 3) as d3,
           arg_min(yards_gained, play_id) filter (where down = 1) as y1
    from p where series >= 1
    group by 1, 2, 3, 4, 5
),
a as (
    select season, team, count(*) as n3,
           avg(case when d1 = 'run' and d2 = 'run' and d3 = 'pass' then 1.0 else 0.0 end) as rrp,
           avg(case when d3 = 'pass' then 1.0 else 0.0 end) as pass3
    from s where d1 is not null and d2 is not null and d3 is not null
    group by 1, 2
),
b as (
    select season, team, count(*) as n_short,
           avg(case when d2 = 'run' then 1.0 else 0.0 end) as run2_after_short
    from s where d1 = 'run' and y1 <= 3 and d2 is not null
    group by 1, 2
)
select a.season, a.team, a.n3, a.rrp, a.pass3, b.n_short, b.run2_after_short
from a join b using (season, team)
""")

metrics = [
    ("rrp", "n3", "SHARE OF SERIES REACHING 3RD DOWN THAT WENT RUN, RUN, PASS"),
    ("run2_after_short", "n_short", "RUN ON 2ND DOWN AFTER A 1ST-DOWN RUN OF 3 YARDS OR LESS"),
    ("pass3", "n3", "PASS ON 3RD DOWN, WHEN THE SERIES REACHED 3RD DOWN"),
]
for col, ncol, label in metrics:
    print(label + "   (rank 1 = highest of 32)")
    print(con.sql(f"""
        with r as (select *, rank() over (partition by season order by {col} desc) as rk from m)
        select season, round(avg({col}), 3) as league_avg,
               max(case when team = 'PHI' then round({col}, 3) end) as phi,
               max(case when team = 'PHI' then rk end) as phi_rank_of_32,
               max(case when team = 'PHI' then {ncol} end) as phi_series
        from r group by 1 order by 1
    """))

cols = {r[0] for r in con.sql(f"describe select * from {src}").fetchall()}
if "run_location" in cols:
    print("SHARE OF RUNS UP THE MIDDLE   (rank 1 = highest of 32)")
    print(con.sql(f"""
        with t as (
            select season, posteam as team,
                   avg(case when run_location = 'middle' then 1.0 else 0.0 end) as mid
            from {src}
            where season_type = 'REG' and play_type = 'run' and run_location is not null
            group by 1, 2
        ),
        r as (select *, rank() over (partition by season order by mid desc) as rk from t)
        select season, round(avg(mid), 3) as league_avg,
               max(case when team = 'PHI' then round(mid, 3) end) as phi,
               max(case when team = 'PHI' then rk end) as phi_rank_of_32
        from r group by 1 order by 1
    """))
else:
    print("No run_location column in these files.")
