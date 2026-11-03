from datetime import date

from app.ingestion.injuries import name_index, normalize_name, transform_injuries


def entry(name, status="Out", **details):
    return {"status": status, "date": "2099-11-03T22:08Z", "athlete": {"displayName": name},
            "details": details}  # fmt: skip


def report(*entries):
    return {"injuries": [{"displayName": "Team", "injuries": list(entries)}]}


def test_names_match_across_accents_suffixes_and_punctuation():
    assert normalize_name("Luka Dončić") == "luka doncic"
    assert normalize_name("P.J. Washington Jr.") == "pj washington"


def test_the_report_keeps_status_injury_side_and_the_estimated_return():
    rows, rejected = transform_injuries(
        report(
            entry("Zed Fixture", type="Hip", side="Left", detail="Strain", returnDate="2099-11-06")
        ),
        name_index([(7, "Zed Fixture")]),
    )
    assert not rejected
    assert rows[0]["player_id"] == 7 and rows[0]["status"] == "Out"
    assert (rows[0]["injury"], rows[0]["detail"], rows[0]["side"]) == ("Hip", "Strain", "Left")
    assert rows[0]["return_date"] == date(2099, 11, 6)


def test_a_missing_return_date_stays_missing():
    rows, _ = transform_injuries(
        report(entry("Zed Fixture", type="Hip")), name_index([(7, "Zed Fixture")])
    )
    assert rows[0]["return_date"] is None


def test_unknown_or_ambiguous_names_are_rejected_not_guessed():
    names = name_index([(1, "Jaylin Williams"), (2, "Jaylin Williams")])
    rows, rejected = transform_injuries(
        report(entry("Jaylin Williams"), entry("Nobody Here")), names
    )
    assert rows == [] and len(rejected) == 2
