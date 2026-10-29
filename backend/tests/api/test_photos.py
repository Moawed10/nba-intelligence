import pytest

from app.services.photos import PNG_SIGNATURE, SENTINEL_ID, PhotoCache, PhotoSourceError
from tests.api.conftest import NO_SHOTS, RETIRED, STAR

pytestmark = pytest.mark.integration

SILHOUETTE = PNG_SIGNATURE + b"silhouette"
PHOTOS = {STAR: PNG_SIGNATURE + b"star", RETIRED: PNG_SIGNATURE + b"retired"}


class FakeServer:
    def __init__(self) -> None:
        self.calls: list[int] = []
        self.down = False

    def __call__(self, url: str) -> bytes:
        player = int(url.rsplit("/", 1)[1].removesuffix(".png"))
        if "1040x760" in url and player in PHOTOS:
            return PHOTOS[player] + b"large"
        self.calls.append(player)
        if self.down:
            raise PhotoSourceError("timed out")
        if player == SENTINEL_ID:
            return SILHOUETTE
        return PHOTOS.get(player, SILHOUETTE)


@pytest.fixture
def server(client, tmp_path) -> FakeServer:
    fake = FakeServer()
    client.app.state.api.photos = PhotoCache(tmp_path, fetch=fake)
    return fake


def test_photo_is_fetched_once_and_served_from_disk(client, server):
    for _ in range(3):
        response = client.get(f"/api/v1/players/{STAR}/photo")
        assert response.status_code == 200
        assert response.content == PHOTOS[STAR]
    assert response.headers["content-type"] == "image/png"
    assert "max-age" in response.headers["cache-control"]
    assert server.calls.count(STAR) == 1


def test_former_players_have_photos_too(client, server):
    assert client.get(f"/api/v1/players/{RETIRED}/photo").content == PHOTOS[RETIRED]


def test_silhouette_means_no_photo_and_is_remembered(client, server):
    for _ in range(2):
        response = client.get(f"/api/v1/players/{NO_SHOTS}/photo")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "photo_not_found"
    assert server.calls.count(NO_SHOTS) == 1


def test_unknown_player_is_not_fetched(client, server):
    assert client.get("/api/v1/players/123456/photo").json()["error"]["code"] == "player_not_found"
    assert 123456 not in server.calls


def test_source_failure_is_a_503_and_not_remembered(client, server):
    server.down = True
    response = client.get(f"/api/v1/players/{STAR}/photo")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "photo_unavailable"
    server.down = False
    assert client.get(f"/api/v1/players/{STAR}/photo").status_code == 200


def test_non_png_responses_are_refused(tmp_path):
    cache = PhotoCache(tmp_path, fetch=lambda url: b"<html>error</html>")
    with pytest.raises(PhotoSourceError):
        cache.path(STAR)
    assert not list(tmp_path.glob("*.png"))


def test_large_photos_are_cached_separately(client, server):
    small = client.get(f"/api/v1/players/{STAR}/photo").content
    large = client.get(f"/api/v1/players/{STAR}/photo", params={"size": "large"}).content
    assert large == PHOTOS[STAR] + b"large" and small == PHOTOS[STAR]
    assert client.get(f"/api/v1/players/{STAR}/photo", params={"size": "huge"}).status_code == 422
