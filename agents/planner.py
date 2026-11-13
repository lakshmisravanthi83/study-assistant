import json
import os
import re
from datetime import date, datetime

from dotenv import load_dotenv
from groq import Groq


from db.database import get_weak_topics, save_plan
from ingestion.pipeline import get_all_chunks

load_dotenv()

_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL = "openai/gpt-oss-20b"
MAX_CONTEXT_CHARS = 5000

SYSTEM_PROMPT = (
    "You are a study planning agent. You will be given the full study "
    "material for a subject and a deadline. Extract the main topics "
    "actually covered in the material, then build a day-wise study plan "
    "that sequences foundational topics first, gives more days to denser "
    "topics, and reserves the final day(s) for revision. "
    "Respond with ONLY valid JSON — no markdown fences, no commentary — "
    "matching exactly this schema:\n"
    '{"topics": ["topic 1", "topic 2", ...], '
    '"plan": [{"day": 1, "date": "YYYY-MM-DD", "topics": ["..."], '
    '"focus": "one-line description of the day"}]}'
)


def _get_full_material(subject: str) -> str:
    chunks = get_all_chunks(subject)
    text = "\n\n".join(c["text"] for c in chunks)
    return text[:MAX_CONTEXT_CHARS]


def _strip_json_fences(raw: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)


def generate_plan(subject: str, exam_date: str) -> dict:
    material = _get_full_material(subject)
    if not material.strip():
        return {"error": f"No material ingested for subject '{subject}'. Upload material first."}

    today = date.today()
    try:
        exam_d = datetime.strptime(exam_date, "%Y-%m-%d").date()
    except ValueError:
        return {"error": "exam_date must be in YYYY-MM-DD format"}

    days_remaining = (exam_d - today).days
    if days_remaining <= 0:
        return {"error": "exam_date must be in the future"}
    weak_topics = get_weak_topics(subject)
    weak_topics_note = ""
    if weak_topics:
      weak_topics_note = (
        f"\n\nIMPORTANT — quiz feedback: the student has struggled with these "
        f"topics based on past quiz results: {', '.join(weak_topics)}. "
        f"Prioritize dedicated revision time for these — schedule them earlier "
        f"in the plan and add a focused review/practice day for them, even if "
        f"they were already covered earlier."
    )

    user_message = (
    f"Today's date: {today.isoformat()}\n"
    f"Exam date: {exam_date}\n"
    f"Days available: {days_remaining}"
    f"{weak_topics_note}\n\n"
    f"Study material:\n{material}\n\n"
    "Create the topic list and day-wise plan as instructed."
)
    
    response = _client.chat.completions.create(
        model=MODEL,
        reasoning_effort="low",
        max_tokens=2000,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )

    raw = _strip_json_fences(response.choices[0].message.content)

    try:
        plan_dict = json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "Planner LLM did not return valid JSON", "raw_response": raw}

    save_plan(subject, exam_date, plan_dict)
    return plan_dict
