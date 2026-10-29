"""Builds the documented 100-query player-search fixture from the stored data.

Players: the 100 active players with the most games since 2018-19. Queries, assigned in rank order:
40 full names typed without accents, 30 full names with one letter dropped from the last name, and
30 last names that belong to exactly one player in the database. Every query names the player it
should find. Usage:

    python scripts/search_queries.py > ../frontend/tests/live/search-queries.json
"""

import json
import sys
import unicodedata

from sqlalchemy import text

from app.db import session_scope

TOP_PLAYERS = """
    SELECT p.id, p.full_name, p.last_name
    FROM players p JOIN player_game_stats s ON s.player_id = p.id
    WHERE p.is_active AND s.minutes > 0
    GROUP BY p.id ORDER BY count(*) DESC, p.id LIMIT 100"""

LAST_NAME_COUNTS = "SELECT lower(last_name), count(*) FROM players GROUP BY 1"


def plain(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def drop_letter(full_name: str, last_name: str | None) -> str:
    """Removes the middle letter of the last name: a realistic one-letter typo."""
    if not last_name or len(last_name) < 5:
        return plain(full_name)
    middle = len(last_name) // 2
    return plain(full_name.replace(last_name, last_name[:middle] + last_name[middle + 1 :]))


def query(player, value: str, kind: str) -> dict:
    return {"query": value, "expected_id": player.id, "expected": player.full_name, "kind": kind}


def main() -> None:
    with session_scope() as session:
        players = session.execute(text(TOP_PLAYERS)).all()
        last_names = dict(session.execute(text(LAST_NAME_COUNTS)).all())
    unique_last = [p for p in players if p.last_name and last_names.get(p.last_name.lower()) == 1]
    unique_last = unique_last[:30]
    others = [p for p in players if p not in unique_last]
    queries = [query(p, plain(p.full_name), "full_name") for p in others[:40]]
    typos = others[40:70]
    queries += [query(p, drop_letter(p.full_name, p.last_name), "typo") for p in typos]
    queries += [query(p, plain(p.last_name), "last_name") for p in unique_last]
    json.dump(queries, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    print(f"{len(queries)} queries", file=sys.stderr)


if __name__ == "__main__":
    main()
