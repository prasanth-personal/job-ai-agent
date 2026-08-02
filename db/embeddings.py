import numpy as np
import os
from db.connection import get_connection
from db.repository import make_job_key
from utils.logger import get_logger

log = get_logger()

GOOGLE_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")

SIMILARITY_THRESHOLD = 0.92

_initialized = False


def _init_vertex():
    """Lazy-init — only runs when an embedding is actually needed, not
    at import time. This means a missing/misconfigured credentials file
    won't crash the whole pipeline at startup."""
    global _initialized
    if _initialized:
        return
    from google.oauth2 import service_account
    import vertexai

    credentials = service_account.Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH)
    vertexai.init(project=GOOGLE_PROJECT_ID, credentials=credentials, location="us-central1")
    _initialized = True


def init_embeddings_table():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS job_embeddings (
            job_key TEXT PRIMARY KEY,
            job_title TEXT,
            employer_name TEXT,
            embedding_text TEXT,
            embedding_vector bytea,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def _embed_text(text: str) -> np.ndarray:
    _init_vertex()
    from vertexai.language_models import TextEmbeddingModel

    model = TextEmbeddingModel.from_pretrained("textembedding-gecko@003")
    embeddings = model.get_embeddings([text])
    return np.array(embeddings[0].values, dtype=np.float32)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def is_semantic_duplicate(employer_name: str, job_title: str, job_description: str) -> bool:
    """Checks if this job is a semantic duplicate. Fails safe: any error
    (missing credentials, network issue, etc.) treats the job as NOT a
    duplicate rather than blocking the pipeline."""
    key = make_job_key(employer_name, job_title)
    embedding_text = f"{job_title} {job_description[:200]}".strip()

    try:
        new_embedding = _embed_text(embedding_text)
    except Exception as e:
        log.warning(f"Embedding call failed for '{job_title}' — {e} — skipping semantic check, keeping job")
        return False

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT job_key, embedding_vector FROM job_embeddings")
    rows = cur.fetchall()

    for existing_key, stored_bytes in rows:
        if existing_key == key:
            cur.close()
            conn.close()
            return True

        existing_embedding = np.frombuffer(stored_bytes, dtype=np.float32)
        similarity = _cosine_similarity(new_embedding, existing_embedding)

        if similarity > SIMILARITY_THRESHOLD:
            log.info(f"Semantic duplicate: '{job_title}' @ '{employer_name}' (similarity: {similarity:.3f}) — skipping")
            cur.close()
            conn.close()
            return True

    cur.execute("""
        INSERT INTO job_embeddings (job_key, job_title, employer_name, embedding_text, embedding_vector)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (job_key) DO NOTHING
    """, (key, job_title, employer_name, embedding_text, new_embedding.tobytes()))
    conn.commit()
    cur.close()
    conn.close()

    return False