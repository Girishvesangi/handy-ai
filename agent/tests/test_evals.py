from evals.metrics import classification_report, hit_at_k, mrr, percentile
from evals.retrieval import answerable, evaluate, relevant
from evals.step_check import build_proxy_cases
from handy.search import GuideIndex


def test_ranking_metrics():
    ranks = [1, 3, None, 2]
    assert hit_at_k(ranks, 1) == 0.25
    assert hit_at_k(ranks, 3) == 0.75
    assert abs(mrr(ranks) - (1 + 1 / 3 + 1 / 2) / 4) < 1e-9


def test_percentile():
    assert percentile([], 50) == 0
    assert percentile([10, 20, 30, 40, 50], 50) == 30
    assert percentile([10, 20, 30, 40, 50], 95) == 50


def test_classification_report():
    labels = ["done", "done", "wrong", "not_done"]
    preds = ["done", "wrong", "wrong", "not_done"]
    r = classification_report(labels, preds, ["done", "not_done", "wrong", "unclear"])
    assert r["accuracy"] == 0.75
    assert r["false_alarm_rate"] == 0.5
    assert r["mistake_catch_rate"] == 1.0
    assert r["confusion"]["done"]["wrong"] == 1


def test_relevance_with_alternatives(guides):
    assert relevant(guides[0], ["thinkpad", "ram|memory"])
    assert not relevant(guides[0], ["macbook"])


def test_retrieval_eval_on_fixtures(guides):
    queries = [
        {"query": "T480 memory", "must": ["t480", "ram|memory"]},
        {"query": "macbook air battery", "must": ["macbook air", "battery"]},
        {"query": "surface battery", "must": ["surface"]},
    ]
    qs = answerable(queries, guides)
    assert len(qs) == 2  # no Surface guide in the fixtures
    result = evaluate(GuideIndex(guides), qs)
    assert result["hit@1"] == 1.0


def test_proxy_cases_are_balanced(guides):
    cases = build_proxy_cases(guides, 8)
    labels = [c["label"] for c in cases]
    assert labels.count("done") == labels.count("not_done") == 4
    for c in cases:
        if c["label"] == "not_done":
            assert str(c["guide_id"]) not in c["image_url"]  # photo comes from another guide
