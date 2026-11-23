{{ config(materialized='table') }}

with pass_rates as (
    select
        season,
        posteam as team,
        count(*) as plays,
        avg(is_pass) as pass_rate
    from {{ ref('int_play_situations') }}
    group by 1, 2
)

select
    p.season,
    p.team,
    p.plays,
    round(p.pass_rate, 3) as pass_rate,
    round(lg.predictability_score, 3) as league_norm_score,
    lg.predictability_rank as league_norm_rank,
    round(sf.self_predictability, 3) as self_score,
    sf.self_predictability_rank as self_rank,
    round(e.epa_expected, 3) as epa_when_expected,
    round(e.epa_unexpected, 3) as epa_when_unexpected,
    round(e.epa_gap, 3) as epa_gap
from pass_rates p
join {{ ref('mart_team_predictability') }} lg
    on p.season = lg.season and p.team = lg.team
join {{ ref('mart_team_self_predictability') }} sf
    on p.season = sf.season and p.team = sf.team
join {{ ref('mart_predictability_epa') }} e
    on p.season = e.season and p.team = e.team
