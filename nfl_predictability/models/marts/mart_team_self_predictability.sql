with buckets as (
    select
        season,
        posteam as team,
        down, distance_bucket, score_state, field_zone,
        count(*) as n,
        sum(is_pass) as passes
    from {{ ref('int_play_situations') }}
    group by 1, 2, 3, 4, 5, 6
),

plays as (
    select
        s.season,
        s.posteam as team,
        s.is_pass,
        b.n - 1 as others_n,
        b.passes - s.is_pass as others_pass
    from {{ ref('int_play_situations') }} s
    join buckets b
        on s.season = b.season
        and s.posteam = b.team
        and s.down = b.down
        and s.distance_bucket = b.distance_bucket
        and s.score_state = b.score_state
        and s.field_zone = b.field_zone
),

scored as (
    select
        season,
        team,
        case
            when others_pass * 1.0 / others_n >= 0.5 and is_pass = 1 then 1.0
            when others_pass * 1.0 / others_n < 0.5 and is_pass = 0 then 1.0
            else 0.0
        end as matched
    from plays
    where others_n >= 5
      and others_pass * 1.0 / others_n <> 0.5
),

by_team as (
    select
        season,
        team,
        count(*) as scored_plays,
        avg(matched) as self_predictability
    from scored
    group by 1, 2
)

select
    *,
    rank() over (partition by season order by self_predictability desc) as self_predictability_rank
from by_team
