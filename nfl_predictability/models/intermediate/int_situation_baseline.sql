select
    down,
    distance_bucket,
    score_state,
    field_zone,
    count(*) as plays,
    avg(is_pass) as league_pass_rate,
    case when avg(is_pass) >= 0.5 then 1 else 0 end as expected_is_pass
from {{ ref('int_play_situations') }}
group by 1, 2, 3, 4
