"""Latency benchmark for the read API (Phase 4 performance gates).

Workload per scenario: REQUESTS requests from CLIENTS concurrent clients against a running server.
Players are drawn from the active directory so profile and game-log requests mix cache misses (first
request per player) with hits. Usage:

    python scripts/benchmark.py --base-url http://127.0.0.1:8000 --out benchmark.json
"""

import argparse
import json
import random
import statistics
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import httpx

SEARCH_TERMS = [
    "le", "jam", "cur", "step", "jok", "don", "gian", "tat", "emb", "dur", "kev", "luk",
    "ant", "edw", "bro", "wil", "joh", "smi", "gre", "dav", "mit", "har", "mor", "tho",
    "lebrn", "jokic", "doncic", "wemban", "gilgeous", "brunson",
]  # fmt: skip


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(pct / 100 * len(ordered)) - 1))
    return round(ordered[index], 1)


def run(
    client: httpx.Client, name: str, paths: Callable[[int], str], requests: int, clients: int
) -> dict:
    def one(i: int) -> tuple[float, int]:
        started = time.perf_counter()
        status = client.get(paths(i)).status_code
        return (time.perf_counter() - started) * 1000, status

    started = time.perf_counter()
    with ThreadPoolExecutor(clients) as pool:
        results = list(pool.map(one, range(requests)))
    elapsed = time.perf_counter() - started
    latencies = [ms for ms, _ in results]
    return {
        "scenario": name,
        "requests": requests,
        "clients": clients,
        "errors": sum(status != 200 for _, status in results),
        "p50_ms": percentile(latencies, 50),
        "p95_ms": percentile(latencies, 95),
        "p99_ms": percentile(latencies, 99),
        "mean_ms": round(statistics.fmean(latencies), 1),
        "throughput_rps": round(requests / elapsed, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--clients", type=int, default=20)
    parser.add_argument("--players", type=int, default=200)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out")
    args = parser.parse_args()
    rng = random.Random(args.seed)

    limits = httpx.Limits(max_connections=args.clients)
    with httpx.Client(base_url=f"{args.base_url}/api/v1", limits=limits, timeout=30) as client:
        ids: list[int] = []
        for offset in range(0, args.players, 100):
            page = client.get("/players", params={"active": True, "limit": 100, "offset": offset})
            ids += [p["id"] for p in page.json()["items"]]
        rng.shuffle(ids)
        ids = ids[: args.players]
        terms = [rng.choice(SEARCH_TERMS) for _ in range(args.requests)]
        picks = [rng.choice(ids) for _ in range(args.requests)]
        scenarios = [
            ("player_search", lambda i: f"/players/search?q={terms[i]}&limit=10"),
            ("player_profile", lambda i: f"/players/{picks[i]}"),
            ("player_game_log", lambda i: f"/players/{picks[i]}/games?limit=25"),
        ]
        results = [run(client, n, p, args.requests, args.clients) for n, p in scenarios]

    report = {
        "measured_at": datetime.now(UTC).isoformat(),
        "base_url": args.base_url,
        "distinct_players": len(ids),
        "results": results,
    }
    print(json.dumps(report, indent=2))
    if args.out:
        with open(args.out, "w") as f:
            json.dump(report, f, indent=2)


if __name__ == "__main__":
    main()
