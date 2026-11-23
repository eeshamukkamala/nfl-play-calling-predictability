select
    s.play_key,
    s.season,
    s.posteam as team,
    s.down,
    s.distance_bucket,
    s.score_state,
    s.is_pass,
    s.epa,
    p.n_rb || 'RB-' || p.n_te || 'TE-' || p.n_wr || 'WR' as personnel_group
from {{ ref('int_play_situations') }} s
join {{ ref('stg_pbp') }} b on s.play_key = b.play_key
join {{ ref('stg_participation') }} p
    on b.game_id = p.game_id and b.play_id = p.play_id
where p.n_rb + p.n_te + p.n_wr between 4 and 6
