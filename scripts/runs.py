import duckdb
con = duckdb.connect()
q = """
with plays as (
    select posteam as team, down, play_type, epa,
           case when ydstogo <= 3 then '1-3'
                when ydstogo <= 6 then '4-6'
                when ydstogo <= 10 then '7-10'
                else '11+' end as dist
    from read_parquet('data/play_by_play_2024.parquet')
    where play_type in ('pass', 'run') and down is not null
      and posteam is not null and qtr <= 4 and epa is not null
),
league as (
    select down, dist, avg(case when play_type = 'run' then 1.0 else 0.0 end) as run_rate
    from plays group by 1, 2
),
runs as (
    select p.team, p.epa, l.run_rate
    from plays p join league l using (down, dist)
    where p.play_type = 'run'
)
select team,
       count(*) as n_runs,
       avg(epa) as epa_all,
       count(*) filter (where run_rate >= 0.6) as n_expected,
       avg(epa) filter (where run_rate >= 0.6) as epa_expected
from runs group by 1
"""
rows = con.sql(q).fetchall()
by_all = sorted(rows, key=lambda r: -r[2])
by_exp = sorted([r for r in rows if r[4] is not None], key=lambda r: -r[4])
rank_all = {r[0]: i for i, r in enumerate(by_all, 1)}
rank_exp = {r[0]: i for i, r in enumerate(by_exp, 1)}
print("2024 EPA per run play. Higher = harder to stop.\n")
print("team   runs   EPA/run (rank)    expected-run spots: n, EPA/run (rank)")
for r in by_all:
    if rank_all[r[0]] <= 5 or r[0] == "PHI":
        e = f"{r[4]:+.3f} (rank {rank_exp[r[0]]})" if r[4] is not None else "n/a"
        flag = "  <-- Eagles" if r[0] == "PHI" else ""
        print(f"{r[0]:<6} {r[1]:<6} {r[2]:+.3f} ({rank_all[r[0]]:>2})        {r[3]:<4} {e}{flag}")
print()
print(f"League average EPA per run: {sum(r[2] for r in rows)/len(rows):+.3f}")
