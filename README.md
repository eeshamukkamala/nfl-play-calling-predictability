# NFL play-calling predictability

How much can a defense learn about run vs. pass from what it sees before the snap, does that differ from team to team, and does it go with offensive success? Built with SQL, dbt, DuckDB, and Python on [nflverse](https://github.com/nflverse/nflverse-data) data for the 2022 to 2025 regular seasons, with the Philadelphia Eagles as a case study.

## What this study does

1. **Measures predictability.** For each team-season, a small model tries to guess run or pass using only information visible before the snap. The share it gets right is the team's *guessability*.
2. **Tests whether it matters.** It compares guessability with offensive success, measured as EPA (expected points added) per play, adjusted for how strong the opposing defenses were.

## What it finds

- **The pre-snap picture reveals a lot.** Always guessing a team's usual call is right about 60% of the time. Adding down, distance, clock, and score raises that to about 67%. Adding formation, personnel, tempo, and the previous plays raises it to about 74%. Motion, backfield count, hash mark, and quarterback position add under a point.
- **Guessability is stable within a season but only modestly across seasons.** A team's score in odd-numbered weeks correlates about +0.70 with its score in even-numbered weeks, but its score in one season correlates only about +0.25 with the next season's, against about +0.4 for lean and +0.44 for opponent-adjusted EPA.
- **There is no strong link between guessability and success.** Correlations with opponent-adjusted EPA per play are below, across 128 team-seasons, with 95% intervals from resampling whole teams (so repeated seasons of the same team are not treated as independent). An interval that includes zero cannot be told apart from no relationship. The data cannot rule out a moderate effect, but it makes a large one unlikely.

| Correlation with opponent-adjusted EPA per play | All plays | Close games |
|---|---|---|
| Guessability | -0.11 [-0.26, +0.05] | +0.12 [-0.03, +0.28] |
| Gain (how much the situation reveals beyond a team's overall run/pass rate) | +0.05 [-0.10, +0.21] | +0.07 [-0.10, +0.25] |
| Lean (how lopsided a team's run/pass split is) | -0.28 [-0.45, -0.10] | +0.19 [-0.00, +0.35] |
| Scramble rate | +0.12 [-0.09, +0.32] | +0.10 [-0.09, +0.29] |

Lean is negative across all plays but turns positive in close games, which is consistent with game score being the cause (teams that are trailing pass a lot, and teams that are leading run), although this study does not establish it. Together, lean and gain explain about 8% of the differences in adjusted EPA across all plays.

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

## Robustness checks

The analysis was rerun under alternative choices (`scripts/league_robust.py`, 128 team-seasons, 2022 to 2025): forward-only validation (train on earlier weeks and test on later ones, starting from week 5), gradient-boosted trees in place of logistic regression, a ridge regression opponent adjustment with separate offense and defense effects for every team, and success rate (share of plays with EPA above zero) as a second measure of offensive success. Intervals resample whole teams.

| Average accuracy | All plays | Close games |
|---|---|---|
| Logistic, odd/even weeks (headline) | 0.738 | 0.710 |
| Logistic, forward-only | 0.735 | 0.706 |
| Trees, odd/even weeks | 0.737 | 0.703 |
| Trees, forward-only | 0.735 | 0.704 |
| Always guess the team's usual call (forward-only) | 0.603 | 0.588 |

Forward-only validation costs about 0.3 to 0.4 points and trees do no better than logistic regression, so neither the retrospective validation nor the linear model appears to understate predictability at this sample size.

**Guessability and offensive success**, across the four prediction variants and three success measures:

| | Plain correlation | Within-team correlation |
|---|---|---|
| All plays | -0.14 to -0.02, every interval includes zero (lowest bound about -0.30) | -0.07 to +0.08, every interval includes zero |
| Close games | +0.05 to +0.21, a few intervals just clear zero | +0.13 to +0.30, 8 of 12 intervals exclude zero |

No variant shows that being more guessable hurts a team. Across all plays the estimates are slightly negative but indistinguishable from zero, and a moderate cost (down to about -0.30) cannot be excluded. In close games every estimate is positive, and the within-team versions, which compare a team with its own usual level, are mostly positive beyond what chance would explain. Lean (how lopsided a team's run/pass split is) reverses sign between samples (-0.20 [-0.37, -0.02] across all plays and +0.20 [+0.02, +0.36] in close games, forward-only, against ridge-adjusted EPA), which is consistent with game score driving the pattern. These are many overlapping comparisons, so borderline intervals should not be read as established findings, and none of this shows cause.

**The Eagles under forward-only validation**, accuracy (league average, rank of 32, 1 = easiest to guess):

| Season | All plays, logistic | All plays, trees | Close games, logistic | Close games, trees |
|---|---|---|---|---|
| 2022 | 0.709 (0.725, 23rd) | 0.719 (0.727, 20th) | 0.712 (0.692, 13th) | 0.688 (0.693, 17th) |
| 2023 | 0.686 (0.729, 29th) | 0.696 (0.725, 27th) | 0.656 (0.704, 30th) | 0.644 (0.697, 30th) |
| 2024 | 0.746 (0.754, 24th) | 0.751 (0.756, 20th) | 0.704 (0.723, 24th) | 0.722 (0.724, 21st) |
| 2025 | 0.703 (0.734, 27th) | 0.697 (0.732, 29th) | 0.664 (0.707, 29th) | 0.673 (0.702, 25th) |

In 2025 the Eagles score 3 to 4 points below the league average in both samples, and 2025 is less guessable than 2024. Their ridge-adjusted EPA per play was +0.084 (3rd), +0.044 (8th), +0.072 (8th), and +0.016 (18th) from 2022 to 2025. Under the ridge adjustment their 2024 schedule ranks easiest of 32 in all plays (2nd in close games) and 2025 ranks 4th (3rd), so raw EPA flatters both years. The ridge penalty reached the top of the grid tried, so schedule effects are heavily shrunk; New England's 2025 schedule ranks easiest of 32 and its adjusted EPA ranks 3rd.

## Known limitations of the method

- **Team-seasons are not independent.** 32 teams appear in up to four seasons each and often keep their quarterback, coach, and system, so the real uncertainty is larger than the plain noise range suggests. The table above uses team-level bootstrap intervals (`scripts/robustness.py`), which are about as wide as the plain noise range. A within-team version, which removes each team's average and each season's average, also shows no sign that being more guessable hurts a team (the one interval that excludes zero, in close games, is positive).
- **Validation.** The headline scores train and test on alternating weeks, so the model can use tendencies from later in the season to predict earlier games. Forward-only validation (train on earlier weeks, test on later ones) lowers average accuracy by about 0.3 to 0.4 points and leaves the conclusions unchanged (see Robustness checks).
- **Model choice.** Logistic regression misses interactions, but gradient-boosted trees scored no higher on average (0.737 vs 0.738 across all plays), so at about 500 to 1,000 plays per team-season the linear model does not appear to understate predictability.
- **The opponent adjustment is simple.** The main adjustment uses season averages of opposing defenses. A ridge regression with offense and defense effects for every team gives nearly the same adjusted EPA (correlation +0.98), but its penalty hit the top of the grid tried, so it shrinks schedule effects heavily.
- **Stability is mostly within a season.** Guessability correlates about +0.25 from one season to the next, so a team's score reflects that season's personnel and system more than a lasting trait.
- **Not compared with prior work.** The study has not been checked against published research on predicting run and pass calls, so its findings may not be new.

## How the method was checked

- **Stability within a season:** odd-vs-even-week correlation of about +0.70, so scores are not mostly noise.
- **Sanity checks:** no team-season scores below a coin flip, and lean matches each team's raw pass rate.
- **Problems found and fixed:** an earlier version skipped tied buckets, which leaked the answer and pushed some teams below chance; formation and personnel labels changed in 2023; scrambles are coded as runs; playoff games were included in early versions; and the motion data starts in 2022, so the study does too.

## Repo layout

    scripts/
      league_final.py         main analysis (guessability, success, schedule adjustment); writes dashboard/team_seasons_final.csv
      league_model.py         formation and personnel version
      league_model_motion.py  adds motion, backfield, hash, and quarterback position
      robustness.py            team-level bootstrap intervals and persistence across seasons
      league_robust.py         forward-only validation, boosted trees, ridge opponent adjustment; writes dashboard/team_seasons_robust.csv
      series_pattern.py       run/pass patterns across a series of downs
      sneaks.py, sneaks_by_week.py, motion_rate.py, schedule_check.py   case-study checks
      old/                    earlier versions, kept for the history above
    nfl_predictability/       dbt project (staging, intermediate, and mart models; 2022-2025 regular seasons)
    dashboard/                data behind the dashboard

The headline numbers come from `scripts/league_final.py`. The robustness checks come from `scripts/league_robust.py` and `scripts/robustness.py`. The dbt project (2022 to 2025 regular seasons) builds the cleaned play tables and two earlier league-norm scores, which measure how unusual a team's calls are compared with the league and not how guessable it is. It has tests on keys, downs, and play types. The headline numbers come from the scripts, not from the dbt marts.

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
