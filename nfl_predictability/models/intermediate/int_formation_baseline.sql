select
    down,
    distance_bucket,
    score_state,
    personnel_group,
    formation_group,
    count(*) as plays,
    avg(is_pass) as league_pass_rate
from {{ ref('int_play_formations') }}
group by 1, 2, 3, 4, 5
