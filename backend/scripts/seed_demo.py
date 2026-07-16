r"""Create an idempotent development-only demo database.

Run from backend: .\.venv\Scripts\python.exe scripts\seed_demo.py
"""
import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.activity.manager import ActivityManager
from src.mastery.manager import MasteryManager
from src.mentor.manager import MentorDecisionEngine
from src.profile.manager import ProfileManager
from src.video.manager import VideoRecommendationService
from src.memory.manager import MemoryManager
from src.memory.storage import get_session_factory
from src.visual_roadmap.models import VisualRoadmap, RoadmapQuiz, RoadmapQuizAttempt
from src.current_affairs.models import CurrentAffairsArticle
from src.current_affairs.service import CurrentAffairsService
from src.current_affairs.quiz_service import CurrentAffairsQuizService
from src.schemas.current_affairs_quiz import QuizCreate, QuizAnswer
from sqlalchemy import select


def seed_demo(db_path: str) -> dict:
    activity = ActivityManager(db_path); mastery = MasteryManager(db_path); profile = ProfileManager(db_path, activity)
    videos = VideoRecommendationService(db_path, activity)
    profile.update({"preferred_language": "english", "preferred_depth": "standard", "preferred_format": "structured", "preferred_content_type": "video", "daily_study_target_minutes": 120, "onboarding_completed": True})

    memory = MemoryManager(db_path)
    titles = {row.title for row in memory.list_conversations()}
    for title, question, answer in (("Polity revision", "Explain Article 32.", "Article 32 provides constitutional remedies."),
        ("Economy practice", "What is the repo rate?", "The repo rate is an RBI monetary policy instrument.")):
        if title not in titles:
            conversation = memory.create_conversation(title); memory.add_user_message(conversation.id, question); memory.add_assistant_message(conversation.id, answer)
    pdf_path = Path(db_path).with_name("demo_upsc_notes.pdf")
    if not pdf_path.exists(): pdf_path.write_bytes(b"%PDF-1.4\n% Development demo fixture: Fundamental Rights and Monetary Policy.\n%%EOF")
    if not activity.list_events(event_type="pdf_uploaded"):
        activity.record_event("pdf_uploaded", datetime.now(timezone.utc), subject="Polity and Governance", topic="Fundamental Rights", metadata_json={"filename": pdf_path.name, "development_fixture": True})

    if not mastery.list_topic_mastery():
        for _ in range(4): mastery.record_evidence(subject="Polity and Governance", topic="Fundamental Rights", evidence_type="recall_success", source="demo_seed")
        mastery.record_evidence(subject="Polity and Governance", topic="Fundamental Rights", evidence_type="revision_completed", source="demo_seed")
        mastery.record_evidence(subject="Economy", topic="Monetary Policy", evidence_type="quiz_incorrect", source="demo_seed")
        mastery.record_evidence(subject="Economy", topic="Monetary Policy", evidence_type="quiz_incorrect", source="demo_seed")
        mastery.record_evidence(subject="Geography", topic="Climatology", evidence_type="recall_failure", occurred_at=datetime.now(timezone.utc) - timedelta(days=60), source="demo_seed")

    factory = get_session_factory(db_path); roadmap_id = "demo-roadmap"; roadmap_quiz_id = "demo-roadmap-quiz"
    svg_path = Path(db_path).with_name("demo_roadmap.svg")
    if not svg_path.exists(): svg_path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="800" height="300"><text x="30" y="60">Demo Constitutional Roadmap</text></svg>', encoding="utf-8")
    structure = {"title": "Constitutional Development", "visual_type": "timeline", "summary": "Development-only grounded roadmap.",
        "nodes": [{"id": f"n{i}", "label": f"Constitution stage {i}", "year": str(1946+i), "description": f"Saved grounded stage {i}.", "importance": f"UPSC point {i}.", "source_ids": ["demo-pdf"]} for i in range(1,6)],
        "connections": [{"from": f"n{i}", "to": f"n{i+1}", "label": "followed by"} for i in range(1,5)], "exam_points": ["Trace constitutional development."], "sources": [{"id": "demo-pdf", "document": pdf_path.name}]}
    with factory() as session:
        if not session.get(VisualRoadmap, roadmap_id): session.add(VisualRoadmap(id=roadmap_id, user_id="user_001", title="Constitutional Development", subject="Polity and Governance", topic="Constitution", visual_type="timeline", language="english", status="ready", structure_json=structure, source_metadata_json=structure["sources"], svg_path=str(svg_path)))
        if not session.get(RoadmapQuiz, roadmap_quiz_id): session.add(RoadmapQuiz(id=roadmap_quiz_id, roadmap_id=roadmap_id, user_id="user_001", difficulty="standard", questions_json=[{"id":"q1","question_type":"true_false","question":"True or false: the roadmap contains five stages.","options":["True","False"],"correct_answer":"True","explanation":"Five saved nodes are present.","source_node_ids":["n1"],"difficulty":"standard","roadmap_id":roadmap_id}]))
        if not session.scalar(select(RoadmapQuizAttempt).where(RoadmapQuizAttempt.quiz_id == roadmap_quiz_id)): session.add(RoadmapQuizAttempt(id="demo-roadmap-attempt", quiz_id=roadmap_quiz_id, user_id="user_001", answers_json=[{"question_id":"q1","answer":"True"}], result_json={"score":1,"total":1,"percentage":100,"weak_source_nodes":[]}))
        session.commit()

    ca_quiz = CurrentAffairsQuizService(db_path, activity=activity, mastery=mastery)
    today = datetime.now(timezone.utc).date()
    with factory() as session:
        if not session.scalar(select(CurrentAffairsArticle).where(CurrentAffairsArticle.id == "demo-ca-1")):
            for index in range(1,3): session.add(CurrentAffairsArticle(id=f"demo-ca-{index}", title=f"Demo RBI policy development {index}", summary=f"What happened: RBI announced grounded demo policy development {index} for regulated institutions.", source_title=f"RBI policy development {index}", publisher="Reserve Bank of India", source_url=f"https://rbi.org.in/demo-policy-{index}", publication_date=today, retrieved_at=datetime.now(timezone.utc), subject="Economy", topic="Monetary Policy", syllabus_tags_json=["GS III"], importance_level="high", relevance_prelims="\n".join(f"Grounded RBI fact {index}-{n}" for n in range(1,7)), relevance_mains="Explain the grounded monetary-policy significance.", content_hash=f"demo-ca-hash-{index}", status="active"))
            session.commit()
    try: CurrentAffairsService(db_path=db_path, llm=object(), indexer=lambda *_: None).generate_daily(today)
    except ValueError: pass
    if not ca_quiz.list():
        quiz = ca_quiz.generate(QuizCreate(period_type="daily", date_from=today, date_to=today, question_count=5), user_id="user_001")
        ca_quiz.submit(quiz.id, [QuizAnswer(question_id=q.id, answer="incorrect demo answer") for q in ca_quiz.questions(quiz.id)], user_id="user_001")

    engine = MentorDecisionEngine(db_path, mastery, profile, activity, videos)
    actions = engine.generate_actions()
    overview = mastery.get_mastery_overview()
    video_matches = videos.recommend(subject="Polity and Governance", topic="Fundamental Rights", language="english", explicit_request=True)
    result = {
        "database": str(Path(db_path).resolve()),
        "strong_topic": overview["strong_topics"][0].topic if overview["strong_topics"] else None,
        "weak_topic": overview["weak_topics"][0].topic if overview["weak_topics"] else None,
        "high_risk_topic": overview["high_risk_topics"][0].topic if overview["high_risk_topics"] else None,
        "completed_revisions": sum(row.revision_count for row in mastery.list_topic_mastery()),
        "quiz_mistakes": sum(row.incorrect_attempts for row in mastery.list_topic_mastery()),
        "mentor_recommendation": actions[0].title if actions else None,
        "trusted_video": video_matches[0]["video"].title if video_matches else None,
        "conversations": len(memory.list_conversations()), "uploaded_pdf": pdf_path.name,
        "visual_roadmap": roadmap_id, "roadmap_quiz_result": roadmap_quiz_id,
        "current_affairs_articles": len(CurrentAffairsService(db_path=db_path, llm=object(), indexer=lambda *_: None).list_articles(date_value=today)),
        "current_affairs_quiz_attempts": len(ca_quiz.attempts()), "high_risk_current_affairs": len(ca_quiz.overview()["high_risk_articles"]),
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--db-path", default="data/demo.sqlite3")
    print(json.dumps(seed_demo(parser.parse_args().db_path), indent=2))
