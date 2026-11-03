# Model Methodology

How NBA Intelligence builds features, trains and selects models, quantifies uncertainty and serves predictions. All results reported anywhere in the project come from running this pipeline; none are estimated. Implemented in `backend/app/ml/` (Phase 6); results are in [test-report.md](test-report.md#phase-6-machine-learning-pipeline).

## Prediction task

For player *p* and scheduled game *g*, predict *p*'s box score in *g* using only information available before *g*'s tip-off.

| Target | Type | Model output |
|---|---|---|
| `pts`, `reb`, `ast`, `fg3m`, `stl`, `blk`, `min` | Regression | Point estimate + 80% interval |
| `double_double` | Binary (≥ 10 in two of pts, reb, ast, stl, blk) | Calibrated probability |

Predictions are **conditional on the player playing**. nba_api has no injury or lineup feed, so a scratched player is a missing outcome, not a zero.

## Training data

- Source: `player_game_stats` joined to `games` and `team_game_stats`. Regular season, play-in and playoffs, 2018-19 onward.
- One row per player-game where the player recorded minutes > 0.
- Rows are eligible as training targets only if the player has at least **5 prior games in the current or previous season**. The same threshold drives the `insufficient_data` response at inference.

## Features

All features for game *g* are computed from games with `game_date < g.game_date`. Implementation: `backend/app/ml/features.py`, used unchanged by training and inference.

**How leakage is prevented in code:** each history (player form, own team, opponent, player-vs-opponent) is computed per game *including* that game, then joined to the target row with `merge_asof(..., allow_exact_matches=False)`, i.e. the latest row strictly before the target date. Every feature row carries the source date of each joined history; the training run counts rows whose source date is on or after the target date and refuses to train if any exist. Rolling windows use up to *n* previous games (fewer when fewer exist) across season boundaries; `season_games` and the 5-prior-game eligibility rule guard thin histories. 60 features in total.

| Group | Features | Leakage control |
|---|---|---|
| Recent form | Mean of each target and of `fga`, `fg3a`, `fta`, `min` over the last 3, 5, 10 games | `groupby(player).shift(1)` before `rolling` |
| Season to date | Expanding mean of each target within the season; games played | Shifted expanding mean; first game of the season falls back to the previous season's mean with a `season_games` count |
| Trend | Last-5 mean minus last-10 mean for `min`, `fga`, `pts` | Built from shifted windows |
| Variability | Std of `pts`, `min` over the last 10 | Shifted |
| Usage proxy | `(FGA + 0.44·FTA + TOV)` share of team total, last 10 | From the player's own prior games |
| Context | `is_home`, `rest_days` (capped at 7), `is_back_to_back`, `team_rest_days` | From schedule dates before *g* |
| Opponent | Opponent defensive rating (points allowed per 100 possessions), last 10 games and season to date; opponent pace | Team game logs before *g* only; season-snapshot endpoints are never used |
| Team | Own team pace, last 10 | Same |
| History vs. opponent | Player's mean of each target vs. this opponent over prior meetings, shrunk toward the season mean by `n / (n + 3)`; meeting count | Prior meetings only |

`feature_schema_version` is a hash of the ordered feature names, dtypes and the feature module version constant. An artifact refuses to load if its schema version does not match the running code.

### Leakage tests (Phase 6 gates)

- Fixture-based: for a hand-built 12-game sequence, every rolling feature at game *k* equals the independently computed mean of games *k−n…k−1*.
- Perturbation: changing any stat in game *k* or later leaves every feature for game *k* unchanged.
- Split boundary: max(train `game_date`) < min(validation `game_date`) < min(test `game_date`).
- Opponent features for a date never reference a team game on or after that date.

## Chronological splits

| Split | Seasons | Use |
|---|---|---|
| Train | 2018-19 – 2023-24 | Fit |
| Validation | 2024-25 | Model selection, hyperparameter search, conformal calibration, probability calibration |
| Test | 2025-26 | Reported once per release; never used for any choice |
| Live | 2026-27 | Real pregame predictions, scored after each game |

After the test evaluation, the selected configuration (same hyperparameters; XGBoost with its early-stopped round count) is refit on train + validation as the production model, and its conformal intervals and probability calibration are fitted on the test season, the most recent completed season. The reported test metrics belong to the held-out fit. The registry stores both: held-out model versions carry the validation and test evaluations, and the production version per target is the one marked `is_selected`. Live accuracy of the production models is measured on 2026-27 games after they finish (Phase 7).

## Defender matchups

Who actually guards a player is only published after a game, so a forecast can never use the real matchup. Implementation: `backend/app/ml/matchups.py`, from `player_matchups`. The sweep handles each date's targets before adding that date's matchups, so a target sees earlier days only; `matchup_source_date` and `position_source_date` are in the leakage check.

**Likely defenders** are the opponents' players who have guarded this player before and whose most recent defensive game (within 400 days) was for this opponent. Past meetings count by possessions, halving in weight per year. Injuries and tonight's rotation are not known, so a likely defender may not play.

| Feature | Meaning |
|---|---|
| `matchup_possessions` | Possessions against these defenders (0 when never met) |
| `likely_defender_share` | Share of those possessions with the most frequent defender |
| `pts_per100_edge_vs_likely`, `ast_…`, `fg3m_…` | Player's rate against them minus his rate over the last year, pulled toward zero until about 50 possessions |
| `likely_defender_pts_allowed_per100` | What those defenders allowed to everyone over the last year, pulled toward the league's 23 until about 200 possessions; the position rate when there is no history |
| `opp_pts_allowed_to_position_per100` | What the opponent allowed to this player's position (G, F, C) over its last 10 tracked games |

Rates are "points by one offensive player per 100 possessions he is on the floor", about 23 league-wide. A release serves on the feature list stored with its artifacts, so these features change nothing until a release trained on them is activated.

## Models compared

Every target is trained with each family on identical rows:

1. **Rolling baseline:** mean of the target over the player's previous 10 games (all previous games when fewer than 10). No fitting.
2. **Ridge regression:** standardized features, `alpha` chosen on validation.
3. **Random forest:** 150 trees, `max_features=0.33`, `max_samples=0.5`; `max_depth` and `min_samples_leaf` from a 3-point grid chosen on validation.
4. **XGBoost:** `tree_method=hist`, early stopping (100 rounds) on validation; 8 random-search trials over `max_depth` 3–8, `learning_rate` 0.02–0.1, `subsample` 0.6–1, `colsample_bytree` 0.5–1, `min_child_weight` 1–50 (fixed seed).

**Selection:** lowest validation MAE per target. The most complex model is not assumed to win. If the baseline wins a target, the baseline is shipped for that target and the analytics page says so.

**Metrics:** MAE, RMSE and R² on the test season, reported per target, per algorithm and per season slice, always next to the baseline computed on the same observations. A ≥ 5% MAE reduction over the baseline is a research objective, not a gate. Whatever the result, it is reported as measured.

## Uncertainty intervals

**Method:** split conformal prediction with Mondrian bins.

1. On the validation season, compute absolute residuals `|y − ŷ|` of the selected model.
2. Bin observations by predicted minutes (tertiles), since variance grows with playing time.
3. Per bin, take the conformal quantile `q = ⌈(n+1)(1−α)⌉ / n` of the residuals, with α = 0.20.
4. Interval = `[max(0, ŷ − q), ŷ + q]`. Counts are clipped at zero.

**Verification:** empirical coverage on the test season, per target and per bin. The gate is 80% ± 5 pp.

**Limitations, shown on the About and Model Analytics pages:**

- Coverage holds on average over games similar to the calibration season. It is not a guarantee for any single game.
- Intervals are symmetric. Real box-score distributions are right-skewed (a 40-point game is likelier than a −10), so the lower bound is often conservative. Quantile regression (XGBoost `reg:quantileerror`) is the planned comparison if test coverage is uneven.
- Exchangeability is violated by role changes, trades and injuries. Coverage is reported per season so drift is visible.

## Double-double probability

A direct classifier (logistic regression and XGBoost compared on raw validation log loss) on the same features. Class weights are not used: the goal is a calibrated probability, and reweighting would only distort it before calibration. Probabilities are calibrated with isotonic regression fitted on the validation season (`CalibratedClassifierCV` over the frozen model). The production probability comes from this classifier, not from multiplying independent regression outputs.

**Reported:** Brier score, log loss, and a reliability curve (10 bins) on the test season, alongside the base-rate Brier score as the baseline. As a cross-check, a Monte Carlo estimate built from the regression residuals is reported but not served.

## Explanations

- Tree models: SHAP `TreeExplainer` values per target. Ridge: coefficient × standardized value.
- The API returns the top 5 contributions per target, each with a plain-language label ("Points, last 5 games"), the feature value and its signed effect in stat units.
- The UI describes these as "factors that moved this prediction", not as causes.

## Inference

- Runs in the FastAPI process from artifacts loaded at startup. The SHA-256 of each artifact is verified against `model_versions.artifact_sha256`. No training code is imported by the API.
- The active release comes from `model_releases.status = 'active'`, never from file names or modification times.
- The feature snapshot is stored with the prediction. Re-running the same artifact on the same snapshot must reproduce the stored values within `1e-9` (a Phase 7 test).

## Post-game evaluation

A scheduled job finds pregame predictions whose games are final, writes `prediction_evaluations` (actual, absolute error, within-interval flag; Brier term for double-double), and leaves the original prediction untouched. Live accuracy is reported separately from backtests.

## Reproducibility

- Fixed seeds (`random_state`, XGBoost `seed`).
- The training run records `data_version`, git SHA, library versions, split dates and hyperparameters in the release.
- Retraining with the same `data_version` and seed must reproduce test MAE within 1e-6 for deterministic models and 1e-3 for XGBoost with `tree_method="hist"` (a Phase 6 test).
