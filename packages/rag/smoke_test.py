"""
Proves the embedding wrapper actually works before anyone builds on top of
it: embed two similar sentences and one unrelated one, confirm the similar
pair scores higher than the unrelated one, confirm the vector length is
exactly 768 (matching the database column).

Run: python smoke_test.py
"""

from embeddings import embed_text, EMBEDDING_DIM


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    # skip norm division -- embeddings are already normalized to length 1
    # (see embeddings.py), so dot product alone IS cosine similarity here.
    return dot


def main():
    tailor = embed_text("Tailoring and stitching shalwar kameez, custom clothing")
    tailor_urdu_expanded = embed_text(
        "Tailoring, stitching shalwar kameez and uniforms, garment production"
    )
    rickshaw = embed_text("Three-wheeler rickshaw transport between districts")

    print(f"vector length: {len(tailor)} (expected {EMBEDDING_DIM})")
    assert len(tailor) == EMBEDDING_DIM, "vector length doesn't match the database column!"

    similar_score = cosine_similarity(tailor, tailor_urdu_expanded)
    different_score = cosine_similarity(tailor, rickshaw)

    print(f"tailor <-> tailor (similar wording):  {similar_score:.4f}")
    print(f"tailor <-> rickshaw (unrelated):       {different_score:.4f}")

    assert similar_score > different_score, "similar text should score higher than unrelated text!"

    print("\nPASS -- embeddings are 768-dim and semantic similarity behaves as expected.")


if __name__ == "__main__":
    main()
