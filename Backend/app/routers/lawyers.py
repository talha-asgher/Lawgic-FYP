# app/routers/lawyers.py
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db
from app.routers.auth import get_current_user  # re-use auth dependency

router = APIRouter(
    prefix="/lawyers",
    tags=["lawyers"],
)


def ensure_lawyer_role(user: models.User):
    if user.role != "lawyer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only users with role 'lawyer' can access this resource",
        )


@router.post("/profile", response_model=schemas.LawyerProfileOut)
def create_or_update_profile(
    profile_in: schemas.LawyerProfileCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Create or update the logged-in lawyer's profile.
    """
    ensure_lawyer_role(current_user)

    # Does this lawyer already have a profile?
    profile = (
        db.query(models.LawyerProfile)
        .filter(models.LawyerProfile.lawyer_id == current_user.user_id)
        .first()
    )

    if profile is None:
        # Create new profile
        profile = models.LawyerProfile(
            lawyer_id=current_user.user_id,
            specialization=profile_in.specialization,
            bio_data=profile_in.bio_data,
            verification_status=profile_in.verification_status,
            years_of_experience=profile_in.years_of_experience,
            office_address=profile_in.office_address,
            consultation_fee=profile_in.consultation_fee,
        )
        db.add(profile)
    else:
        # Update existing
        profile.specialization = profile_in.specialization
        profile.bio_data = profile_in.bio_data
        profile.verification_status = profile_in.verification_status
        profile.years_of_experience = profile_in.years_of_experience
        profile.office_address = profile_in.office_address
        profile.consultation_fee = profile_in.consultation_fee

    db.commit()
    db.refresh(profile)
    return profile


@router.get("/me", response_model=schemas.LawyerProfileOut)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Get the current lawyer's profile.
    """
    ensure_lawyer_role(current_user)

    profile = (
        db.query(models.LawyerProfile)
        .filter(models.LawyerProfile.lawyer_id == current_user.user_id)
        .first()
    )
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found. Create one using POST /lawyers/profile.",
        )
    return profile


@router.get("/search", response_model=List[schemas.LawyerPublic])
def search_lawyers(
    specialization: Optional[str] = None,
    min_experience: Optional[int] = None,
    max_fee: Optional[float] = None,
    db: Session = Depends(get_db),
):
    """
    Public search endpoint for lawyers.

    All filters are optional:
    - specialization: exact match on specialization text
    - min_experience: minimum years_of_experience
    - max_fee: maximum consultation_fee
    """
    query = db.query(models.LawyerProfile).join(models.User)

    if specialization:
        query = query.filter(models.LawyerProfile.specialization == specialization)

    if min_experience is not None:
        query = query.filter(
            models.LawyerProfile.years_of_experience >= min_experience
        )

    if max_fee is not None:
        query = query.filter(models.LawyerProfile.consultation_fee <= max_fee)

    profiles = query.all()

    # Map to LawyerPublic with user.name included
    result: List[schemas.LawyerPublic] = []
    for p in profiles:
        result.append(
            schemas.LawyerPublic(
                lawyer_id=p.lawyer_id,
                name=p.user.name,  # from related User
                specialization=p.specialization,
                years_of_experience=p.years_of_experience,
                office_address=p.office_address,
                consultation_fee=float(p.consultation_fee)
                if p.consultation_fee is not None
                else None,
                verification_status=p.verification_status,
            )
        )

    return result
