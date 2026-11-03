"""Who is likely to guard a player, and how that has gone, from games before the target date.

The real defender is unknown until the game is played, so nothing here reads the target game. The
sweep below processes targets in date order and only then adds that date's matchups to its state, so
a target can only ever see earlier days. Definitions: docs/model-methodology.md#defender-matchups.
"""

import numpy as np
import pandas as pd

MATCHUP_FEATURES: tuple[str, ...] = (
    "matchup_possessions",
    "likely_defender_share",
    "pts_per100_edge_vs_likely",
    "ast_per100_edge_vs_likely",
    "fg3m_per100_edge_vs_likely",
    "likely_defender_pts_allowed_per100",
    "opp_pts_allowed_to_position_per100",
)

MATCHUP_LABELS: dict[str, str] = {
    "matchup_possessions": "Possessions against these likely defenders",
    "likely_defender_share": "Share of past matchups with the most likely defender",
    "pts_per100_edge_vs_likely": "Points against likely defenders, compared with usual",
    "ast_per100_edge_vs_likely": "Assists against likely defenders, compared with usual",
    "fg3m_per100_edge_vs_likely": "3-pointers against likely defenders, compared with usual",
    "likely_defender_pts_allowed_per100": "Points likely defenders usually allow",
    "opp_pts_allowed_to_position_per100": "Points this team allows to this position, last 10 games",
}

SOURCE_DATES = ("matchup_source_date", "position_source_date")

# Older meetings count half as much per year; a defender not seen for this long has left the league
# or the rotation. Rates cover the last year and are pulled toward a prior until there is enough
# sample: possessions at which the player's own rate and the prior weigh the same.
HALF_LIFE_DAYS = 365.0
ROSTER_DAYS = 400
RATE_DAYS = 365
OWN_RATE_PRIOR_POSSESSIONS = 50.0
DEFENDER_PRIOR_POSSESSIONS = 200.0
# Points one offensive player scores per 100 possessions he is on the floor: the league-wide figure
# from stored matchups, fixed so that training and serving (which read a subset) agree.
LEAGUE_PTS_PER_100 = 23.0
POSITION_GAMES = 10
POSITIONS = ("G", "F", "C")
EMPTY_COLUMNS = (*MATCHUP_FEATURES, *SOURCE_DATES)


def _position(value: object) -> str:
    text = str(value or "")[:1].upper()
    return text if text in POSITIONS else "all"


def _position_rates(m: pd.DataFrame) -> pd.DataFrame:
    """Each defending team's points allowed per 100 by position, over its last N games, including
    that game; joined to later games only."""
    rows = m.assign(position=m["off_position"].map(_position))
    by_game = ["def_team_id", "game_date", "game_id"]
    total = rows.groupby(by_game, sort=True)[["pts", "poss"]].sum()
    frames = {"all": total}
    for position in POSITIONS:
        part = rows[rows["position"] == position].groupby(by_game)[["pts", "poss"]].sum()
        frames[position] = part.reindex(total.index, fill_value=0.0)
    out = pd.DataFrame(index=total.index)
    for name, part in frames.items():
        rolled = part.groupby(level="def_team_id", sort=False).rolling(
            POSITION_GAMES, min_periods=1
        ).sum().droplevel(0)  # fmt: skip
        out[name] = rolled["pts"] / rolled["poss"].where(rolled["poss"] > 0) * 100
    return (
        out.reset_index()
        .drop(columns="game_id")
        .rename(columns={"game_date": "position_source_date"})
        .sort_values("position_source_date", kind="mergesort")
    )


def _add_position_feature(
    out: pd.DataFrame, targets: pd.DataFrame, m: pd.DataFrame, positions: np.ndarray
) -> None:
    left = pd.DataFrame(
        {
            "game_date": pd.to_datetime(targets["game_date"]).to_numpy(),
            "opponent_id": targets["opponent_id"].to_numpy(),
            "_row": np.arange(len(targets)),
        }
    ).sort_values("game_date", kind="mergesort")
    joined = pd.merge_asof(
        left,
        _position_rates(m),
        left_on="game_date",
        right_on="position_source_date",
        left_by="opponent_id",
        right_by="def_team_id",
        allow_exact_matches=False,
    ).sort_values("_row")
    values = joined[["all", *POSITIONS]].to_numpy(float)
    columns = {name: i for i, name in enumerate(("all", *POSITIONS))}
    chosen = values[np.arange(len(values)), [columns[p] for p in positions]]
    out["opp_pts_allowed_to_position_per100"] = np.where(np.isnan(chosen), values[:, 0], chosen)
    out["position_source_date"] = joined["position_source_date"].to_numpy()


def defender_features(targets: pd.DataFrame, matchups: pd.DataFrame | None) -> pd.DataFrame:
    """One row per target, in its order, from matchups played on earlier dates only."""
    out = pd.DataFrame(np.nan, index=range(len(targets)), columns=list(MATCHUP_FEATURES))
    out["matchup_source_date"] = pd.NaT
    out["position_source_date"] = pd.NaT
    if matchups is None or targets.empty:
        return out
    if matchups.empty:
        out["matchup_possessions"] = 0.0
        return out

    m = matchups.assign(game_date=pd.to_datetime(matchups["game_date"])).sort_values(
        ["game_date", "game_id"], kind="mergesort"
    )
    epoch = m["game_date"].min()
    day = (m["game_date"] - epoch).dt.days.to_numpy()
    players, player_ids = pd.factorize(
        np.concatenate([m["off_player_id"], m["def_player_id"], targets["player_id"]])
    )
    n_rows = len(m)
    off, deff = players[:n_rows], players[n_rows : 2 * n_rows]
    target_player = players[2 * n_rows :]
    def_team = m["def_team_id"].to_numpy()
    poss = m["poss"].to_numpy(float)
    stats = {s: m[s].to_numpy(float) for s in ("pts", "ast", "fg3m")}
    position_of = dict(zip(m["off_player_id"], m["off_position"], strict=False))

    size = len(player_ids)
    team_now = np.full(size, -1, dtype=np.int64)
    last_seen = np.full(size, -(10**7), dtype=np.int64)
    allowed_pts, allowed_poss = np.zeros(size), np.zeros(size)
    own = {s: np.zeros(size) for s in stats}
    own_poss = np.zeros(size)

    by_player: dict[int, np.ndarray] = {}
    order = np.argsort(off, kind="mergesort")
    cuts = np.flatnonzero(np.diff(off[order])) + 1
    for rows in np.split(order, cuts):
        by_player[int(off[rows[0]])] = rows

    target_day = (pd.to_datetime(targets["game_date"]) - epoch).dt.days.to_numpy()
    opponent = targets["opponent_id"].to_numpy()
    positions = np.full(len(targets), "all", dtype=object)
    results = np.full((len(targets), 6), np.nan)
    sources = np.full(len(targets), np.nan)
    added = expired = 0

    def apply(rows: slice, sign: int) -> None:
        np.add.at(allowed_pts, deff[rows], sign * stats["pts"][rows])
        np.add.at(allowed_poss, deff[rows], sign * poss[rows])
        np.add.at(own_poss, off[rows], sign * poss[rows])
        for s, values in stats.items():
            np.add.at(own[s], off[rows], sign * values[rows])

    for i in np.argsort(target_day, kind="mergesort"):
        d = target_day[i]
        end = int(np.searchsorted(day, d, side="left"))
        if end > added:
            rows = slice(added, end)
            team_now[deff[rows]] = def_team[rows]
            last_seen[deff[rows]] = day[rows]
            apply(rows, 1)
            added = end
        stop = int(np.searchsorted(day, d - RATE_DAYS, side="left"))
        if stop > expired:
            apply(slice(expired, stop), -1)
            expired = stop

        p = target_player[i]
        rows = by_player.get(int(p))
        results[i, 0] = 0.0
        if rows is None:
            continue
        rows = rows[: int(np.searchsorted(day[rows], d, side="left"))]
        if rows.size == 0:
            continue
        positions[i] = _position(position_of.get(player_ids[p]))
        defenders = deff[rows]
        here = (team_now[defenders] == opponent[i]) & (last_seen[defenders] >= d - ROSTER_DAYS)
        if not here.any():
            continue
        rows, defenders = rows[here], defenders[here]
        decay = 0.5 ** ((d - day[rows]) / HALF_LIFE_DAYS)
        weight = poss[rows] * decay
        total = weight.sum()
        unique, inverse = np.unique(defenders, return_inverse=True)
        share = np.bincount(inverse, weight) / total
        allowed = (allowed_pts[unique] + DEFENDER_PRIOR_POSSESSIONS * LEAGUE_PTS_PER_100 / 100) / (
            allowed_poss[unique] + DEFENDER_PRIOR_POSSESSIONS
        )
        results[i, 0] = poss[rows].sum()
        results[i, 1] = share.max()
        results[i, 5] = float(share @ allowed) * 100
        sources[i] = day[rows].max()
        if own_poss[p] > 0:
            for k, s in enumerate(("pts", "ast", "fg3m")):
                usual = own[s][p] / own_poss[p]
                seen = (decay @ stats[s][rows] + OWN_RATE_PRIOR_POSSESSIONS * usual) / (
                    total + OWN_RATE_PRIOR_POSSESSIONS
                )
                results[i, 2 + k] = (seen - usual) * 100

    for k, name in enumerate(MATCHUP_FEATURES[:6]):
        out[name] = results[:, k]
    seen_days = pd.to_timedelta(sources, unit="D")
    out["matchup_source_date"] = pd.Series(epoch + seen_days, index=out.index)
    _add_position_feature(out, targets, m, positions)
    unseen = out["likely_defender_pts_allowed_per100"].isna()
    out.loc[unseen, "likely_defender_pts_allowed_per100"] = out.loc[
        unseen, "opp_pts_allowed_to_position_per100"
    ]
    return out
