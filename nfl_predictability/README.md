# dbt models

This folder holds the dbt project for the NFL play-calling predictability analysis. It reads the nflverse play-by-play and participation files from `../data/` and builds descriptive baselines in DuckDB. The guessability models and the tests described in the main README (odd/even weeks, forward-only, gradient-boosted trees) live in `../scripts/`, not here.

## Models

| Layer | Model | What it does |
|---|---|---|
| Staging | `stg_pbp` | Run and pass plays, 2022-2025 |
| Staging | `stg_participation` | Formation and personnel for each play |
| Intermediate | `int_play_situations` | Labels each play by down, distance and score state |
| Intermediate | `int_situation_baseline` | The league-typical call for each situation |
| Intermediate | `int_play_formations` | Adds formation and personnel to each play |
| Intermediate | `int_formation_baseline` | The league-typical call for each pre-snap look |
| Marts | `mart_team_predictability` | Share of plays where a team made the league-usual call for its down and distance |
| Marts | `mart_team_read_predictability` | Share of plays where a team's call matched the league-typical call for its pre-snap look |

`dbt build` runs all 8 models and 11 tests (unique and not-null keys, accepted values for down and play type, and not-null checks on the marts).

## How to run

Download the data into `data/` at the top of the repo (see the main README), then:

```bash
pip install dbt-duckdb duckdb pyarrow
cd nfl_predictability
dbt build
```

Run `dbt` from inside this folder: the connection settings are in `profiles.yml` here, and the models read data from `../data/`.