import hashlib
import numpy as np
from db.connection import get_connection
from db.embeddings import _embed_text
from utils.logger import get_logger

log = get_logger()

MIN_CHUNK_CHARS = 120


def init_resume_chunks_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS resume_chunks (
            id SERIAL PRIMARY KEY,
            resume_hash TEXT NOT NULL,
            chunk_order INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding_vector bytea NOT NULL
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def _split_into_chunks(resume_text: str) -> list[str]:
    """Split on blank lines (paragraph-style chunks), merging short
    fragments together so no chunk is too tiny to carry meaning alone."""
    raw_paragraphs = [p.strip() for p in resume_text.split("\n\n") if p.strip()]

    chunks = []
    buffer = ""
    for para in raw_paragraphs:
        buffer = f"{buffer}\n\n{para}".strip() if buffer else para
        if len(buffer) >= MIN_CHUNK_CHARS:
            chunks.append(buffer)
            buffer = ""
    if buffer:
        if chunks:
            chunks[-1] = f"{chunks[-1]}\n\n{buffer}"
        else:
            chunks.append(buffer)

    return chunks


def _resume_hash(resume_text: str) -> str:
    return hashlib.sha256(resume_text.encode("utf-8")).hexdigest()


def ensure_resume_chunks_embedded(resume_text: str):
    """Embeds and caches resume chunks — only redoes the work if the
    resume file's content actually changed (hash check), so a normal
    daily run doesn't re-embed anything."""
    if not resume_text.strip():
        return

    current_hash = _resume_hash(resume_text)

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM resume_chunks WHERE resume_hash = %s LIMIT 1", (current_hash,))
    already_embedded = cur.fetchone() is not None

    if already_embedded:
        cur.close()
        conn.close()
        return

    cur.execute("DELETE FROM resume_chunks")
    chunks = _split_into_chunks(resume_text)

    for i, chunk in enumerate(chunks):
        try:
            embedding = _embed_text(chunk)
        except Exception as e:
            log.warning(f"Resume chunk {i} failed to embed — {e} — skipping this chunk")
            continue
        cur.execute("""
            INSERT INTO resume_chunks (resume_hash, chunk_order, chunk_text, embedding_vector)
            VALUES (%s, %s, %s, %s)
        """, (current_hash, i, chunk, np.array(embedding, dtype=np.float32).tobytes()))

    conn.commit()
    cur.close()
    conn.close()
    log.info(f"Resume changed — re-embedded {len(chunks)} chunk(s)")


def get_relevant_resume_excerpt(job_description: str, resume_text: str, top_k: int = 4) -> str:
    """Top_k most relevant resume chunks for this job, stitched back
    together in original resume order. Falls back to the first 2000
    chars of the full resume if anything embedding-related fails —
    never blocks scoring."""
    try:
        ensure_resume_chunks_embedded(resume_text)

        job_embedding = np.array(_embed_text(job_description[:2000]), dtype=np.float32)

        conn = get_connection()
        cur = conn.cursor()
        current_hash = _resume_hash(resume_text)
        cur.execute(
            "SELECT chunk_order, chunk_text, embedding_vector FROM resume_chunks WHERE resume_hash = %s ORDER BY chunk_order",
            (current_hash,)
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if not rows:
            raise RuntimeError("No resume chunks available")

        scored = []
        for order, text, stored_bytes in rows:
            chunk_embedding = np.frombuffer(stored_bytes, dtype=np.float32)
            norm_a = np.linalg.norm(job_embedding)
            norm_b = np.linalg.norm(chunk_embedding)
            similarity = float(np.dot(job_embedding, chunk_embedding) / (norm_a * norm_b)) if norm_a and norm_b else 0.0
            scored.append((order, text, similarity))

        top = sorted(scored, key=lambda x: -x[2])[:top_k]
        top_in_resume_order = sorted(top, key=lambda x: x[0])

        return "\n\n".join(text for _, text, _ in top_in_resume_order)

    except Exception as e:
        log.warning(f"Resume RAG retrieval failed — {e} — falling back to full resume excerpt")
        return resume_text[:2000]