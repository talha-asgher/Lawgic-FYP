# Lawgic Agent Instructions

## Project Overview
Lawgic is a legal-tech FYP for Pakistan. It uses:
- Frontend: Next.js
- Backend: FastAPI
- Database: PostgreSQL with pgvector
- RAG: BGE-M3 embeddings, BM25/hybrid retrieval, reranking, and Ollama-based local LLM responses

## Important Folders
- frontend/ or client/: Next.js frontend
- backend/ or server/: FastAPI backend
- RAG/: retrieval, embeddings, chunk loading, evaluation, and database scripts
- scripts/: utility scripts
- docs/ or report/: documentation if present

## Rules
- Do not modify `.env` files.
- Do not expose API keys, database URLs, JWT secrets, Supabase credentials, or Ollama endpoints.
- Do not delete datasets, embeddings, migrations, or database scripts unless explicitly asked.
- Make small, reviewable changes.
- Prefer simple code over over-engineered solutions.
- Avoid unnecessary comments unless they explain non-obvious logic.
- Before large changes, explain the plan first.
- After changes, mention exactly which files were edited.

## Backend Commands
Use the existing virtual environment if available.

Common commands:
```bash
pip install -r requirements.txt
uvicorn main:app --reload
pytest