# app/routers/reviews.py
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db
from app.routers.auth import get_current_user

router = APIRouter(
    prefix="/reviews",
    tags=["reviews"],
)


@router.post("/", response_model=schemas.ReviewOut)
def create_review(
    review_in: schemas.ReviewCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "client":
        raise HTTPException(status_code=403, detail="Only clients can leave reviews")

    lawyer_profile = db.get(models.LawyerProfile, review_in.lawyer_id)
    if not lawyer_profile:
        raise HTTPException(status_code=404, detail="Lawyer not found")

    existing = (
        db.query(models.RatingReview)
        .filter(
            models.RatingReview.user_id == current_user.user_id,
            models.RatingReview.lawyer_id == review_in.lawyer_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="You have already reviewed this lawyer")

    review = models.RatingReview(
        user_id=current_user.user_id,
        lawyer_id=review_in.lawyer_id,
        stars=review_in.stars,
        comment=review_in.comment,
    )
    db.add(review)
    db.flush()

    agg = (
        db.query(func.avg(models.RatingReview.stars), func.count(models.RatingReview.rating_id))
        .filter(models.RatingReview.lawyer_id == review_in.lawyer_id)
        .first()
    )
    lawyer_profile.average_rating = round(float(agg[0]), 2) if agg[0] else 0.0
    lawyer_profile.review_count = agg[1] or 0

    db.commit()
    db.refresh(review)

    return schemas.ReviewOut(
        rating_id=review.rating_id,
        user_id=review.user_id,
        lawyer_id=review.lawyer_id,
        stars=review.stars,
        comment=review.comment,
        reviewer_name=current_user.name,
        created_at=review.created_at,
    )


@router.get("/lawyer/{lawyer_id}", response_model=List[schemas.ReviewOut])
def get_lawyer_reviews(
    lawyer_id: int,
    db: Session = Depends(get_db),
):
    lawyer_profile = db.get(models.LawyerProfile, lawyer_id)
    if not lawyer_profile:
        raise HTTPException(status_code=404, detail="Lawyer not found")

    reviews = (
        db.query(models.RatingReview)
        .filter(models.RatingReview.lawyer_id == lawyer_id)
        .order_by(models.RatingReview.created_at.desc())
        .all()
    )

    result = []
    for r in reviews:
        reviewer = db.get(models.User, r.user_id)
        result.append(schemas.ReviewOut(
            rating_id=r.rating_id,
            user_id=r.user_id,
            lawyer_id=r.lawyer_id,
            stars=r.stars,
            comment=r.comment,
            reviewer_name=reviewer.name if reviewer else "Anonymous",
            created_at=r.created_at,
        ))
    return result
