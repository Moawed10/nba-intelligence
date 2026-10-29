import pytest
from sqlalchemy import text

from app.ml.dataset import load_dataset
from tests.api.conftest import FINAL, STAR

pytestmark = pytest.mark.integration


def test_dataset_loads_final_games_at_the_current_data_version(loaded):
    dataset = load_dataset(loaded)
    with loaded.connect() as conn:
        version = conn.scalar(text("SELECT max(id) FROM ingestion_runs WHERE status = 'succeeded'"))
    assert dataset.data_version == version
    assert len(dataset.frame) == len(FINAL) * 10
    assert dataset.leakage_violations == 0

    star = dataset.frame[dataset.frame["player_id"] == STAR].sort_values("game_date")
    assert star["pts"].tolist() == [26, 11, 11, 11]
    assert star["double_double"].tolist() == [1, 0, 0, 0]
    assert star["is_home"].tolist() == [1.0, 0.0, 1.0, 0.0]
    assert star["pts_avg_3"].iloc[1:].tolist() == pytest.approx([26, 18.5, 16])
    assert not dataset.eligible["player_id"].eq(STAR).any()
