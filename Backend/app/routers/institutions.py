# app/routers/institutions.py
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db

router = APIRouter(
    prefix="/institutions",
    tags=["institutions"],
)


@router.get("/", response_model=List[schemas.LegalInstitutionOut])
def list_institutions(db: Session = Depends(get_db)):

    return db.query(models.LegalInstitution).all()
