from scripts.seed_demo import seed_demo


def test_demo_seed_is_complete_and_idempotent(tmp_path):
    path = str(tmp_path / "demo.sqlite3")
    first = seed_demo(path); second = seed_demo(path)
    assert first["strong_topic"] == "Fundamental Rights"
    assert first["weak_topic"]
    assert first["high_risk_topic"]
    assert first["completed_revisions"] >= 1
    assert first["quiz_mistakes"] >= 1
    assert first["mentor_recommendation"]
    assert first["trusted_video"]
    assert first["long_term_history"]["conversations_added"] == 6
    assert first["long_term_history"]["messages_added"] == 12
    assert first["long_term_history"]["mastery_topics_added"] == 12
    assert first["long_term_history"]["visual_roadmaps_added"] == 6
    assert second["long_term_history"]["conversations_added"] == 0
    assert second["long_term_history"]["visual_roadmaps_added"] == 0
