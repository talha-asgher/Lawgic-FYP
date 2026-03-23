# app/routers/case_messages.py
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
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
        raise HTTPException(status_code=403, detail="Access denied")


@router.post("/{case_id}/messages", response_model=schemas.CaseMessageOut)
def send_case_message(
    case_id: int,
    msg_in: schemas.CaseMessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    case = db.get(models.Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    verify_case_access(case, current_user, db)

    if case.status == "closed":
        raise HTTPException(status_code=400, detail="Cannot message in a closed case")

    msg = models.CaseMessage(
        case_id=case_id,
        sender_id=current_user.user_id,
        content=msg_in.content,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    return schemas.CaseMessageOut(
        message_id=msg.message_id,
        case_id=msg.case_id,
        sender_id=msg.sender_id,
        sender_name=current_user.name,
        content=msg.content,
        is_read=msg.is_read,
        created_at=msg.created_at,
    )


@router.get("/{case_id}/messages", response_model=List[schemas.CaseMessageOut])
def list_case_messages(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    case = db.get(models.Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    verify_case_access(case, current_user, db)

    messages = (
        db.query(models.CaseMessage)
        .filter(models.CaseMessage.case_id == case_id)
        .order_by(models.CaseMessage.created_at.asc())
        .all()
    )

    for m in messages:
        if not m.is_read and m.sender_id != current_user.user_id:
            m.is_read = True
    db.commit()

    result = []
    for m in messages:
        sender = db.get(models.User, m.sender_id)
        result.append(schemas.CaseMessageOut(
            message_id=m.message_id,
            case_id=m.case_id,
            sender_id=m.sender_id,
            sender_name=sender.name if sender else None,
            content=m.content,
            is_read=m.is_read,
            created_at=m.created_at,
        ))
    return result
