# app/routers/lawyers.py
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db
from app.routers.auth import get_current_user

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


def build_lawyer_public(profile: models.LawyerProfile) -> schemas.LawyerPublic:
    specializations = [s.strip() for s in profile.specialization.split(",") if s.strip()]
    languages_list = []
    if profile.languages:
        languages_list = [l.strip() for l in profile.languages.split(",") if l.strip()]

    return schemas.LawyerPublic(
        lawyer_id=profile.lawyer_id,
        name=profile.user.name,
        email=profile.user.email,
        phone_num=profile.user.phone_num,
        specialization=profile.specialization,
        specializations=specializations,
        bio_data=profile.bio_data,
        years_of_experience=profile.years_of_experience,
        office_address=profile.office_address,
        city=profile.city,
        consultation_fee=float(profile.consultation_fee) if profile.consultation_fee else None,
        verification_status=profile.verification_status,
        languages=profile.languages,
        languages_list=languages_list,
        average_rating=profile.average_rating,
        review_count=profile.review_count or 0,
        bar_council_number=profile.bar_council_number,
        degree_type=profile.degree_type,
        law_school=profile.law_school,
    )


@router.post("/profile", response_model=schemas.LawyerProfileOut)
def create_or_update_profile(
    profile_in: schemas.LawyerProfileCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_lawyer_role(current_user)

    profile = (
        db.query(models.LawyerProfile)
        .filter(models.LawyerProfile.lawyer_id == current_user.user_id)
        .first()
    )

    if profile is None:
        profile = models.LawyerProfile(
            lawyer_id=current_user.user_id,
            specialization=profile_in.specialization,
            bio_data=profile_in.bio_data,
            verification_status="pending",
            years_of_experience=profile_in.years_of_experience,
            office_address=profile_in.office_address,
            consultation_fee=profile_in.consultation_fee,
            city=profile_in.city,
            languages=profile_in.languages,
            bar_council_number=profile_in.bar_council_number,
            law_school=profile_in.law_school,
            grad_year=profile_in.grad_year,
            degree_type=profile_in.degree_type,
            average_rating=0.0,
            review_count=0,
        )
        db.add(profile)
    else:
        profile.specialization = profile_in.specialization
        profile.bio_data = profile_in.bio_data
        profile.years_of_experience = profile_in.years_of_experience
        profile.office_address = profile_in.office_address
        profile.consultation_fee = profile_in.consultation_fee
        profile.city = profile_in.city
        profile.languages = profile_in.languages
        profile.bar_council_number = profile_in.bar_council_number
        profile.law_school = profile_in.law_school
        profile.grad_year = profile_in.grad_year
        profile.degree_type = profile_in.degree_type

    db.commit()
    db.refresh(profile)
    return profile


@router.get("/me", response_model=schemas.LawyerProfileOut)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
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
    q: Optional[str] = None,
    specialization: Optional[str] = None,
    city: Optional[str] = None,
    min_experience: Optional[int] = None,
    max_fee: Optional[float] = None,
    min_rating: Optional[float] = None,
    verification_status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.LawyerProfile).join(models.User)

    query = query.filter(models.User.is_active == True)

    if q:
        search_term = f"%{q}%"
        query = query.filter(
            models.User.name.ilike(search_term) |
            models.LawyerProfile.specialization.ilike(search_term)
        )

    if specialization:
        query = query.filter(
            models.LawyerProfile.specialization.ilike(f"%{specialization}%")
        )

    if city:
        query = query.filter(models.LawyerProfile.city.ilike(f"%{city}%"))

    if min_experience is not None:
        query = query.filter(models.LawyerProfile.years_of_experience >= min_experience)

    if max_fee is not None:
        query = query.filter(models.LawyerProfile.consultation_fee <= max_fee)

    if min_rating is not None:
        query = query.filter(models.LawyerProfile.average_rating >= min_rating)

    if verification_status:
        query = query.filter(models.LawyerProfile.verification_status == verification_status)

    profiles = query.order_by(models.LawyerProfile.average_rating.desc().nullslast()).all()
    return [build_lawyer_public(p) for p in profiles]


@router.get("/{lawyer_id}", response_model=schemas.LawyerPublic)
def get_lawyer_by_id(
    lawyer_id: int,
    db: Session = Depends(get_db),
):
    profile = (
        db.query(models.LawyerProfile)
        .filter(models.LawyerProfile.lawyer_id == lawyer_id)
        .first()
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Lawyer not found")
    return build_lawyer_public(profile)
