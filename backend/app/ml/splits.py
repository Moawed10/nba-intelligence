"""Chronological season splits (docs/model-methodology.md#chronological-splits)."""

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class SplitPlan:
    train: tuple[int, ...]
    validation: int
    test: int

    def describe(self) -> dict[str, list[int] | int]:
        return {"train": list(self.train), "validation": self.validation, "test": self.test}


DEFAULT_PLAN = SplitPlan(train=(2018, 2019, 2020, 2021, 2022, 2023), validation=2024, test=2025)


@dataclass(frozen=True)
class Splits:
    train: pd.DataFrame
    validation: pd.DataFrame
    test: pd.DataFrame

    def date_range(self, part: str) -> tuple[pd.Timestamp, pd.Timestamp]:
        frame = getattr(self, part)
        return frame["game_date"].min(), frame["game_date"].max()

    @property
    def chronological(self) -> bool:
        """Every training game precedes every validation game, which precedes every test game."""
        return (
            self.train["game_date"].max() < self.validation["game_date"].min()
            and self.validation["game_date"].max() < self.test["game_date"].min()
        )


def split(frame: pd.DataFrame, plan: SplitPlan = DEFAULT_PLAN) -> Splits:
    eligible = frame[frame["eligible"]]
    parts = Splits(
        train=eligible[eligible["season_id"].isin(plan.train)],
        validation=eligible[eligible["season_id"] == plan.validation],
        test=eligible[eligible["season_id"] == plan.test],
    )
    if not parts.chronological:
        raise ValueError("Splits overlap in time")
    return parts
