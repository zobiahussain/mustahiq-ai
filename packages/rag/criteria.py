"""Shared program-document indexing and filtered pgvector retrieval.

No model or LLM participates in eligibility through this module. It serves
on-demand staff reference answers only. The local SQLite demo uses explicit
keyword source lookup; Supabase uses the existing 768-dimensional embedder.
"""
from sqlalchemy import text


def index_passages(db, passages):
    if db.bind.dialect.name != 'postgresql':
        return
    from embeddings import embed_texts
    vectors = embed_texts([p['chunk_text'] for p in passages])
    for passage, vector in zip(passages, vectors):
        db.execute(text('update program_criteria set embedding = cast(:vector as vector) where id = :id'),
                   {'vector': str(vector), 'id': str(passage['id'])})


def retrieve_passages(db, question, program_ids, limit=4):
    if not program_ids:
        return []
    from embeddings import embed_text
    vector = embed_text(question)
    # Department/program access is a WHERE filter before ORDER/LIMIT, not a
    # Python filter after top-k. All identifiers are bound parameters.
    from sqlalchemy import bindparam
    statement = text('''select id, program_id, chunk_text, chunk_index,
                1 - (embedding <=> cast(:vector as vector)) as similarity
            from program_criteria
            where program_id in :program_ids and embedding is not null
            order by embedding <=> cast(:vector as vector) limit :limit''').bindparams(bindparam('program_ids', expanding=True))
    return [dict(r) for r in db.execute(statement, {'vector': str(vector), 'program_ids': program_ids, 'limit': limit}).mappings()]
