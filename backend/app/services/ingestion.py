from app.models.document import Document
from app.services.embeddings.base import Embedder
from app.services.vectorstore.base import VectorChunk


def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> list[str]:
    """Character-based sliding window. Works for Chinese text (no word
    boundaries needed) and is plenty for the short demo documents in scope."""
    cleaned = text.strip()
    if len(cleaned) <= chunk_size:
        return [cleaned]

    chunks = []
    start = 0
    n = len(cleaned)
    while start < n:
        end = min(start + chunk_size, n)
        chunks.append(cleaned[start:end])
        if end == n:
            break
        start = end - overlap
    return chunks


def chunk_document(text: str, max_chars: int = 800, title: str = "") -> list[str]:
    """Paragraph-aware chunking for real library files: packs whole lines into
    chunks of up to max_chars (an oversized single line is window-split), and
    prefixes every chunk with the document title so a chunk that is a slice of
    a table/spreadsheet is still self-describing for retrieval and citation."""
    prefix = f"[{title}]\n" if title else ""
    pieces: list[str] = []
    cur = ""
    for line in (ln.strip() for ln in text.splitlines()):
        if not line:
            continue
        for part in ([line] if len(line) <= max_chars else chunk_text(line, max_chars, 100)):
            if cur and len(cur) + len(part) + 1 > max_chars:
                pieces.append(cur)
                cur = ""
            cur = f"{cur}\n{part}" if cur else part
    if cur:
        pieces.append(cur)
    return [prefix + p for p in pieces] or [prefix.strip()]


TEXT_CHUNK_CHARS = 800
TABLE_CHUNK_CHARS = 1500  # spreadsheet rows are short and related; keep more of a table together
MIN_SECTION_CHARS = 300  # don't cut a prose chunk at a section boundary before this size


def chunk_structured(
    lines: list[tuple[str, str]],
    title: str = "",
    department: str = "",
    table: bool = False,
) -> list[str]:
    """Section-aware chunking over parse_structured() output.

    Packs whole lines up to a size limit, but starts a new chunk when the
    section (heading / slide / sheet) changes - always for tables, and for
    prose once the current chunk is big enough. Every chunk is prefixed with
    "[title | department | section]" (section = where the chunk starts), so
    a slice of a sheet or a deep subsection is still self-describing for
    retrieval, and for the citation shown to the user."""
    limit = TABLE_CHUNK_CHARS if table else TEXT_CHUNK_CHARS
    chunks: list[tuple[str, str]] = []  # (section_at_start, body)
    cur, cur_section, last_section = "", "", None

    def flush():
        nonlocal cur
        if cur:
            chunks.append((cur_section, cur))
            cur = ""

    for text, section in lines:
        text = text.strip()
        if not text:
            continue
        if cur and section != last_section and (table or len(cur) >= MIN_SECTION_CHARS):
            flush()
        last_section = section
        for part in [text] if len(text) <= limit else chunk_text(text, limit, 100):
            if cur and len(cur) + len(part) + 1 > limit:
                flush()
            if not cur:
                cur_section = section
            cur = f"{cur}\n{part}" if cur else part
    flush()

    def prefix(section: str) -> str:
        label = " | ".join(x for x in (title, department, section) if x)
        return f"[{label}]\n" if label else ""

    return [prefix(sec) + body for sec, body in chunks]


def build_chunks_from_lines(
    document: Document,
    lines: list[tuple[str, str]],
    embedder: Embedder,
    title: str = "",
    department: str = "",
    table: bool = False,
) -> list[VectorChunk]:
    pieces = chunk_structured(lines, title=title, department=department, table=table)
    vectors = embedder.embed_texts(pieces)
    return [
        VectorChunk(
            chunk_id=f"{document.id}::chunk{i}",
            doc_id=document.id,
            text=piece,
            vector=vector,
            allowed_roles=document.allowed_roles,
            required_clearance=document.required_clearance,
            compartments=document.compartments,
            version=document.version or "v1",
            status=document.status or "active",
        )
        for i, (piece, vector) in enumerate(zip(pieces, vectors))
    ]


def build_chunks_for_document(
    document: Document, raw_text: str, embedder: Embedder, title: str | None = None
) -> list[VectorChunk]:
    pieces = chunk_document(raw_text, title=title) if title is not None else chunk_text(raw_text)
    vectors = embedder.embed_texts(pieces)
    return [
        VectorChunk(
            chunk_id=f"{document.id}::chunk{i}",
            doc_id=document.id,
            text=piece,
            vector=vector,
            allowed_roles=document.allowed_roles,
            required_clearance=document.required_clearance,
            compartments=document.compartments,
            version=document.version or "v1",
            status=document.status or "active",
        )
        for i, (piece, vector) in enumerate(zip(pieces, vectors))
    ]
