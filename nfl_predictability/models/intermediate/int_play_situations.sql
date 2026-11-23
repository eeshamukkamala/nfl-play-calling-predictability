select
    play_key,
    season,
    posteam,
    down,
    case
        when ydstogo <= 3 then '1-3'
        when ydstogo <= 6 then '4-6'
        when ydstogo <= 10 then '7-10'
        else '11+'
    end as distance_bucket,
    case
        when score_differential < -3 then 'trailing'
        when score_differential > 3 then 'leading'
        else 'close'
    end as score_state,
    case when yardline_100 <= 20 then 'red_zone' else 'open_field' end as field_zone,
    case when play_type = 'pass' then 1 else 0 end as is_pass,
    epa
from {{ ref('stg_pbp') }}
