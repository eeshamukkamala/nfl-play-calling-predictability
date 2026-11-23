import duckdb
con = duckdb.connect()
print(con.sql("""
with j as (
    select p.season, p.posteam as team,
           cast(f.is_qb_sneak as integer) as sneak,
           case when p.first_down = 1 or p.touchdown = 1 then 1.0 else 0.0 end as conv
    from read_parquet('data/play_by_play_*.parquet', union_by_name=true) p
    join read_parquet('data/ftn_*.parquet', union_by_name=true) f
      on p.game_id = f.nflverse_game_id and cast(p.play_id as bigint) = cast(f.nflverse_play_id as bigint)
    where p.season_type = 'REG' and p.posteam is not null and p.play_type in ('run', 'pass')
),
t as (
    select season, team,
           sum(case when sneak = 1 then 1 else 0 end) as sneaks,
           avg(conv) filter (where sneak = 1) as conv
    from j group by 1, 2
),
r as (select *, rank() over (partition by season order by sneaks desc) as rk from t)
select season,
       round(avg(sneaks), 1) as league_avg_sneaks,
       round(avg(conv), 3) as league_conv,
       max(case when team = 'PHI' then sneaks end) as phi_sneaks,
       max(case when team = 'PHI' then rk end) as phi_rank_of_32,
       max(case when team = 'PHI' then round(conv, 3) end) as phi_conv
from r group by 1 order by 1
"""))
