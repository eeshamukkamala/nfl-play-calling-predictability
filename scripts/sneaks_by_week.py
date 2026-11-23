import duckdb
con = duckdb.connect()
print(con.sql("""
select p.season, p.week,
       sum(cast(f.is_qb_sneak as integer)) as sneaks,
       sum(case when cast(f.is_qb_sneak as integer) = 1 and (p.first_down = 1 or p.touchdown = 1) then 1 else 0 end) as converted
from read_parquet('data/play_by_play_*.parquet', union_by_name=true) p
join read_parquet('data/ftn_*.parquet', union_by_name=true) f
  on p.game_id = f.nflverse_game_id and cast(p.play_id as bigint) = cast(f.nflverse_play_id as bigint)
where p.season_type = 'REG' and p.posteam = 'PHI' and p.season in (2024, 2025)
  and p.play_type in ('run', 'pass')
group by 1, 2 order by 1, 2
"""))
