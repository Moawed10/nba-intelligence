import argparse
import json
import platform
import random
import statistics
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import httpx


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(pct / 100 * len(ordered)) - 1))
    return round(ordered[index], 1)


def run(
    name: str, call: Callable[[int], httpx.Response], requests: int, clients: int, ok: set[int]
) -> dict:
    def one(i: int) -> tuple[float, int]:
        started = time.perf_counter()
        try:
            status = call(i).status_code
        except httpx.HTTPError:
            status = 0
        return (time.perf_counter() - started) * 1000, status

    started = time.perf_counter()
    with ThreadPoolExecutor(clients) as pool:
        results = list(pool.map(one, range(requests)))
    elapsed = time.perf_counter() - started
    latencies = [ms for ms, _ in results]
    statuses = Counter(str(status) for _, status in results)
    return {
        "scenario": name,
        "requests": requests,
        "clients": clients,
        "statuses": dict(statuses),
        "unexpected": sum(status not in ok for _, status in results),
        "p50_ms": percentile(latencies, 50),
        "p95_ms": percentile(latencies, 95),
        "p99_ms": percentile(latencies, 99),
        "max_ms": round(max(latencies), 1),
        "mean_ms": round(statistics.fmean(latencies), 1),
        "throughput_rps": round(requests / elapsed, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--clients", type=int, default=20)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--out")
    args = parser.parse_args()
    rng = random.Random(args.seed)

    limits = httpx.Limits(max_connections=args.clients)
    with httpx.Client(base_url=f"{args.base_url}/api/v1", limits=limits, timeout=60) as client:
        release = next(r for r in client.get("/models").json() if r["status"] == "active")
        games = client.get("/games/upcoming", params={"days": args.days}).json()
        teams = {t for g in games for t in (g["home"]["team"]["id"], g["away"]["team"]["id"])}
        roster: dict[int, list[int]] = {}
        for offset in range(0, 600, 100):
            params = {"active": True, "limit": 100, "offset": offset}
            for player in client.get("/players", params=params).json()["items"]:
                team = player.get("team")
                if team and team["id"] in teams:
                    roster.setdefault(team["id"], []).append(player["id"])
        pairs = [
            {"player_id": player, "game_id": game["id"]}
            for game in games
            for team in (game["home"]["team"]["id"], game["away"]["team"]["id"])
            for player in roster.get(team, [])[:6]
        ]
        rng.shuffle(pairs)
        distinct = pairs[:300]
        picks = [rng.choice(distinct) for _ in range(args.requests)]
        ids = [p["player_id"] for p in picks]
        days = [games[i % len(games)]["game_date"] for i in range(args.requests)]
        game_ids = [games[i % len(games)]["id"] for i in range(args.requests)]
        read_ok = {200}
        forecast_ok = {200, 201, 422}
        scenarios = [
            ("read_player_profile", lambda i: client.get(f"/players/{ids[i]}"), read_ok),
            (
                "read_games_by_date",
                lambda i: client.get("/games", params={"date": days[i]}),
                read_ok,
            ),
            ("read_model_summary", lambda i: client.get(f"/models/{release['version']}"), read_ok),
            ("forecast_player", lambda i: client.post("/predictions", json=picks[i]), forecast_ok),
            (
                "forecast_game",
                lambda i: client.post("/predictions/games", json={"game_ids": [game_ids[i]]}),
                read_ok,
            ),
        ]
        results = [run(n, c, args.requests, args.clients, ok) for n, c, ok in scenarios]

    report = {
        "measured_at": datetime.now(UTC).isoformat(),
        "environment": {
            "base_url": args.base_url,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "workload": {
            "release": release["version"],
            "upcoming_games": len(games),
            "distinct_player_games": len(distinct),
            "seed": args.seed,
        },
        "results": results,
    }
    print(json.dumps(report, indent=2))
    if args.out:
        with open(args.out, "w") as f:
            json.dump(report, f, indent=2)


if __name__ == "__main__":
    main()
