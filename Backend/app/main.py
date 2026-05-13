# app/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import engine, Base
from app import models
from app.deps import get_db
from app.schema_migrations import ensure_doc_analysis_columns
from app.routers import (
    auth,
    lawyers,
    institutions,
    appointments,
    users,
    cases,
    case_messages,
    conversations,
    reviews,
    documents,
    ai_qa,
)
from app.routers.documents import analysis_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Lawgic API",
    description="AI-powered legal platform for Pakistan",
    version="1.0.0",
)

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(lawyers.router)
app.include_router(reviews.router)
app.include_router(cases.router)
app.include_router(case_messages.router)
app.include_router(conversations.router)
app.include_router(appointments.router)
app.include_router(institutions.router)
app.include_router(documents.router)
app.include_router(analysis_router)
app.include_router(ai_qa.router)


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    return {"status": "ok", "db": "connected"}
