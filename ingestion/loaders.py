"""
Document loaders for the study assistant.
"""

from pathlib import Path
import re


def _strip_repeated_headers(text: str) -> str:
    """
    Many lecture-note PDFs repeat a header/footer (e.g. instructor names) on
    every page, sometimes glued directly onto heading text with no space.
    This pollutes every chunk and hurts retrieval quality, so strip that
    pattern generically: any run of two or more "Prof. Name" segments
    separated by commas.
    """
    cleaned = re.sub(r"(?:Prof\.\s*\w+\s*,\s*){1,}Prof\.\s*\w+", "", text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned


def load_pdf(path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = _strip_repeated_headers(text)
        pages.append(f"[Page {i + 1}]\n{text}")
    return "\n\n".join(pages)


def load_pptx(path: str) -> str:
    from pptx import Presentation

    prs = Presentation(path)
    slides = []
    for i, slide in enumerate(prs.slides):
        lines = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = "".join(run.text for run in para.runs)
                    if text.strip():
                        lines.append(text)
        slides.append(f"[Slide {i + 1}]\n" + "\n".join(lines))
    return "\n\n".join(slides)


def load_docx(path: str) -> str:
    import docx

    doc = docx.Document(path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def load_txt(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")


LOADERS = {
    ".pdf": load_pdf,
    ".pptx": load_pptx,
    ".docx": load_docx,
    ".txt": load_txt,
    ".md": load_txt,
}


def load_document(path: str) -> str:
    """Dispatch to the right loader based on file extension."""
    ext = Path(path).suffix.lower()
    if ext not in LOADERS:
        raise ValueError(
            f"Unsupported file type: {ext}. Supported: {list(LOADERS.keys())}"
        )
    return LOADERS[ext](path)