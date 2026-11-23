# NFL play-calling predictability

Does being predictable cost an NFL offense success? Built with SQL, dbt, DuckDB, and Python on [nflverse](https://github.com/nflverse/nflverse-data) play-by-play data, 2020 to 2025, with the Philadelphia Eagles as a case study.

## Questions

1. How predictable was a team, meaning how often could you guess run or pass from the down and distance?
2. How successful was it anyway, measured as EPA (expected points added) per play, and do the two move together?

## Answer

**There is no sign that predictability costs a team success.**

- Across 192 team-seasons (32 teams, 2020 to 2025), predictability explains about 1% of the differences in EPA per play in close games (R-squared 0.01). Every correlation is within noise.
- Across all plays, a small link appears (gain +0.25, lean -0.24), but it goes away once the analysis is limited to close games. It was mostly game script: good teams lead, and teams that lead call plays that fit the situation.
- The Eagles in 2024 were easy to guess from down and distance (67.1% correct against a league average of 64.5%, 5th of 32) and still ranked 4th in EPA per run play (+0.089 on 737 runs).

| Version | Guessability | Gain | Lean | R-squared |
|---|---|---|---|---|
| A. All plays, guesses scored on the plays they came from | +0.03 | +0.25 | -0.24 | 0.06 |
| B. All plays, each guess made from the team's other plays | +0.09 | +0.23 | -0.19 | 0.05 |
| C. Close games only, each guess made from the team's other plays | +0.08 | -0.01 | +0.09 | 0.01 |

Correlations are with EPA per play across team-seasons. With 192 team-seasons, anything within about 0.14 of zero cannot be told apart from noise.

Eagles in close games (first three quarters, score within 7), ranked against all 192 team-seasons:

| Season | Plays | EPA per play | Rank of 192 |
|---|---|---|---|
| 2020 | 517 | -0.104 | 165 |
| 2021 | 543 | +0.055 | 57 |
| 2022 | 673 | +0.179 | 3 |
| 2023 | 596 | +0.055 | 29 |
| 2024 | 758 | +0.091 | 26 |
| 2025 | 603 | +0.050 | 56 |

## Definitions

Plays are runs and passes on downs 1 to 4 in regulation, with a recorded EPA. Each play is placed in a bucket by down and distance (1-3, 4-6, 7-10, 11+ yards).

- **Guessability:** the share of a team's plays you would call correctly by guessing that team's usual run or pass call in the same bucket, using only the team's other plays that season (at least 5 other plays, and buckets split exactly 50/50 are skipped).
- **Lean:** the same, but always guessing the team's most common call overall. It measures how lopsided the run/pass split is.
- **Gain:** guessability minus lean, which is how much the down and distance give away beyond the team's overall tendency.
- **Close games:** first three quarters, score within 7 points.

## What this does not show

- **Call type only.** The analysis sees run or pass, not formation, motion, tempo, who carries the ball, or the previous play. A defense could use all of those, so true guessability is likely higher than measured.
- **Correlation, not cause.** Coaches choose their unusual calls, such as play-action off a run look, so a team doing better on unusual calls does not show that predictability causes worse results.
- **A small effect is not ruled out.** Close games leave about 560 plays per team-season (minimum 381), and the filter drops the fourth quarter.
- **Execution is separate.** Quarterback play, the offensive line, and the skill players explain far more of EPA than predictability does. The Eagles' strong 2022 and 2024 seasons are not explained by anything measured here.

## How the method changed

The first version scored how often a team made the league's usual call, which measures being unusual, not being guessable. A second version scored teams against their own tendencies, but it rewarded run-heavy teams: the 2024 Eagles passed on 44.8% of plays against a league rate of 57.0% and ranked 6th. Adding personnel and formation from nflverse participation data exposed a label change in 2023 (formation labels dropped from 7 to 3, and personnel strings started listing linemen, so personnel groups jumped from about 55 to 65 to 250 to 270). Counting only running backs, tight ends, and wide receivers, and taking shotgun from the play-by-play flag, made seasons comparable. Those models remain in the dbt project; the headline analysis uses the scripts, which measure guessability directly.

## Repo layout

    nfl_predictability/          dbt project (11 models, 14 tests)
      models/staging/            stg_pbp, stg_participation
      models/intermediate/       situation and formation buckets, league baselines
      models/marts/              team scores and a season summary
    scripts/
      guess.py                   2024 guessability by team
      runs.py                    2024 EPA per run play
      league.py                  all 192 team-seasons, version A
      league_close.py            versions B and C

dbt tests check unique and non-null play keys, downs of 1 to 4, play types of run or pass, and non-null scores, teams, and seasons. The season summary has 32 teams in every season.

## How to run

    pip install dbt-duckdb duckdb pandas pyarrow
    mkdir -p data
    for y in 2020 2021 2022 2023 2024 2025; do curl -L -o data/play_by_play_$y.parquet https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_$y.parquet; done
    python scripts/league_close.py

For the dbt models, also download the participation files and build:

    for y in 2020 2021 2022 2023 2024 2025; do curl -L -o data/participation_$y.parquet https://github.com/nflverse/nflverse-data/releases/download/pbp_participation/pbp_participation_$y.parquet; done
    cd nfl_predictability
    dbt build

## Data and license

Play-by-play and participation data come from [nflverse](https://github.com/nflverse/nflverse-data) and are downloaded from its releases page, not stored in this repo. Check nflverse's terms before reusing the data. Code is MIT licensed.
