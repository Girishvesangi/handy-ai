from handy.guides import load_guides, save_guides
from handy.search import BM25, GuideIndex, rrf, tokenize


def test_tokenize_drops_stopwords():
    assert tokenize("How do I fix THE fan on my T480?") == ["fix", "fan", "t480"]


def test_bm25_prefers_matching_doc():
    bm = BM25(["battery replacement macbook", "fan cleaning dell", "ram upgrade thinkpad"])
    scores = bm.scores("macbook battery")
    assert scores.index(max(scores)) == 0
    assert scores[1] == 0


def test_rrf_rewards_agreement():
    # item 2 is near the top of both lists, so it should win
    assert rrf([[1, 2, 3], [2, 3, 1]])[0] == 2


def test_keyword_search_finds_model_numbers(guides):
    index = GuideIndex(guides)
    assert index.search("T480 memory upgrade")[0].id == 1001
    assert index.search("macbook air battery")[0].id == 2002
    assert index.search("xps 9360 ssd")[0].id == 3003


def test_hybrid_uses_vectors(guides):
    for i, g in enumerate(guides):
        g.embedding = [1.0 if j == i else 0.0 for j in range(4)]
    index = GuideIndex(guides)
    assert index.has_embeddings
    # The query matches no keywords, so the vector alone should rank guide 4004 first.
    assert index.search("noisy whirring", query_vec=[0, 0, 0, 1])[0].id == 4004


def test_no_embeddings_means_keyword_only(guides):
    index = GuideIndex(guides)
    assert not index.has_embeddings
    assert index.search("macbook fan", query_vec=[0.1, 0.2])[0].id == 4004


def test_guides_round_trip(tmp_path, guides):
    path = tmp_path / "guides.json"
    save_guides(guides, path)
    loaded = load_guides(path)
    assert [g.id for g in loaded] == [g.id for g in guides]
    assert loaded[0].steps[0].lines == guides[0].steps[0].lines


def test_missing_file_gives_empty_list(tmp_path):
    assert load_guides(tmp_path / "nope.json") == []
