{{ config(materialized='table') }}

select
    nflverse_game_id as game_id,
    play_id,
    offense_personnel,
    coalesce(offense_formation = 'PISTOL', false) as is_pistol,
    coalesce(try_cast(nullif(regexp_extract(offense_personnel, '(\d+) RB', 1), '') as integer), 0) as n_rb,
    coalesce(try_cast(nullif(regexp_extract(offense_personnel, '(\d+) TE', 1), '') as integer), 0) as n_te,
    coalesce(try_cast(nullif(regexp_extract(offense_personnel, '(\d+) WR', 1), '') as integer), 0) as n_wr
from read_parquet('../data/participation_*.parquet', union_by_name=true)
where offense_personnel is not null
