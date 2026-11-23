with scored as (
    select
        s.season,
        s.posteam as team,
        case when s.is_pass = b.expected_is_pass then 1.0 else 0.0 end as matched
    from {{ ref('int_play_situations') }} s
    join {{ ref('int_situation_baseline') }} b
        using (down, distance_bucket, score_state, field_zone)
    where b.plays >= 200
      and (b.league_pass_rate >= 0.60 or b.league_pass_rate <= 0.40)
),

by_team as (
    select
        season,
        team,
        count(*) as scored_plays,
        avg(matched) as predictability_score
    from scored
    group by 1, 2
)

select
    *,
    rank() over (partition by season order by predictability_score desc) as predictability_rank
from by_team
