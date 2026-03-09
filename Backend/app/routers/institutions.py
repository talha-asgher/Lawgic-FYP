# app/routers/institutions.py
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db

router = APIRouter(
    prefix="/institutions",
    tags=["institutions"],
)


@router.get("/", response_model=List[schemas.LegalInstitutionOut])
def list_institutions(
    inst_type: Optional[str] = None,
    city: Optional[str] = None,
    amenity: Optional[str] = None,
    q: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    query = db.query(models.LegalInstitution)

    if q:
        query = query.filter(models.LegalInstitution.name.ilike(f"%{q}%"))

    if inst_type:
        query = query.filter(
            models.LegalInstitution.type.ilike(f"%{inst_type}%") |
            models.LegalInstitution.amenity.ilike(f"%{inst_type}%") |
            models.LegalInstitution.office.ilike(f"%{inst_type}%")
        )

    if city:
        query = query.filter(
            models.LegalInstitution.city.ilike(f"%{city}%") |
            models.LegalInstitution.address.ilike(f"%{city}%") |
            models.LegalInstitution.jurisdiction.ilike(f"%{city}%")
        )

    if amenity:
        query = query.filter(models.LegalInstitution.amenity.ilike(f"%{amenity}%"))

    return query.offset(skip).limit(limit).all()
