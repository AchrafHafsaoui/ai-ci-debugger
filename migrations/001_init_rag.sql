-- Enable the pgvector extension to work with embeddings
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS failure_history (
    id SERIAL PRIMARY KEY,
    repo_name TEXT NOT NULL,
    error_snippet TEXT NOT NULL,
    ai_diagnosis TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    -- 384 is standard for Sentence Transformers embeddings
    embedding VECTOR(384), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);