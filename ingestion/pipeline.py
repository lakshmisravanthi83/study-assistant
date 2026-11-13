"""
Ingestion pipeline: file -> text -> chunks -> vector store.

Usage:
    from ingestion.pipeline import ingest_file, query_subject

    ingest_file("data/uploads/os_unit1.pdf", subject="operating-systems")
    results = query_subject("operating-systems", "what is a semaphore?")
"""

from pathlib import Path

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ingestion.loaders import load_document

import re

CHROMA_PATH = str(Path(__file__).resolve().parent.parent / "vectorstore" / "chroma")

_client = chromadb.PersistentClient(path=CHROMA_PATH)

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def _collection_for(subject: str):
    # One Chroma collection per subject keeps retrieval scoped and simple to reset.
    safe_name = subject.strip().lower().replace(" ", "-")
    return _client.get_or_create_collection(name=f"subject-{safe_name}")

MIN_CHUNK_CHARS = 200


def _merge_small_chunks(chunks: list[str], min_size: int = MIN_CHUNK_CHARS) -> list[str]:
    """
    RecursiveCharacterTextSplitter can leave tiny orphan chunks right at
    section/page boundaries (e.g. a one-line intro sentence split apart
    from the list it introduces). Merge anything under `min_size` into
    the next chunk so short lead-ins stay attached to their content.
    """
    merged = []
    buffer = ""
    for chunk in chunks:
        buffer = f"{buffer}\n\n{chunk}" if buffer else chunk
        if len(buffer) >= min_size:
            merged.append(buffer)
            buffer = ""
    if buffer:
        if merged:
            merged[-1] = f"{merged[-1]}\n\n{buffer}"
        else:
            merged.append(buffer)
    return merged

def ingest_file(file_path: str, subject: str) -> int:
    """
    Parse a file, chunk it, and add it to the subject's vector collection.
    Returns the number of chunks added.
    """
    text = load_document(file_path)
    if not text.strip():
        raise ValueError(f"No extractable text found in {file_path}")

    chunks = _splitter.split_text(text)
    chunks = _merge_small_chunks(chunks)
    collection = _collection_for(subject)

    file_stem = Path(file_path).stem
    ids = [f"{file_stem}-{i}" for i in range(len(chunks))]
    metadatas = [{"source": Path(file_path).name, "chunk_index": i} for i in range(len(chunks))]

    collection.add(documents=chunks, ids=ids, metadatas=metadatas)
    return len(chunks)


def query_subject(subject: str, question: str, n_results: int = 5):
    """
    Retrieve the most relevant chunks for a question within one subject.
    Returns a list of {text, source, chunk_index, distance} dicts.
    Lower distance = more relevant (Chroma default is cosine distance).
    """
    collection = _collection_for(subject)
    results = collection.query(query_texts=[question], n_results=n_results)

    out = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    for doc, meta, dist in zip(docs, metas, distances):
        out.append({
            "text": doc,
            "source": meta.get("source"),
            "chunk_index": meta.get("chunk_index"),
            "distance": dist,
        })
    return out


def list_subjects():
    return [c.name.replace("subject-", "", 1) for c in _client.list_collections()]
def get_all_chunks(subject: str):
    """Return every ingested chunk for a subject (not just top-k retrieval)."""
    collection = _collection_for(subject)
    results = collection.get()
    docs = results.get("documents", [])
    metas = results.get("metadatas", [])
    return [
        {"text": d, "source": m.get("source"), "chunk_index": m.get("chunk_index")}
        for d, m in zip(docs, metas)
    ]
import re  # add this near your other imports at the top

STOPWORDS = {
    "of", "the", "a", "an", "and", "or", "in", "on", "for", "to", "with", "is", "are",
    "what", "how", "why", "which", "who", "when", "where", "does", "do", "did",
    "can", "could", "would", "should", "will", "tell", "me", "about", "explain",
    "describe", "list", "give", "show", "please",
}
from spellchecker import SpellChecker

_spellcheckers = {}


def _spellchecker_for(subject: str) -> SpellChecker:
    if subject not in _spellcheckers:
        sc = SpellChecker(language=None)
        vocabulary = " ".join(c["text"] for c in get_all_chunks(subject))
        if vocabulary.strip():
            sc.word_frequency.load_text(vocabulary)
        _spellcheckers[subject] = sc
    return _spellcheckers[subject]


def correct_spelling(subject: str, phrase: str) -> str:
    sc = _spellchecker_for(subject)
    words = phrase.split()
    corrected_words = []
    for w in words:
        bare = re.sub(r"[^a-zA-Z]", "", w).lower()
        if bare and bare in sc.unknown([bare]):
            correction = sc.correction(bare)
            if correction:
                corrected_words.append(correction)
                continue
        corrected_words.append(w)
    return " ".join(corrected_words)


def _keywords(phrase: str) -> list:
    words = re.findall(r"[a-zA-Z]+", phrase.lower())
    return [w for w in words if w not in STOPWORDS]

def _normalize_hyphens(text): return re.sub(r"(?<=[a-zA-Z])-(?=[a-zA-Z])", "", text)

def _keywords(phrase: str) -> list:
   words = re.findall(r"[a-zA-Z]+", _normalize_hyphens(phrase).lower())
   return [w for w in words if w not in STOPWORDS]


def _stem(word: str, length: int = 6) -> str:
    return word[:length]


def keyword_search(subject: str, phrase: str, window: int = 8, stem_len: int = 6) -> list:
    keywords = _keywords(correct_spelling(subject, phrase))
    if not keywords:
        return []
    target_stems = {_stem(k, stem_len) for k in keywords}

    all_chunks = get_all_chunks(subject)
    by_source = {}
    for c in all_chunks:
        by_source.setdefault(c["source"], []).append(c)
    for src in by_source:
        by_source[src].sort(key=lambda c: c["chunk_index"])

    matched_indices = {}
    for src, chunks in by_source.items():
        matched_indices[src] = set()
        for i, c in enumerate(chunks):
            chunk_words = re.findall(r"[a-zA-Z]+", _normalize_hyphens(c["text"]).lower())
            chunk_stems = {_stem(w, stem_len) for w in chunk_words}
            if target_stems.issubset(chunk_stems):
                for j in range(i, min(i + 1 + window, len(chunks))):
                    matched_indices[src].add(chunks[j]["chunk_index"])

    result = []
    for src, chunks in by_source.items():
        for c in chunks:
            if c["chunk_index"] in matched_indices[src]:
                result.append(c)
    return result