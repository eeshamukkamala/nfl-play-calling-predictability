import duckdb
con = duckdb.connect()
con.execute("""
create view j as
select p.season, p.team, cast(f.is_motion as integer) as motion
from (select season, game_id, cast(play_id as bigint) as play_id, posteam as team
      from read_parquet('data/play_by_play_*.parquet', union_by_name=true)
      where season_type = 'REG' and play_type in ('pass', 'run') and posteam is not null) p
left join (select nflverse_game_id, cast(nflverse_play_id as bigint) as play_id, is_motion
           from read_parquet('data/ftn_*.parquet', union_by_name=true)) f
  on p.game_id = f.nflverse_game_id and p.play_id = f.play_id
""")
print("COVERAGE: run/pass plays and how many have a motion value")
print(con.sql("select season, count(*) as plays, count(motion) as with_motion, round(count(motion) * 1.0 / count(*), 3) as share from j group by 1 order by 1"))
print("MOTION RATE (rank 1 = most motion of 32)")
print(con.sql("""
with t as (select season, team, count(motion) as n, avg(motion) as rate from j where motion is not null group by 1, 2),
r as (select *, rank() over (partition by season order by rate desc) as rk from t)
select season, round(avg(rate), 3) as league_avg,
       max(case when team = 'PHI' then round(rate, 3) end) as phi_rate,
       max(case when team = 'PHI' then rk end) as phi_rank_of_32
from r group by 1 order by 1
"""))
