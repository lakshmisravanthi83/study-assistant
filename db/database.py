import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "study_assistant.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS plans (
            subject TEXT PRIMARY KEY,
            exam_date TEXT,
            created_at TEXT,
            plan_json TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quizzes (
            quiz_id TEXT PRIMARY KEY,
            subject TEXT,
            created_at TEXT,
            quiz_json TEXT,
            submitted INTEGER DEFAULT 0,
            score REAL,
            weak_topics TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            name TEXT,
            created_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def save_plan(subject: str, exam_date: str, plan_dict: dict) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO plans (subject, exam_date, created_at, plan_json) VALUES (?, ?, ?, ?)",
        (subject, exam_date, datetime.now(timezone.utc).isoformat(), json.dumps(plan_dict)),
    )
    conn.commit()
    conn.close()


def get_plan(subject: str):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT plan_json, exam_date, created_at FROM plans WHERE subject = ?",
        (subject,),
    ).fetchone()
    conn.close()

    if not row:
        return None

    plan_json, exam_date, created_at = row
    return {"plan": json.loads(plan_json), "exam_date": exam_date, "created_at": created_at}


def save_quiz(quiz_id: str, subject: str, quiz_dict: dict) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO quizzes (quiz_id, subject, created_at, quiz_json) VALUES (?, ?, ?, ?)",
        (quiz_id, subject, datetime.now(timezone.utc).isoformat(), json.dumps(quiz_dict)),
    )
    conn.commit()
    conn.close()


def get_quiz(quiz_id: str):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT subject, quiz_json FROM quizzes WHERE quiz_id = ?",
        (quiz_id,),
    ).fetchone()
    conn.close()

    if not row:
        return None

    subject, quiz_json = row
    return {"subject": subject, "quiz": json.loads(quiz_json)}


def save_quiz_result(quiz_id: str, score: float, weak_topics: list) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE quizzes SET submitted = 1, score = ?, weak_topics = ? WHERE quiz_id = ?",
        (score, json.dumps(weak_topics), quiz_id),
    )
    conn.commit()
    conn.close()


def get_weak_topics(subject: str) -> list:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT weak_topics FROM quizzes WHERE subject = ? AND submitted = 1",
        (subject,),
    ).fetchall()
    conn.close()

    topics = set()
    for (weak_topics_json,) in rows:
        if weak_topics_json:
            topics.update(json.loads(weak_topics_json))
    return sorted(topics)


init_db()
def create_user(email: str, password_hash: str, name: str = "") -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO users (email, password_hash, name, created_at) VALUES (?, ?, ?, ?)",
        (email.lower().strip(), password_hash, name, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id


def get_user_by_email(email: str):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, email, password_hash, name FROM users WHERE email = ?",
        (email.lower().strip(),),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "email": row[1], "password_hash": row[2], "name": row[3]}


def get_user_by_id(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT id, email, name FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "email": row[1], "name": row[2]}