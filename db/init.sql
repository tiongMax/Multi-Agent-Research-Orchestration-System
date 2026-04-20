CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS research_memory (
    id          SERIAL PRIMARY KEY,
    query       TEXT NOT NULL,
    sub_questions TEXT[],
    facts       TEXT[],
    report      TEXT,
    embedding   vector(768),
    created_at  TIMESTAMP DEFAULT NOW()
);

-- ivfflat index for approximate nearest-neighbour search
CREATE INDEX IF NOT EXISTS research_memory_embedding_idx
    ON research_memory
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
