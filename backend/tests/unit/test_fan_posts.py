from datetime import UTC, datetime, timedelta

import pytest

from app.config import Settings
from app.ingestion.fan_posts import KEEP_PER_TEAM, score, team_terms, transform_posts

NOW = datetime(2099, 11, 3, 12, tzinfo=UTC)
TERMS = ["Lakers", "Los Angeles Lakers"]
GOOD = "The Lakers finally look like a real team on defense"


def post(text=GOOD, *, likes=10, handle="fan.example.com", key="abc", age=1.0, **extra):
    return {
        "uri": f"at://did:plc:x/app.bsky.feed.post/{key}",
        "author": {"handle": handle, "displayName": "A Fan", **extra.pop("author", {})},
        "record": {
            "text": text,
            "createdAt": (NOW - timedelta(days=age)).isoformat().replace("+00:00", "Z"),
            **extra.pop("record", {}),
        },
        "likeCount": likes,
        "repostCount": 1,
        "replyCount": 2,
        **extra,
    }


def test_a_good_post_keeps_its_text_author_and_a_link_to_the_original():
    [row] = transform_posts(1, TERMS, [post()], NOW)
    assert row["text"] == GOOD and row["author_handle"] == "fan.example.com"
    assert row["url"] == "https://bsky.app/profile/fan.example.com/post/abc"
    assert (row["likes"], row["reposts"], row["replies"]) == (10, 1, 2)


@pytest.mark.parametrize(
    "bad",
    [
        pytest.param(
            post(author={"labels": [{"val": "!no-unauthenticated"}]}), id="author opted out"
        ),
        pytest.param(post(labels=[{"val": "porn"}]), id="moderation label"),
        pytest.param(post("#nba lol, what a night for hoops"), id="never names the team"),
        pytest.param(post("Lakers in 5"), id="too short"),
        pytest.param(post("Final:\nRaptors 125\nLakers 131 tonight"), id="score bot"),
        pytest.param(
            post("Lakers 38 Warriors 15 Lakers 15 Warriors 38 12 14 8"), id="mostly numbers"
        ),
        pytest.param(post(f"{GOOD}, holy shit"), id="profanity"),
        pytest.param(post(f"{GOOD}. Take my parlay"), id="betting"),
        pytest.param(post(f"{GOOD}, unlike Trump"), id="politics"),
        pytest.param(post(likes=2), id="too little engagement"),
        pytest.param(post(age=8), id="too old"),
        pytest.param(post(age=-1), id="dated in the future"),
        pytest.param(post(record={"reply": {"root": {}}}), id="reply without its thread"),
        pytest.param(
            post(embed={"$type": "app.bsky.embed.record#view"}), id="quote without its post"
        ),
        pytest.param(post(handle="bad/handle"), id="handle that can't make a link"),
    ],
)
def test_noise_and_opted_out_posts_are_left_out(bad):
    assert transform_posts(1, TERMS, [bad], NOW) == []


def test_a_team_word_inside_another_word_does_not_count():
    assert (
        transform_posts(1, ["Heat"], [post("The heatwave broke, what a relief this week")], NOW)
        == []
    )


def test_everyday_nicknames_need_the_full_name():
    assert team_terms("Miami", "Heat") == ["Miami Heat"]
    assert team_terms("Los Angeles", "Lakers") == ["Lakers", "Los Angeles Lakers"]


def test_each_author_appears_once_and_the_best_posts_come_first():
    posts = [
        post(key="a", handle="one.example.com", likes=5),
        post(key="b", handle="one.example.com", likes=50),
        post(key="c", handle="two.example.com", likes=20),
    ]
    rows = transform_posts(1, TERMS, posts, NOW)
    assert [r["uri"][-1] for r in rows] == ["b", "c"]


def test_at_most_a_few_posts_are_kept_per_team():
    posts = [post(key=str(i), handle=f"u{i}.example.com") for i in range(KEEP_PER_TEAM + 3)]
    assert len(transform_posts(1, TERMS, posts, NOW)) == KEEP_PER_TEAM


def test_recent_posts_outrank_equally_liked_older_ones():
    assert score(10, 0, 0, 0.5) > score(10, 0, 0, 5)


def test_the_app_password_never_shows_in_settings_output():
    settings = Settings(bluesky_app_password="not-a-real-secret")
    assert "not-a-real-secret" not in repr(settings)
