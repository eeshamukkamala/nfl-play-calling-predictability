{{ config(materialized='table') }}

select
    game_id || '_' || cast(play_id as varchar) as play_key,
    game_id,
    play_id,
    season,
    week,
    season_type,
    posteam,
    defteam,
    down,
    ydstogo,
    yardline_100,
    qtr,
    game_seconds_remaining,
    score_differential,
    case when coalesce(qb_scramble, 0) = 1 then 'pass' else play_type end as play_type, 
    epa,
    shotgun,
    no_huddle
from read_parquet('../data/play_by_play_*.parquet', union_by_name=true)
where season >= 2022
  and season_type = 'REG'
  and play_type in ('pass', 'run')
  and down is not null
  and posteam is not null
  and qtr <= 4
