"""
Streamlit UI for the Study Assistant.

Run this in a SEPARATE terminal from your FastAPI backend:
    streamlit run app.py

Requires the backend (uvicorn main:app --reload) to already be running
on http://127.0.0.1:8000 — this file is just a frontend that calls it.
"""

import requests
import streamlit as st

BASE_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Study Assistant", page_icon="📚", layout="wide")
st.title("📚 Agentic Study Assistant")

if "subject" not in st.session_state:
    st.session_state.subject = ""
if "quiz" not in st.session_state:
    st.session_state.quiz = None
if "quiz_id" not in st.session_state:
    st.session_state.quiz_id = None

st.session_state.subject = st.text_input(
    "Subject name (use the same one across Upload / Ask / Plan / Quiz)",
    value=st.session_state.subject,
    placeholder="e.g. prompt-engineering",
)
subject = st.session_state.subject.strip()

tab_upload, tab_ask, tab_plan, tab_quiz = st.tabs(["📤 Upload", "💬 Ask", "🗓️ Study Plan", "📝 Quiz"])

with tab_upload:
    st.subheader("Upload study material")
    uploaded_file = st.file_uploader("Choose a PDF, PPTX, DOCX, or TXT file", type=["pdf", "pptx", "docx", "txt"])

    if st.button("Upload & Ingest", type="primary", disabled=not (subject and uploaded_file)):
        with st.spinner("Uploading and processing..."):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
            data = {"subject": subject}
            try:
                resp = requests.post(f"{BASE_URL}/upload", files=files, data=data, timeout=120)
                resp.raise_for_status()
                result = resp.json()
                st.success(f"Ingested {result['filename']} — {result['chunks_added']} chunks added to '{subject}'")
            except requests.RequestException as e:
                st.error(f"Upload failed: {e}")

    if subject:
        try:
            subs = requests.get(f"{BASE_URL}/subjects", timeout=10).json().get("subjects", [])
            st.caption(f"Subjects currently ingested: {', '.join(subs) if subs else 'none yet'}")
        except requests.RequestException:
            st.caption("Could not reach backend to list subjects.")

with tab_ask:
    st.subheader("Ask a question about your notes")
    question = st.text_input("Your question", placeholder="e.g. what are the types of prompts?")

    if st.button("Ask", type="primary", disabled=not (subject and question)):
        with st.spinner("Thinking..."):
            try:
                resp = requests.get(f"{BASE_URL}/ask", params={"subject": subject, "question": question}, timeout=60)
                resp.raise_for_status()
                result = resp.json()
                st.markdown(result["answer"])
                if result.get("sources"):
                    with st.expander("Sources"):
                        for s in result["sources"]:
                            st.caption(f"{s['source']} (chunk {s['chunk_index']})")
            except requests.RequestException as e:
                st.error(f"Request failed: {e}")

with tab_plan:
    st.subheader("Generate or view your study plan")
    col1, col2 = st.columns([2, 1])
    with col1:
        exam_date = st.date_input("Exam date")
    with col2:
        st.write("")
        st.write("")
        generate_clicked = st.button("Generate / Re-plan", type="primary", disabled=not subject)

    if generate_clicked:
        with st.spinner("Building your study plan... this can take a bit"):
            try:
                resp = requests.post(
                    f"{BASE_URL}/plan",
                    params={"subject": subject, "exam_date": exam_date.isoformat()},
                    timeout=120,
                )
                resp.raise_for_status()
                st.session_state.last_plan = resp.json()
                st.success("Plan generated.")
            except requests.RequestException as e:
                st.error(f"Failed to generate plan: {e}")

    if st.button("Load saved plan", disabled=not subject):
        try:
            resp = requests.get(f"{BASE_URL}/plan/{subject}", timeout=10)
            if resp.status_code == 404:
                st.warning("No saved plan yet for this subject.")
            else:
                resp.raise_for_status()
                st.session_state.last_plan = resp.json()["plan"]
        except requests.RequestException as e:
            st.error(f"Failed to load plan: {e}")

    plan_data = st.session_state.get("last_plan")
    if plan_data:
        st.markdown("**Topics covered:** " + ", ".join(plan_data.get("topics", [])))
        for day in plan_data.get("plan", []):
            with st.expander(f"Day {day['day']} — {day.get('date', '')} — {day.get('focus', '')}"):
                for t in day.get("topics", []):
                    st.markdown(f"- {t}")

with tab_quiz:
    st.subheader("Test yourself")
    topics_input = st.text_input("Topics to quiz on (comma-separated)", placeholder="e.g. types of prompts")
    n_questions = st.slider("Number of questions", 1, 10, 5)

    if st.button("Generate Quiz", type="primary", disabled=not (subject and topics_input)):
        topics = [t.strip() for t in topics_input.split(",") if t.strip()]
        with st.spinner("Writing your quiz..."):
            try:
                resp = requests.post(
                    f"{BASE_URL}/quiz/generate",
                    json={"subject": subject, "topics": topics, "n_questions": n_questions},
                    timeout=120,
                )
                resp.raise_for_status()
                result = resp.json()
                if "error" in result:
                    st.error(result["error"])
                else:
                    st.session_state.quiz = result["questions"]
                    st.session_state.quiz_id = result["quiz_id"]
            except requests.RequestException as e:
                st.error(f"Failed to generate quiz: {e}")

    if st.session_state.quiz:
        st.markdown("---")
        answers = {}
        for q in st.session_state.quiz:
            st.markdown(f"**{q['question']}**")
            option_keys = list(q["options"].keys())
            choice = st.radio(
                "Select an answer",
                option_keys,
                format_func=lambda k, opts=q["options"]: f"{k}) {opts[k]}",
                key=f"q_{q['id']}",
                label_visibility="collapsed",
            )
            answers[q["id"]] = choice
            st.markdown("")

        if st.button("Submit Quiz", type="primary"):
            with st.spinner("Scoring..."):
                try:
                    resp = requests.post(
                        f"{BASE_URL}/quiz/submit",
                        json={"quiz_id": st.session_state.quiz_id, "answers": answers},
                        timeout=30,
                    )
                    resp.raise_for_status()
                    result = resp.json()
                    st.metric("Score", f"{result['correct']} / {result['total']}")
                    if result.get("weak_topics"):
                        st.warning(f"Weak topics flagged for revision: {', '.join(result['weak_topics'])}")
                    else:
                        st.success("No weak topics — nice work!")
                    for r in result["results"]:
                        icon = "✅" if r["correct"] else "❌"
                        st.markdown(f"{icon} **{r['topic']}** — correct answer: `{r['correct_option']}`")
                        st.caption(r["explanation"])
                except requests.RequestException as e:
                    st.error(f"Submission failed: {e}")