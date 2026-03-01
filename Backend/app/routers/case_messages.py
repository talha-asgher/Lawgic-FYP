from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db
from app.routers.auth import get_current_user

router = APIRouter(
    prefix="/cases",
    tags=["case-chat"],
)


def verify_case_access(case: models.Case, user: models.User, db: Session):
    if user.user_id == case.user_id:
        return

    assignment = (
        db.query(models.CaseAssignment)
        .filter(
            models.CaseAssignment.case_id == case.case_id,
            models.CaseAssignment.lawyer_id == user.user_id,
            models.CaseAssignment.status == "active",
        )
        .first()
    )

    if not assignment:
        raise HTTPException(403, "Access denied")