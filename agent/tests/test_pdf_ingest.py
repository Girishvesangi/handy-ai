from handy.guides import Guide
from handy.pdf_ingest import merge, stable_id, to_guides

SAMPLE = {
    "guides": [
        {
            "title": "Latitude 5490 Battery Replacement",
            "page": 31,
            "tools": ["Phillips #0 screwdriver"],
            "steps": [
                {"title": "Before you begin", "lines": ["Turn off the computer.", "Disconnect the AC adapter."]},
                {"title": "Battery", "lines": ["Remove the two screws.", ""]},
            ],
        },
        {"title": "Too short", "steps": [{"title": "only one", "lines": ["x"]}]},
    ]
}


def test_to_guides():
    guides = to_guides(SAMPLE, "Dell Latitude 5490", "https://example.com/manual.pdf")
    assert len(guides) == 1  # single-step procedures are dropped
    g = guides[0]
    assert g.id < 0
    assert g.url == "https://example.com/manual.pdf#page=31"
    assert g.tools == ["Phillips #0 screwdriver"]
    assert [s.number for s in g.steps] == [1, 2]
    assert g.steps[1].lines == ["Remove the two screws."]
    assert "page 31" in g.introduction


def test_ids_are_stable_and_merge_replaces():
    assert stable_id("A", "B") == stable_id("A", "B") != stable_id("A", "C")
    old = Guide(stable_id("D", "T"), "T", "D", "", steps=[])
    keep = Guide(5, "iFixit guide", "X", "")
    new = Guide(stable_id("D", "T"), "T v2", "D", "", steps=[])
    merged = merge([keep, old], [new])
    assert [g.title for g in merged] == ["iFixit guide", "T v2"]
