"""
Local text embeddings for the Mustahiq AI marketplace + eligibility RAG layer.

WHAT THIS IS
------------
An embedding turns a piece of text into a list of numbers (a "vector") such
that texts with similar MEANING end up with similar numbers. Postgres (via
the pgvector extension) can then find "the closest meaning to this one" by
comparing number-lists directly in SQL -- that's the whole trick behind
semantic search and matching in this project.

WHY LOCAL, NOT AN API
----------------------
Groq (our LLM provider) has no embeddings endpoint -- confirmed directly
against their API reference. Running the model ourselves, on CPU, costs
nothing per call and never touches Groq's rate limit. See CLAUDE.md
"Needs reconciling" history for the full reasoning.

WHY THIS EXACT MODEL AND SIZE
-------------------------------
BAAI/bge-base-en-v1.5 outputs vectors of exactly 768 numbers. That has to
match the database column type EXACTLY -- the schema
(packages/data/schema/*.sql) declares every embedding column as
`vector(768)`, a fixed-size slot. A 384-number vector simply will not fit
in a 768-number column. Confirmed with the team 1 Sep 2026 -- see CLAUDE.md
"Resolved".

THE LAZY SINGLETON PATTERN
----------------------------
The model itself is a ~420MB file that takes real time to load into memory.
If we reloaded it inside embed_text() on every call, every single call
would pay that cost -- unusable. Instead we load it exactly ONCE, the
first time it's actually needed (lazy), and keep that one loaded copy
around for every call after that (singleton). This is also the mitigation
for the Render free-tier memory watch item flagged in CLAUDE.md: the model
only ever occupies memory once it's actually used, not at process startup.
"""

from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-base-en-v1.5"
EMBEDDING_DIM = 768

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Load the model on first use only, then reuse the same instance forever."""
    global _model
    if _model is None:
        print(f"[embeddings] loading {MODEL_NAME} (first call only, this takes a moment)...")
        _model = SentenceTransformer(MODEL_NAME)
        print("[embeddings] model loaded, ready.")
    return _model


def embed_text(text: str) -> list[float]:
    """
    Turn one piece of text into a 768-number vector.

    This is the ONLY function most callers need. It always returns a plain
    Python list of floats (not a numpy array) because that's what gets
    handed straight to pgvector in an INSERT/SELECT.
    """
    if not text or not text.strip():
        raise ValueError("embed_text() got empty text -- nothing meaningful to embed")

    # normalize_embeddings=True scales every vector to length 1 before
    # returning it. Reason: pgvector's cosine-distance operator (<=>) works
    # correctly either way, but this specific model (BGE) was TRAINED
    # assuming normalized vectors -- skipping this step doesn't break
    # anything visibly, it just quietly makes every similarity score worse.
    model = _get_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Same idea, but for many texts at once -- batching is meaningfully faster
    than calling embed_text() in a loop, since the model processes them
    together instead of one at a time.
    """
    if not texts:
        return []

    model = _get_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return vectors.tolist()
