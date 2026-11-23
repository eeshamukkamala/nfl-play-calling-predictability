# NFL play-calling predictability

How much can a defense learn about run vs. pass from what it sees before the snap, does that differ from team to team, and does it go with offensive success? Built with SQL, dbt, DuckDB, and Python on [nflverse](https://github.com/nflverse/nflverse-data) data for the 2022 to 2025 regular seasons, with the Philadelphia Eagles as a case study.

## What this study does

1. **Measures predictability.** For each team-season, a small model tries to guess run or pass using only information visible before the snap. The share it gets right is the team's *guessability*.
2. **Tests whether it matters.** It compares guessability with offensive success, measured as EPA (expected points added) per play, adjusted for how strong the opposing defenses were.

## What it finds

- **The pre-snap picture reveals a lot.** Always guessing a team's usual call is right about 60% of the time. Adding down, distance, clock, and score raises that to about 67%. Adding formation, personnel, tempo, and the previous plays raises it to about 74%. Motion, backfield count, hash mark, and quarterback position add under a point.
- **Guessability is a stable trait.** A team's score in odd-numbered weeks correlates about +0.70 with its score in even-numbered weeks.
- **There is no strong link between guessability and success.** Correlations with opponent-adjusted EPA per play are below, across 128 team-seasons, where anything within about 0.18 of zero cannot be told apart from noise. The data cannot rule out a moderate effect, but it makes a large one unlikely.

| Correlation with opponent-adjusted EPA per play | All plays | Close games |
|---|---|---|
| Guessability | -0.11 | +0.12 |
| Gain (how much the situation reveals beyond a team's overall run/pass rate) | +0.05 | +0.07 |
| Lean (how lopsided a team's run/pass split is) | -0.28 | +0.19 |
| Scramble rate | +0.12 | +0.10 |

Lean is negative across all plays but turns positive in close games, which points to game score as the cause (teams that are trailing pass a lot, and teams that are leading run) and not to the split itself. Together, lean and gain explain about 8% of the differences in adjusted EPA across all plays.

What does drive offensive success is outside the scope of this study. Execution, quarterback play, and the offensive line are obvious candidates to examine separately.

## The Eagles as a case study

Guessability is shown against the league average for that season, with the Eagles' rank of 32 (1 = easiest to guess). Adjusted EPA per play is shown with the rank of 32 (1 = best).

| Season | Guessability, all plays | Guessability, close games | Adjusted EPA, all plays | Adjusted EPA, close games |
|---|---|---|---|---|
| 2022 | 0.718 vs 0.729 (22nd) | 0.694 vs 0.697 (17th) | +0.103 (3rd) | +0.179 (2nd) |
| 2023 | 0.668 vs 0.726 (32nd) | 0.667 vs 0.701 (27th) | +0.072 (8th) | +0.073 (13th) |
| 2024 | 0.743 vs 0.758 (23rd) | 0.699 vs 0.728 (25th) | +0.068 (8th) | +0.054 (10th) |
| 2025 | 0.718 vs 0.740 (25th) | 0.692 vs 0.713 (24th) | +0.001 (18th) | -0.001 (19th) |

- **By this measure the Eagles were not unusually easy to guess.** They scored below the league average in every season and both samples, and 2025 was no more guessable than 2024.
- **The 2025 offense did decline.** Adjusted for opponents, EPA per play fell from +0.068 to +0.001. The 2025 and 2024 schedules were both on the easy side (adjustments of +0.034 and +0.036), so raw EPA flatters both years.
- **They scrambled more than the league.** The Eagles' scramble rate was 7.2%, 7.7%, 7.9%, and 7.6% of dropbacks, against league rates of 4.6%, 5.0%, 5.3%, and 5.5%. The data cannot say whether that reflects pressure, quarterback style, or the line.
- **Quarterback sneaks.** The Eagles led the league in sneaks every season (32, 43, 43, and 28), well above the league average of about 9 to 10. Use fell in 2025, and the conversion rate fell from 76.7% in 2024 to 60.7%, on a small number of attempts. Motion and sneak flags come from FTN charting data.
- **Motion.** The Eagles' share of plays with pre-snap motion rose from 23.0% in 2023 to 44.6% in 2024 and 47.4% in 2025, while the league average rose from 45.3% to 49.3% to 55.1%. Their rank was 32nd, 32nd, 19th, and 27th of 32 across 2022 to 2025 (20.3% in 2022).
- **After a short first-down run** (3 yards or less), the Eagles ran again on second down at or above the league rate in each season, and clearly above it in 2022, 2024, and 2025: 35.8% vs 31.2% in 2022, 33.6% vs 33.3% in 2023, 36.6% vs 32.0% in 2024, and 40.0% vs 32.2% in 2025.

## Definitions

- **Guessability:** for each team-season, regular-season weeks are split into odd and even. A logistic regression is fit on one half and scored on the other, then the halves are swapped. Inputs are down, distance, field position, clock, score, timeouts, formation (pistol, shotgun, or under center), offensive personnel (running backs, tight ends, wide receivers), no-huddle, the previous two plays (run or pass), the previous play's yards, the play's number within the drive, and, for 2022 on, pre-snap motion, backfield count, hash mark, and quarterback position. Defensive alignment, routes, play-action, and anything that happens after the snap are left out on purpose.
- **Run or pass label:** a quarterback scramble is a dropback that turned into a run, so scrambles (flagged by nflverse) are counted as called passes.
- **Lean:** how often always guessing the team's usual call would be right. It measures how lopsided the run/pass split is.
- **Gain:** how much better the full model predicts than that overall rate alone, measured by log loss.
- **Opponent-adjusted EPA:** a team's EPA per play minus the average EPA per play its opponents' defenses allowed to other offenses that season (games against the team itself excluded). The adjustment varies by about 0.02 across teams, against about 0.08 for EPA per play itself. It agrees with a simpler opponent-win-percentage measure only moderately (correlations of -0.20, -0.27, -0.35, and -0.58 by season), so it is noisy for individual teams.
- **Close games:** first three quarters, score within 7 points.

## What this study cannot tell you

- **Whether a defense could read a specific offense.** The model sees run or pass and a limited pre-snap picture. A defender also reads route concepts, who gets the ball, and protection, so a person can legitimately beat this model.
- **Why anything happened.** Correlation only, with 128 team-seasons and a margin of about 0.18.
- **A small or moderate cost of predictability.** It is not ruled out.
- **Execution, quarterback play, and the offensive line.** None is measured.
- **Preseason schedule rankings.** Those use the previous season's records, so they can miss badly, as with the Eagles' 2025 schedule.

## How the method was checked

- **Stability:** odd-vs-even-week correlation of about +0.70, so scores are not mostly noise.
- **Sanity checks:** no team-season scores below a coin flip, and lean matches each team's raw pass rate.
- **Problems found and fixed:** an earlier version skipped tied buckets, which leaked the answer and pushed some teams below chance; formation and personnel labels changed in 2023; scrambles are coded as runs; playoff games were included in early versions; and the motion data starts in 2022, so the study does too.

## Repo layout

    scripts/
      league_final.py         main analysis (guessability, success, schedule adjustment); writes dashboard/team_seasons_final.csv
      league_model.py         formation and personnel version
      league_model_motion.py  adds motion, backfield, hash, and quarterback position
      series_pattern.py       run/pass patterns across a series of downs
      sneaks.py, sneaks_by_week.py, motion_rate.py, schedule_check.py   case-study checks
      old/                    earlier versions, kept for the history above
    nfl_predictability/       dbt project (staging, intermediate, and mart models)
    dashboard/                data behind the dashboard

The headline numbers come from `scripts/league_final.py`. The dbt project builds the same kind of cleaned tables and formation-based scores, with tests on keys, downs, and play types.

## How to run

    pip install dbt-duckdb duckdb pandas pyarrow scikit-learn
    mkdir -p data
    for y in 2022 2023 2024 2025; do
      curl -L -o data/play_by_play_$y.parquet https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_$y.parquet
      curl -L -o data/participation_$y.parquet https://github.com/nflverse/nflverse-data/releases/download/pbp_participation/pbp_participation_$y.parquet
      curl -L -o data/ftn_$y.parquet https://github.com/nflverse/nflverse-data/releases/download/ftn_charting/ftn_charting_$y.parquet
    done
    python scripts/league_final.py

For the dbt models: `cd nfl_predictability && dbt build`.

## Data and license

Play-by-play, participation, and FTN charting data come from [nflverse](https://github.com/nflverse/nflverse-data) and are downloaded from its releases page, not stored in this repo. Check nflverse's and FTN's terms before reusing the data. Code is MIT licensed.
