r"""Seed realistic, idempotent long-term learner activity for local demos.

Run from ``backend``::

    .\.venv\Scripts\python.exe scripts\seed_long_term_history.py
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


SUBJECTS = (
    ("Polity and Governance", ("Fundamental Rights", "Parliament", "Federalism", "Judiciary")),
    ("History", ("Modern India", "Freedom Struggle", "Ancient India", "Art and Culture")),
    ("Geography", ("Indian Monsoon", "Climatology", "Rivers", "Human Geography")),
    ("Economy", ("Monetary Policy", "Inflation", "Fiscal Policy", "Banking")),
    ("Environment and Ecology", ("Biodiversity", "Climate Change", "Conservation", "Pollution")),
    ("Science and Technology", ("Space Technology", "Biotechnology", "AI Governance", "Cyber Security")),
    ("Ethics", ("Integrity", "Public Service Values", "Case Studies", "Accountability")),
    ("Current Affairs", ("International Relations", "Government Schemes", "Economy", "Environment")),
)

SEARCHES = (
    ("Polity and Governance", "article 32 constitutional remedies"),
    ("Polity and Governance", "fundamental rights landmark cases"),
    ("History", "1857 revolt causes upsc"),
    ("History", "gandhian movements timeline"),
    ("Geography", "indian monsoon mechanism"),
    ("Geography", "el nino impact on india"),
    ("Economy", "repo rate inflation relationship"),
    ("Economy", "fiscal deficit upsc notes"),
    ("Environment and Ecology", "biodiversity hotspots india"),
    ("Environment and Ecology", "climate conventions comparison"),
    ("Science and Technology", "space missions current affairs"),
    ("Ethics", "ethics case study examples"),
    ("Current Affairs", "important government schemes"),
    ("Current Affairs", "india international relations update"),
)

SEARCH_PAGES = ("chat", "revision", "visual", "upsc_books", "current_affairs")

DEMO_CONVERSATIONS = (
    ("polity", "Fundamental Rights — Mains preparation", "How should I structure a Mains answer on Article 32?", "Open with constitutional remedies, explain writ jurisdiction, add one landmark case, and conclude with its role as the Constitution's protective mechanism."),
    ("economy", "Inflation and monetary policy", "Compare demand-pull and cost-push inflation with Indian examples.", "Demand-pull inflation follows excess demand; cost-push inflation follows rising input costs. Use food supply shocks and fuel prices as grounded Indian examples."),
    ("history", "Modern History revision", "Create a quick revision sequence for Gandhian movements.", "Revise Champaran, Ahmedabad, Kheda, Non-Cooperation, Civil Disobedience, and Quit India in chronological order with cause, method, outcome, and UPSC significance."),
    ("geography", "Indian Monsoon concepts", "Why does El Niño often weaken the Indian monsoon?", "El Niño changes Pacific pressure and circulation patterns, which can weaken the monsoon flow. Treat it as an influence, not a guaranteed one-to-one cause."),
    ("environment", "Climate conventions comparison", "Compare UNFCCC, Kyoto Protocol, and Paris Agreement.", "Organize the comparison by adoption year, legal character, country coverage, targets, finance, and India's position."),
    ("ethics", "Ethics case-study practice", "Give me a framework for an integrity case study.", "Identify stakeholders, competing values, legal constraints, options, consequences, and a justified course of action with safeguards."),
)

DEMO_MASTERY = (
    ("Polity and Governance", "Fundamental Rights", .72, .78, 14, 9, 5, 3),
    ("Polity and Governance", "Parliament", .64, .69, 11, 7, 4, 2),
    ("Economy", "Monetary Policy", .58, .84, 12, 6, 6, 2),
    ("Economy", "Inflation", .67, .63, 10, 7, 3, 3),
    ("History", "Freedom Struggle", .81, .42, 16, 13, 3, 5),
    ("History", "Art and Culture", .49, .88, 9, 4, 5, 1),
    ("Geography", "Indian Monsoon", .74, .55, 13, 10, 3, 4),
    ("Environment and Ecology", "Biodiversity", .62, .71, 10, 6, 4, 2),
    ("Science and Technology", "Space Technology", .55, .79, 8, 4, 4, 1),
    ("Ethics", "Integrity", .77, .47, 12, 10, 2, 4),
    ("Current Affairs", "Government Schemes", .51, .86, 7, 3, 4, 1),
    ("International Relations", "India and Indo-Pacific", .60, .73, 9, 5, 4, 2),
)

DEMO_ROADMAPS = (
    ("constitutional", "Constitutional Development Timeline", "Polity and Governance", "Constitutional Development", "timeline"),
    ("monsoon", "Indian Monsoon Mechanism", "Geography", "Indian Monsoon", "process"),
    ("inflation", "Inflation Cause-and-Effect Map", "Economy", "Inflation", "cause_effect"),
    ("freedom", "Freedom Struggle Milestones", "History", "Freedom Struggle", "timeline"),
    ("climate", "Climate Agreements Comparison", "Environment and Ecology", "Climate Change", "comparison"),
    ("parliament", "How a Bill Becomes Law", "Polity and Governance", "Parliament", "flowchart"),
)


def _event(event_id: str, event_type: str, occurred_at: datetime, **values) -> dict:
    return {
        "id": event_id, "user_id": "user_001", "event_type": event_type,
        "occurred_at": occurred_at, "consented": True,
        "metadata_json": {"source": "long_term_demo_seed", **values.pop("metadata_json", {})},
        "conversation_id": None, "subject": None, "topic": None, "duration_seconds": None,
        **values,
    }


def seed_long_term_history(db_path: str, *, start_date: date = date(2023, 1, 9), end_date: date | None = None) -> dict:
    """Add a reproducible multi-year learning history without replacing real rows."""
    end_date = end_date or datetime.now(timezone.utc).date()
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")

    rng = random.Random(20230109)
    events: list[dict] = []
    day = start_date
    active_days = 0
    while day <= end_date:
        # Four to six study days per week, with occasional realistic breaks.
        is_break = day.month == 6 and 10 <= day.day <= 16
        active = day.weekday() < 5 or (day.weekday() == 5 and rng.random() < 0.58)
        if active and not is_break and rng.random() < 0.91:
            active_days += 1
            index = (day.toordinal() + day.month) % len(SUBJECTS)
            subject, topics = SUBJECTS[index]
            topic = topics[(day.day + day.month) % len(topics)]
            started = datetime.combine(day, time(hour=6 + day.day % 3, minute=(day.day * 7) % 60), timezone.utc)
            duration_minutes = 55 + rng.randint(0, 105) + min((day.year - start_date.year) * 8, 24)
            events.append(_event(
                f"history-study-{day.isoformat()}", "study_time_logged", started,
                subject=subject, topic=topic, duration_seconds=duration_minutes * 60,
                metadata_json={"page": "study_workspace", "session_kind": "focused_study"},
            ))

            if active_days % 2 == 0:
                events.append(_event(
                    f"history-question-{day.isoformat()}", "question_asked", started + timedelta(minutes=duration_minutes // 2),
                    subject=subject, topic=topic, metadata_json={"page": "chat", "mode": "learn"},
                ))
            if active_days % 3 == 0:
                search_subject, query = SEARCHES[(active_days + day.month) % len(SEARCHES)]
                page = SEARCH_PAGES[(active_days + day.month) % len(SEARCH_PAGES)]
                events.append(_event(
                    f"history-search-{day.isoformat()}", "internal_search", started + timedelta(minutes=12),
                    subject=search_subject, topic=query,
                    metadata_json={"page": page, "context": "UPSC AI Mentor only"},
                ))
            if active_days % 7 == 0:
                events.append(_event(
                    f"history-revision-{day.isoformat()}", "revision_completed", started + timedelta(minutes=duration_minutes),
                    subject=subject, topic=topic, metadata_json={"page": "revision", "method": "active_recall"},
                ))
            if active_days % 11 == 0:
                events.append(_event(
                    f"history-test-{day.isoformat()}", "prelims_test_completed", started + timedelta(minutes=duration_minutes + 25),
                    subject=subject, topic=topic,
                    metadata_json={"page": "tests", "score_percent": 56 + (active_days % 35), "question_count": 20},
                ))
            if active_days % 19 == 0:
                events.append(_event(
                    f"history-book-{day.isoformat()}", "upsc_book_opened", started + timedelta(minutes=5),
                    subject=subject, topic=topic, metadata_json={"page": "upsc_books"},
                ))
            if active_days % 29 == 0:
                events.append(_event(
                    f"history-roadmap-{day.isoformat()}", "visual_roadmap_generated", started + timedelta(minutes=35),
                    subject=subject, topic=topic, metadata_json={"page": "visual", "visual_type": "mind_map"},
                ))
        day += timedelta(days=1)

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS activity_events (
                id VARCHAR(64) PRIMARY KEY, user_id VARCHAR(64) NOT NULL DEFAULT 'user_001',
                event_type VARCHAR(64) NOT NULL, conversation_id VARCHAR(64),
                subject VARCHAR(128), topic VARCHAR(255), duration_seconds INTEGER,
                details JSON, consented BOOLEAN NOT NULL DEFAULT 1,
                occurred_at DATETIME NOT NULL, recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        added = 0
        for row in events:
            cursor = connection.execute(
                """INSERT OR IGNORE INTO activity_events
                   (id, user_id, event_type, conversation_id, subject, topic, duration_seconds, details, consented, occurred_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row["id"], row["user_id"], row["event_type"], row["conversation_id"], row["subject"],
                 row["topic"], row["duration_seconds"], json.dumps(row["metadata_json"]), int(row["consented"]),
                 # Match SQLAlchemy's SQLite DateTime representation. Mixing
                 # offset-aware seed strings with existing naive UTC rows makes
                 # Python sorting/min operations fail in activity summaries.
                 row["occurred_at"].astimezone(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")),
            )
            added += cursor.rowcount

        # Refresh metadata on older seeded search rows created before page-level
        # histories were introduced. This never changes real learner activity.
        for row in (item for item in events if item["event_type"] == "internal_search"):
            connection.execute(
                "update activity_events set details=? where id=? and json_extract(details, '$.source')='long_term_demo_seed'",
                (json.dumps(row["metadata_json"]), row["id"]),
            )

        feature_counts = _seed_feature_records(connection, Path(db_path), end_date)
        connection.commit()

    return {
        "database": str(Path(db_path).resolve()),
        "history_from": start_date.isoformat(),
        "history_to": end_date.isoformat(),
        "learning_days": active_days,
        "events_planned": len(events),
        "events_added": added,
        "events_already_present": len(events) - added,
        **feature_counts,
    }


def _seed_feature_records(connection: sqlite3.Connection, db_path: Path, end_date: date) -> dict:
    """Populate real feature tables used by Coach, Revision, and Visual Learning."""
    tables = {row[0] for row in connection.execute("select name from sqlite_master where type='table'")}
    required = {"conversations", "conversation_messages", "topic_mastery", "visual_roadmaps"}
    if not required.issubset(tables):
        return {"conversations_added": 0, "messages_added": 0, "mastery_topics_added": 0, "visual_roadmaps_added": 0}
    now = datetime.combine(end_date, time(hour=9), timezone.utc).replace(tzinfo=None)
    conversation_added = message_added = mastery_added = roadmap_added = 0

    for index, (key, title, question, answer) in enumerate(DEMO_CONVERSATIONS):
        conversation_id = f"history-conversation-{key}"
        created = now - timedelta(days=index * 23 + 4)
        conversation_added += connection.execute(
            "insert or ignore into conversations (id,title,created_at,updated_at) values (?,?,?,?)",
            (conversation_id, title, created.isoformat(sep=" "), (created + timedelta(minutes=18)).isoformat(sep=" ")),
        ).rowcount
        for role, content, offset in (("user", question, 0), ("assistant", answer, 2)):
            exists = connection.execute(
                "select 1 from conversation_messages where conversation_id=? and role=? and content=?",
                (conversation_id, role, content),
            ).fetchone()
            if not exists:
                connection.execute(
                    "insert into conversation_messages (conversation_id,role,content,created_at) values (?,?,?,?)",
                    (conversation_id, role, content, (created + timedelta(minutes=offset)).isoformat(sep=" ")),
                )
                message_added += 1

    for index, (subject, topic, mastery, risk, attempts, correct, incorrect, revisions) in enumerate(DEMO_MASTERY):
        key = f"history-mastery-{index:02d}"
        revised = now - timedelta(days=8 + index * 3)
        next_revision = now - timedelta(days=max(1, index % 6)) if risk >= .69 else now + timedelta(days=4 + index)
        mastery_added += connection.execute(
            """insert or ignore into topic_mastery
               (id,user_id,subject,topic,mastery_score,forgetting_risk,confidence_score,total_attempts,
                correct_attempts,incorrect_attempts,revision_count,last_attempt_at,last_revised_at,next_revision_at,
                explanation_json,created_at,updated_at)
               values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (key, "user_001", subject, topic, mastery, risk, max(.35, mastery - .06), attempts, correct,
             incorrect, revisions, (revised + timedelta(days=3)).isoformat(sep=" "), revised.isoformat(sep=" "),
             next_revision.isoformat(sep=" "), json.dumps([f"{topic} is scheduled from recorded recall and test performance.", f"Forgetting risk is {round(risk * 100)}% based on elapsed time and evidence."]),
             (revised - timedelta(days=180)).isoformat(sep=" "), now.isoformat(sep=" ")),
        ).rowcount

    visual_dir = db_path.parent / "seeded_visuals"
    visual_dir.mkdir(parents=True, exist_ok=True)
    for index, (key, title, subject, topic, visual_type) in enumerate(DEMO_ROADMAPS):
        roadmap_id = f"history-roadmap-{key}"
        svg_path = visual_dir / f"{key}.svg"
        if not svg_path.exists():
            svg_path.write_text(
                f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="420" viewBox="0 0 900 420"><rect width="900" height="420" fill="#09172e"/><text x="48" y="58" fill="#eef3ff" font-size="28" font-family="Arial">{title}</text><path d="M100 210 H800" stroke="#6574e8" stroke-width="5"/>' + ''.join(f'<circle cx="{150+n*145}" cy="210" r="28" fill="#263d75"/><text x="{143+n*145}" y="217" fill="#fff" font-size="18">{n+1}</text>' for n in range(5)) + '</svg>',
                encoding="utf-8",
            )
        created = now - timedelta(days=index * 17 + 2)
        source = {"id": "general-upsc", "source_type": "general", "document": None, "title": "General UPSC knowledge", "url": None, "publisher": None, "domain": None, "retrieved_at": None, "source_category": None, "trust_level": None, "page_start": None, "page_end": None, "chunk_id": None}
        nodes = [{"id": f"n{n}", "label": f"{topic} point {n}", "description": f"Reviewed UPSC learning point {n} for {topic}.", "importance": f"Useful revision anchor for {topic}.", "source_ids": [source["id"]]} for n in range(1, 6)]
        structure = {"title": title, "summary": f"A saved {visual_type.replace('_', ' ')} used to revise {topic}.", "visual_type": visual_type, "nodes": nodes, "connections": [], "exam_points": [f"Connect {topic} to Prelims facts and Mains analysis."], "sources": [source]}
        roadmap_added += connection.execute(
            """insert or ignore into visual_roadmaps
               (id,user_id,conversation_id,title,subject,topic,visual_type,language,status,structure_json,
                source_metadata_json,svg_path,png_path,created_at,updated_at)
               values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (roadmap_id, "user_001", None, title, subject, topic, visual_type, "english", "ready",
             json.dumps(structure), json.dumps([source]), str(svg_path.resolve()), None,
             created.isoformat(sep=" "), created.isoformat(sep=" ")),
        ).rowcount
        connection.execute(
            "update visual_roadmaps set structure_json=?,source_metadata_json=?,svg_path=? where id=?",
            (json.dumps(structure), json.dumps([source]), str(svg_path.resolve()), roadmap_id),
        )

    return {"conversations_added": conversation_added, "messages_added": message_added, "mastery_topics_added": mastery_added, "visual_roadmaps_added": roadmap_added}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="data/memory.sqlite3")
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2023, 1, 9))
    args = parser.parse_args()
    print(json.dumps(seed_long_term_history(args.db_path, start_date=args.start_date), indent=2))
