"""
Study Assistant API — now with authentication.

Run:
    uvicorn main:app --reload

Auth:
    POST /auth/register   {email, password, name} -> {token, user}
    POST /auth/login      {email, password}        -> {token, user}
    GET  /auth/me         (Authorization: Bearer <token>) -> current user

All other endpoints below require "Authorization: Bearer <token>" and are
automatically scoped per-user: a subject like "biology" is transparently
turned into "u5_biology" internally, so users never see each other's data.
"""

import shutil
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agents.evaluator import generate_quiz, submit_quiz
from agents.planner import generate_plan
from agents.tutor import answer_question
from auth import create_access_token, get_current_user, hash_password, scoped_subject, verify_password
from db.database import create_user, get_plan, get_user_by_email
from ingestion.pipeline import ingest_file, list_subjects, query_subject

app = FastAPI(title="Study Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path(__file__).resolve().parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------- Auth models
class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class QuizRequest(BaseModel):
    subject: str
    topics: list[str]
    n_questions: int = 5


class QuizSubmission(BaseModel):
    quiz_id: str
    answers: dict[str, str]


# ---------------------------------------------------------------- Auth routes
@app.post("/auth/register")
async def register(req: RegisterRequest):
    if get_user_by_email(req.email):
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    password_hash = hash_password(req.password)
    user_id = create_user(req.email, password_hash, req.name)
    token = create_access_token(user_id, req.email)

    return {"token": token, "user": {"id": user_id, "email": req.email, "name": req.name}}


@app.post("/auth/login")
async def login(req: LoginRequest):
    user = get_user_by_email(req.email)
    if not user or not user["password_hash"] or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(user["id"], user["email"])
    return {"token": token, "user": {"id": user["id"], "email": user["email"], "name": user["name"]}}


@app.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return {"user": user}


# ---------------------------------------------------------------- Protected routes
@app.post("/upload")
async def upload(
    subject: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    dest = UPLOAD_DIR / file.filename
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        num_chunks = ingest_file(str(dest), subject=scoped_subject(subject, user))
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    return {"filename": file.filename, "subject": subject, "chunks_added": num_chunks}


@app.get("/query")
async def query(subject: str, question: str, n_results: int = 5, user: dict = Depends(get_current_user)):
    results = query_subject(scoped_subject(subject, user), question, n_results=n_results)
    return {"subject": subject, "question": question, "results": results}


@app.get("/ask")
async def ask(subject: str, question: str, user: dict = Depends(get_current_user)):
    result = answer_question(scoped_subject(subject, user), question)
    return result


@app.post("/plan")
async def create_plan(subject: str, exam_date: str, user: dict = Depends(get_current_user)):
    """exam_date format: YYYY-MM-DD"""
    result = generate_plan(scoped_subject(subject, user), exam_date)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result


@app.get("/plan/{subject}")
async def fetch_plan(subject: str, user: dict = Depends(get_current_user)):
    result = get_plan(scoped_subject(subject, user))
    if not result:
        return JSONResponse(status_code=404, content={"error": f"No plan found for subject '{subject}'"})
    return result


@app.post("/quiz/generate")
async def create_quiz(req: QuizRequest, user: dict = Depends(get_current_user)):
    result = generate_quiz(scoped_subject(req.subject, user), req.topics, req.n_questions)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result


@app.post("/quiz/submit")
async def submit_quiz_endpoint(req: QuizSubmission, user: dict = Depends(get_current_user)):
    # quiz_id already uniquely identifies the quiz (created under this
    # user's scoped subject), so no extra scoping needed here.
    result = submit_quiz(req.quiz_id, req.answers)
    if "error" in result:
        return JSONResponse(status_code=404, content=result)
    return result


@app.get("/subjects")
async def subjects(user: dict = Depends(get_current_user)):
    prefix = f"u{user['id']}_"
    mine = [s[len(prefix):] for s in list_subjects() if s.startswith(prefix)]
    return {"subjects": mine}


@app.get("/")
async def health():
    return {"status": "ok"}