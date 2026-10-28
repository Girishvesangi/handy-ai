from handy.ifixit import clean_text, parse_guide, parse_search_results


def test_clean_text_strips_markup():
    assert clean_text("Loosen the [link|https://x.y|bottom cover] screws.") == "Loosen the bottom cover screws."
    assert clean_text("[icon_caution] Careful '''now'''") == "Careful now"
    assert clean_text("<p>Hello <b>world</b></p>") == "Hello world"
    assert clean_text(None) == ""


def test_parse_guide(raw_guide):
    g = parse_guide(raw_guide)
    assert g.id == 1001
    assert g.device == "Lenovo ThinkPad T480"
    assert g.tools == ["Phillips #1 Screwdriver", "Spudger"]
    assert g.introduction == "Use this guide to add or replace a RAM module."
    assert [s.number for s in g.steps] == [1, 2, 3]
    assert g.steps[0].image_urls == ["https://img.example/1.large"]  # prefers the largest size
    assert g.steps[1].lines == ["Disconnect the internal battery connector before touching anything else."]
    assert g.steps[2].image_urls == []  # video steps have no photo
    assert g.steps[2].lines == ["Spread the retaining clips and lift the RAM module out at an angle."]


def test_parse_search_results_keeps_only_guides():
    data = {"results": [{"dataType": "guide", "guideid": 5}, {"dataType": "wiki", "title": "x"}, {"dataType": "guide", "guideid": 9}]}
    assert parse_search_results(data) == [5, 9]
