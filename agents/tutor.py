"""
Tutor agent: turns retrieved chunks into a complete, grounded answer,
strictly scoped to the ingested notes for a subject.
"""

import os

from groq import Groq
from dotenv import load_dotenv
from streamlit import context
from ingestion.pipeline import keyword_search, query_subject

load_dotenv()

_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

MODEL = "openai/gpt-oss-20b"

SYSTEM_PROMPT = (
    "You are a study tutor scoped strictly to the student's uploaded notes for "
    "this module. Answer using ONLY the provided source material below — do not "
    "add facts, context, or explanations from your own general knowledge, even "
    "if you know more about the topic than the notes contain. If the source "
    "material only partially covers the question, answer the covered part and "
    "explicitly say what's missing rather than filling the gap yourself. Keep "
    "the answer clear and complete — don't cut off mid-thought. "
    "Write the answer as clean, standalone text for the student: do NOT include "
    "inline citations, chunk numbers, page numbers, or filenames anywhere in "
    "your answer (e.g. never write things like 'Source: chunk 17' or "
    "'(Chunk 4, Page 3)'). Sources are tracked separately by the system — your "
    "job is just to write the answer itself."
)
RELEVANCE_THRESHOLD = 0.8
MAX_CONTEXT_CHARS = 6000



def answer_question(subject: str, question: str, n_chunks: int = 8) -> dict:
    relevant_chunks = keyword_search(subject, question)

    if not relevant_chunks:
        chunks = query_subject(subject, question, n_results=n_chunks)

        if not chunks:
            return {
                "answer": (
                    f"No material has been ingested yet for subject '{subject}', "
                    "so I can't answer this from your notes. Upload some material first."
                ),
                "sources": [],
            }

        relevant_chunks = [c for c in chunks if c.get("distance") is None or c["distance"] <= RELEVANCE_THRESHOLD]

    if not relevant_chunks:
        return {
            "answer": (
                "This doesn't appear to be covered in the notes uploaded for this "
                "module, so I won't guess at an answer. Try rephrasing, or ask "
                "something closer to what's in your material."
            ),
            "sources": [],
        }

    context = "\n\n".join(
        f"[Source: {c['source']}, chunk {c['chunk_index']}]\n{c['text']}" for c in relevant_chunks
    )[:MAX_CONTEXT_CHARS]
    
    user_message = (
        f"Source material:\n\n{context}\n\n"
        f"Question: {question}\n\n"
        "Give a complete answer based on the source material above."
    )

    response = _client.chat.completions.create(
        model=MODEL,
        max_tokens=1500,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )

    answer_text = response.choices[0].message.content

    return {
        "answer": answer_text,
        "sources": [{"source": c["source"], "chunk_index": c["chunk_index"]} for c in relevant_chunks],
    }