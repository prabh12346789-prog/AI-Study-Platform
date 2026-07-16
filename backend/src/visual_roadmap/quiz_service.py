from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from src.activity.manager import ActivityManager
from src.mastery.manager import MasteryManager
from src.memory.storage import get_session_factory
from src.schemas.roadmap_quiz import QuizQuestion
from src.schemas.visual_roadmap import RoadmapStructure
from src.visual_roadmap.models import RoadmapQuiz, RoadmapQuizAttempt
from src.visual_roadmap.service import VisualRoadmapService


class RoadmapQuizService:
    def __init__(self, db_path=None, roadmap_service=None, activity_manager=None, mastery_manager=None):
        self.sessions = get_session_factory(db_path)
        self.roadmaps = roadmap_service or VisualRoadmapService(db_path=db_path)
        self.activity = activity_manager or ActivityManager(db_path)
        self.mastery = mastery_manager or MasteryManager(db_path)

    @staticmethod
    def _question(roadmap_id, index, kind, text, answer, explanation, nodes, difficulty, options=None):
        return QuizQuestion(id=f"q{index}", roadmap_id=roadmap_id, question_type=kind, question=text,
            options=options or [], correct_answer=answer, explanation=explanation,
            source_node_ids=nodes, difficulty=difficulty).model_dump()

    def generate(self, roadmap_id: str, *, question_count=5, difficulty="standard", user_id="user_001"):
        roadmap = self.roadmaps.get(roadmap_id, user_id=user_id)
        if not roadmap or roadmap.status != "ready": raise ValueError("Valid ready roadmap not found")
        data = RoadmapStructure.model_validate(roadmap.structure_json)
        nodes = data.nodes
        if len(nodes) < 3: raise ValueError("Roadmap needs at least three informative nodes for a recall quiz")
        questions = []
        labels = [node.label for node in nodes]
        years = [node for node in nodes if node.year]
        # Timeline chronology uses only the saved node order, which is the validated visual sequence.
        if data.visual_type == "timeline":
            chosen = nodes[:min(4, len(nodes))]
            answer = " | ".join(node.id for node in chosen)
            options = [f"{node.id}: {node.label}" for node in chosen]
            questions.append(self._question(roadmap_id, 1, "sequence", "Arrange these roadmap events in the displayed chronological order.", answer,
                "The order follows the validated timeline roadmap.", [node.id for node in chosen], difficulty, options))
        for node in nodes:
            if len(questions) >= question_count: break
            distractors = [label for label in labels if label != node.label][:3]
            if len(distractors) >= 2:
                options = [node.label] + distractors
                rotation = len(questions) % len(options); options = options[rotation:] + options[:rotation]
                questions.append(self._question(roadmap_id, len(questions)+1, "mcq",
                    f"Which roadmap event matches this description: {node.description}", node.label,
                    f"{node.label}: {node.importance or node.description}", [node.id], difficulty, options))
        if len(questions) < question_count and len(years) >= 2:
            for node in years:
                if len(questions) >= question_count: break
                options = list(dict.fromkeys([item.year for item in years if item.year]))
                if len(options) >= 2:
                    questions.append(self._question(roadmap_id, len(questions)+1, "match_year",
                        f"Match {node.label} with its year.", node.year, f"The saved roadmap pairs {node.label} with {node.year}.", [node.id], difficulty, options))
        if len(questions) < question_count:
            node = nodes[0]
            questions.append(self._question(roadmap_id, len(questions)+1, "short_recall",
                f"Recall the roadmap event described as: {node.description}", node.label,
                f"The saved roadmap identifies this as {node.label}.", [node.id], difficulty))
        for node in nodes:
            if len(questions) >= question_count: break
            statement = node.importance or node.description
            questions.append(self._question(roadmap_id, len(questions)+1, "true_false",
                f"True or false: the roadmap states that {node.label} — {statement}", "True",
                f"This statement is taken directly from node {node.label}.", [node.id], difficulty, ["True", "False"]))
        if len(questions) < question_count:
            raise ValueError("Roadmap does not contain enough distinct information for the requested quiz")
        texts = [q["question"] for q in questions[:question_count]]
        if len(texts) != len(set(texts)): raise ValueError("Roadmap could not produce distinct questions")
        quiz = RoadmapQuiz(id=str(uuid.uuid4()), roadmap_id=roadmap_id, user_id=user_id,
            difficulty=difficulty, questions_json=questions[:question_count])
        with self.sessions() as session: session.add(quiz); session.commit(); session.refresh(quiz)
        self.activity.record_event("roadmap_quiz_started", datetime.now(timezone.utc), user_id=user_id,
            conversation_id=roadmap.conversation_id, subject=roadmap.subject, topic=roadmap.topic,
            metadata_json={"roadmap_id": roadmap.id, "quiz_id": quiz.id, "total": question_count})
        return quiz

    def get(self, roadmap_id: str, *, user_id="user_001"):
        if not self.roadmaps.get(roadmap_id, user_id=user_id): return None
        with self.sessions() as session:
            return session.scalar(select(RoadmapQuiz).where(RoadmapQuiz.roadmap_id == roadmap_id,
                RoadmapQuiz.user_id == user_id).order_by(RoadmapQuiz.created_at.desc()))

    @staticmethod
    def _normalize(value): return " ".join(str(value).casefold().split())

    def submit(self, roadmap_id: str, answers, *, user_id="user_001"):
        roadmap = self.roadmaps.get(roadmap_id, user_id=user_id); quiz = self.get(roadmap_id, user_id=user_id)
        if not roadmap or not quiz: raise ValueError("Roadmap quiz not found")
        with self.sessions() as session:
            existing = session.scalar(select(RoadmapQuizAttempt).where(RoadmapQuizAttempt.quiz_id == quiz.id, RoadmapQuizAttempt.user_id == user_id))
            if existing: return existing.result_json
        submitted = {answer.question_id: answer.answer for answer in answers}
        results = []
        for question in quiz.questions_json:
            answer = submitted.get(question["id"], "")
            correct = self._normalize(answer) == self._normalize(question["correct_answer"])
            results.append({"question_id": question["id"], "correct": correct, "submitted_answer": answer,
                "correct_answer": question["correct_answer"], "explanation": question["explanation"],
                "source_node_ids": question["source_node_ids"]})
        score = sum(item["correct"] for item in results); total = len(results)
        result = {"score": score, "total": total, "percentage": round(score / total * 100, 1),
            "correct_answers": [item for item in results if item["correct"]],
            "incorrect_answers": [item for item in results if not item["correct"]],
            "explanations": [item["explanation"] for item in results],
            "weak_source_nodes": sorted({node for item in results if not item["correct"] for node in item["source_node_ids"]})}
        attempt = RoadmapQuizAttempt(id=str(uuid.uuid4()), quiz_id=quiz.id, user_id=user_id,
            answers_json=[answer.model_dump() for answer in answers], result_json=result)
        with self.sessions() as session: session.add(attempt); session.commit()
        completed = self.activity.record_event("roadmap_quiz_completed", datetime.now(timezone.utc), user_id=user_id,
            conversation_id=roadmap.conversation_id, subject=roadmap.subject, topic=roadmap.topic,
            metadata_json={"roadmap_id": roadmap.id, "quiz_id": quiz.id, "score": score, "total": total, "percentage": result["percentage"]})
        for item in results:
            self.mastery.record_evidence(subject=roadmap.subject, topic=roadmap.topic, user_id=user_id,
                evidence_type="quiz_correct" if item["correct"] else "quiz_incorrect", score=1 if item["correct"] else 0,
                confidence=1, source="roadmap_quiz", metadata_json={"roadmap_id": roadmap.id, "quiz_id": quiz.id,
                    "source_node_ids": item["source_node_ids"]}, source_activity_event_id=f"{completed.id}:{item['question_id']}")
        return result
