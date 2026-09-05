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

import os
from pathlib import Path

MODEL_NAME = "BAAI/bge-base-en-v1.5"
EMBEDDING_DIM = 768


def _model_is_cached(repo_id: str) -> bool:
    """
    True if this model's files are already sitting in the local Hugging Face
    cache. Pure filesystem check -- no imports, no network -- so it's safe to
    call before `sentence_transformers` is imported below.

    HF stores every model under `<cache>/hub/models--<org>--<name>/snapshots/`.
    The cache root is HF_HUB_CACHE, else HF_HOME/hub, else ~/.cache/huggingface/hub
    (same precedence huggingface_hub itself uses).
    """
    cache_root = os.environ.get("HF_HUB_CACHE")
    if not cache_root:
        hf_home = os.environ.get("HF_HOME") or str(Path.home() / ".cache" / "huggingface")
        cache_root = os.path.join(hf_home, "hub")
    snapshots = Path(cache_root) / f"models--{repo_id.replace('/', '--')}" / "snapshots"
    return snapshots.is_dir() and any(snapshots.iterdir())


# WHY HF_HUB_OFFLINE HAS TO BE SET BEFORE THE sentence_transformers IMPORT
# --------------------------------------------------------------------
# "Vector search felt slow" turned out to mostly be this, not the actual
# search: every time a fresh process calls SentenceTransformer(MODEL_NAME)
# for the first time, huggingface_hub -- underneath sentence-transformers
# -- makes a real network call (a HEAD request) to check whether a newer
# version of the model exists on the Hub, EVEN THOUGH the model is
# already fully downloaded and cached locally. That network round-trip is
# what was slow, and on one flaky connection it's also what produced the
# WinError 10054 we hit earlier. HF_HUB_OFFLINE=1 tells huggingface_hub to
# never touch the network at all -- use the local cache or fail loudly, no
# freshness check. It has to be an environment variable set BEFORE
# `from sentence_transformers import SentenceTransformer` runs, because
# huggingface_hub reads it once at import time, not per-call.
#
# BUT: forcing offline mode only works once the model is actually cached.
# On a brand-new machine the cache is empty, so we leave the network ON for
# that first run to let the ~420MB download happen, and only switch to the
# fast offline path once _model_is_cached() confirms it's there. Every run
# after the first download gets the offline path automatically -- no manual
# "unset HF_HUB_OFFLINE for one run" step, which the old setup docs missed.
# An explicit HF_HUB_OFFLINE in the environment always wins (setdefault).
if _model_is_cached(MODEL_NAME):
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
else:
    print(
        f"[embeddings] {MODEL_NAME} is not in the local Hugging Face cache -- "
        "this first run will download it (~420MB) from huggingface.co. "
        "Every run after this one loads it offline from the cache."
    )

from sentence_transformers import SentenceTransformer  # noqa: E402

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
