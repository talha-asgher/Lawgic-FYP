# app/main.py
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import engine, Base
from app import models
from app.deps import get_db
from app.routers import auth, lawyers, institutions, appointments, users, cases

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Lawgic Backend")

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
)

app.include_router(auth.router)
app.include_router(lawyers.router) 
app.include_router(institutions.router)
app.include_router(appointments.router)
app.include_router(users.router)
app.include_router(cases.router)


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    return {"status": "ok", "db": "connected"}
