with totals as (
    select season, team, count(*) as total_plays
    from {{ ref('int_play_formations') }}
    group by 1, 2
),

scored as (
    select
        f.season,
        f.team,
        case
            when f.is_pass = (case when b.league_pass_rate >= 0.5 then 1 else 0 end)
            then 1.0 else 0.0
        end as matched
    from {{ ref('int_play_formations') }} f
    join {{ ref('int_formation_baseline') }} b
        using (down, distance_bucket, score_state, personnel_group, formation_group)
    where b.plays >= 75
      and (b.league_pass_rate >= 0.60 or b.league_pass_rate <= 0.40)
),

by_team as (
    select season, team, count(*) as scored_plays, avg(matched) as read_score
    from scored
    group by 1, 2
)

select
    t.season,
    t.team,
    t.total_plays,
    b.scored_plays,
    round(b.scored_plays * 1.0 / t.total_plays, 3) as share_scored,
    round(b.read_score, 3) as read_score,
    rank() over (partition by t.season order by b.read_score desc) as read_rank
from totals t
join by_team b on t.season = b.season and t.team = b.team
