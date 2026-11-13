import json
import os
import re
import uuid
from collections import defaultdict
from ingestion.pipeline import keyword_search, query_subject

from dotenv import load_dotenv
from groq import Groq


from db.database import get_quiz, save_quiz, save_quiz_result
from ingestion.pipeline import query_subject

load_dotenv()

_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "openai/gpt-oss-20b"

MAX_CONTEXT_CHARS = 12000

RELEVANCE_THRESHOLD = 0.8


RELEVANCE_THRESHOLD = 0.8  # fallback only, used if keyword search finds nothing

SYSTEM_PROMPT = (
    "You are a quiz-generation agent for a study assistant. You will be "
    "given source material covering one or more topics. Write multiple-"
    "choice questions grounded ONLY in that material — do not invent facts "
    "or ask about anything not covered in the material. "
    "IMPORTANT: only write questions that are DIRECTLY about the topics "
    "listed by the user. If the provided material contains content that is "
    "only loosely or tangentially related to the listed topics, IGNORE that "
    "content completely rather than writing a question about it. Every "
    "question's 'topic' field must exactly match one of the user-provided "
    "topics, and the question itself must genuinely test that topic — not "
    "just something the retrieved text happened to also mention. "
    "Each question must have exactly 4 options and one correct option. "
    "Respond with ONLY valid JSON — no markdown fences, no commentary — "
    "matching exactly this schema:\n"
    '{"questions": [{"id": "q1", "topic": "<one of the given topics>", '
    '"question": "...", "options": {"a": "...", "b": "...", "c": "...", '
    '"d": "..."}, "correct_option": "a", "explanation": "why this is correct"}]}'
)

def _strip_json_fences(raw: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)

def _gather_context(subject: str, topics: list) -> str:
    seen = set()
    pieces = []
    for topic in topics:
        matched = keyword_search(subject, topic)

        if not matched:
            chunks = query_subject(subject, topic, n_results=5)
            matched = [c for c in chunks if c.get("distance") is None or c["distance"] <= RELEVANCE_THRESHOLD]

        for chunk in matched:
            key = (chunk["source"], chunk["chunk_index"])
            if key not in seen:
                seen.add(key)
                pieces.append(f"[Topic context: {topic} | Source: {chunk['source']}]\n{chunk['text']}")
    return "\n\n".join(pieces)[:MAX_CONTEXT_CHARS]


def generate_quiz(subject: str, topics: list, n_questions: int = 5) -> dict:
    context = _gather_context(subject, topics)
    if not context.strip():
        return {"error": f"No material found for topics {topics} in subject '{subject}'."}

    user_message = (
        f"Topics to quiz on: {', '.join(topics)}\n"
        f"Number of questions: {n_questions}\n\n"
        f"Source material:\n{context}\n\n"
        "Generate the quiz as instructed."
    )

    response = _client.chat.completions.create(
        model=MODEL,
        max_tokens=2000,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )

    raw = _strip_json_fences(response.choices[0].message.content)
    try:
        quiz_dict = json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "Evaluator LLM did not return valid JSON", "raw_response": raw}

    quiz_id = str(uuid.uuid4())
    save_quiz(quiz_id, subject, quiz_dict)

    client_questions = [
        {"id": q["id"], "topic": q["topic"], "question": q["question"], "options": q["options"]}
        for q in quiz_dict["questions"]
    ]
    return {"quiz_id": quiz_id, "questions": client_questions}


def submit_quiz(quiz_id: str, answers: dict) -> dict:
    record = get_quiz(quiz_id)
    if not record:
        return {"error": f"No quiz found with id '{quiz_id}'"}

    subject = record["subject"]
    questions = record["quiz"]["questions"]

    results = []
    correct_count = 0
    wrong_topics = defaultdict(int)

    for q in questions:
        qid = q["id"]
        submitted = answers.get(qid)
        is_correct = submitted is not None and submitted == q["correct_option"]
        if is_correct:
            correct_count += 1
        else:
            wrong_topics[q["topic"]] += 1

        results.append({
            "id": qid,
            "topic": q["topic"],
            "your_answer": submitted,
            "correct_option": q["correct_option"],
            "correct": is_correct,
            "explanation": q["explanation"],
        })

    total = len(questions)
    score = round(correct_count / total, 2) if total else 0.0
    weak_topics = list(wrong_topics.keys())

    save_quiz_result(quiz_id, score, weak_topics)

    return {
        "subject": subject,
        "score": score,
        "correct": correct_count,
        "total": total,
        "weak_topics": weak_topics,
        "results": results,
    }