import duckdb
con = duckdb.connect()
q = """
with plays as (
    select posteam as team, down,
           case when ydstogo <= 3 then '1-3'
                when ydstogo <= 6 then '4-6'
                when ydstogo <= 10 then '7-10'
                else '11+' end as dist,
           case when play_type = 'pass' then 1 else 0 end as is_pass
    from read_parquet('data/play_by_play_2024.parquet')
    where play_type in ('pass', 'run') and down is not null
      and posteam is not null and qtr <= 4
),
level1 as (
    select team, count(*) as plays,
           greatest(avg(is_pass), 1 - avg(is_pass)) as acc1
    from plays group by 1
),
buckets as (
    select team, down, dist, count(*) as n,
           greatest(sum(is_pass), count(*) - sum(is_pass)) as correct
    from plays group by 1, 2, 3
),
level2 as (
    select team, sum(correct) * 1.0 / sum(n) as acc2
    from buckets group by 1
)
select l1.team, l1.plays, l1.acc1, l2.acc2
from level1 l1 join level2 l2 using (team)
order by l2.acc2 desc
"""
rows = con.sql(q).fetchall()
print("2024 season, 32 teams. Higher = easier to guess.\n")
print("team   plays   level 1   level 2")
for i, r in enumerate(rows, 1):
    if i <= 5 or i > len(rows) - 5 or r[0] == "PHI":
        flag = "  <-- Eagles" if r[0] == "PHI" else ""
        print(f"{r[0]:<6} {r[1]:<7} {r[2]:.3f}     {r[3]:.3f}   (rank {i} of {len(rows)}){flag}")
print()
print(f"League average:  level 1 = {sum(r[2] for r in rows)/len(rows):.3f}   level 2 = {sum(r[3] for r in rows)/len(rows):.3f}")
