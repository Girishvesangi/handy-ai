from handy.tracker import StepTracker


def test_walks_through_a_guide(guides):
    t = StepTracker()
    assert not t.active and t.current is None
    assert t.describe_current() == "No guide is active."

    t.start(guides[0])
    assert t.current.number == 1
    assert t.describe_current().startswith("Step 1 of 3 (Bottom cover): Shut down")

    assert t.next().number == 2
    assert t.completed == {1}
    assert t.previous().number == 1
    assert t.go_to(3).number == 3
    assert t.is_last
    assert t.next() is None  # finished
    assert t.completed == {1, 3}


def test_bounds(guides):
    t = StepTracker()
    t.start(guides[0])
    assert t.previous().number == 1  # can't go before step 1
    assert t.go_to(99).number == 1  # out of range is ignored


def test_state_for_the_web_app(guides):
    t = StepTracker()
    assert t.state() == {"guide": None}
    t.start(guides[0])
    s = t.state()
    assert s["guide"]["total_steps"] == 3
    assert s["step"]["number"] == 1
    assert s["step"]["image_urls"] == ["https://img.example/1.large"]
    t.stop()
    assert not t.active


def test_recap_counts_checks_and_mistakes(guides):
    t = StepTracker()
    assert t.recap() == {}
    t.start(guides[0])
    t.record_check("done", "ok")
    t.next()
    t.record_check("wrong", "Pried the battery with a metal tool.")
    r = t.recap()
    assert r["checks"] == 2
    assert r["steps_completed"] == 1
    assert r["mistakes_caught"] == [{"step": 2, "reason": "Pried the battery with a metal tool."}]
    assert r["minutes"] >= 0
