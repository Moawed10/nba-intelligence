"""Database integrity and reconciliation checks backing the Phase 3 quality gates."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

CHECKS: dict[str, str] = {
    "orphan_player_lines": """
        SELECT count(*) FROM player_game_stats s
        LEFT JOIN games g ON g.id = s.game_id LEFT JOIN players p ON p.id = s.player_id
        WHERE g.id IS NULL OR p.id IS NULL""",
    "orphan_team_lines": """
        SELECT count(*) FROM team_game_stats s
        LEFT JOIN games g ON g.id = s.game_id LEFT JOIN teams t ON t.id = s.team_id
        WHERE g.id IS NULL OR t.id IS NULL""",
    "final_games_without_two_team_lines": """
        SELECT count(*) FROM games g
        WHERE g.status = 'final' AND g.home_score IS NOT NULL
          AND (SELECT count(*) FROM team_game_stats t WHERE t.game_id = g.id) <> 2""",
    "score_mismatch_vs_team_lines": """
        SELECT count(*) FROM games g
        JOIN team_game_stats h ON h.game_id = g.id AND h.team_id = g.home_team_id
        JOIN team_game_stats a ON a.game_id = g.id AND a.team_id = g.away_team_id
        WHERE g.home_score <> h.pts OR g.away_score <> a.pts""",
    "player_points_mismatch_vs_team": """
        SELECT count(*) FROM (
          SELECT t.game_id, t.team_id, t.pts, sum(p.pts) AS player_pts
          FROM team_game_stats t
          JOIN player_game_stats p ON p.game_id = t.game_id AND p.team_id = t.team_id
          GROUP BY t.game_id, t.team_id, t.pts) x
        WHERE x.pts <> x.player_pts""",
    "duplicate_player_lines": """
        SELECT count(*) FROM (SELECT game_id, player_id FROM player_game_stats
                              GROUP BY 1, 2 HAVING count(*) > 1) d""",
}

COVERAGE = """
    SELECT g.season_id, s.label, g.season_type::text AS season_type,
           count(*) FILTER (WHERE g.status = 'final' AND g.home_score IS NOT NULL) AS final_games,
           count(*) FILTER (WHERE g.status <> 'final') AS not_final_games,
           (SELECT count(*) FROM player_game_stats p JOIN games g2 ON g2.id = p.game_id
             WHERE g2.season_id = g.season_id AND g2.season_type = g.season_type) AS player_lines,
           count(*) FILTER (
             WHERE g.status = 'final' AND g.home_score IS NOT NULL
               AND (SELECT count(DISTINCT p.team_id) FROM player_game_stats p
                    WHERE p.game_id = g.id) = 2) AS final_games_with_both_teams
    FROM games g JOIN seasons s ON s.id = g.season_id
    GROUP BY g.season_id, s.label, g.season_type ORDER BY g.season_id, g.season_type"""

RUNS = """
    SELECT job, params, status::text, rows_fetched, rows_valid, rows_inserted, rows_updated,
           rows_rejected, retry_count, finished_at
    FROM ingestion_runs ORDER BY id DESC LIMIT :limit"""


def integrity_report(session: Session) -> dict[str, Any]:
    checks = {name: session.scalar(text(sql)) for name, sql in CHECKS.items()}
    coverage = [dict(r) for r in session.execute(text(COVERAGE)).mappings()]
    for row in coverage:
        row["completeness"] = (
            round(row["final_games_with_both_teams"] / row["final_games"], 4)
            if row["final_games"]
            else None
        )
    return {"checks": checks, "coverage": coverage}


def recent_runs(session: Session, limit: int = 20) -> list[dict[str, Any]]:
    return [dict(r) for r in session.execute(text(RUNS), {"limit": limit}).mappings()]
