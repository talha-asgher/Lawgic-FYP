# app/routers/users.py
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db
from app.routers.auth import get_current_user, verify_password, hash_password, validate_password

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


@router.get("/me", response_model=schemas.UserProfileOut)
def get_my_profile(current_user: models.User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=schemas.UserProfileOut)
def update_my_profile(
    update: schemas.UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if update.email and update.email != current_user.email:
        existing = (
            db.query(models.User)
            .filter(models.User.email == update.email)
            .first()
        )
        if existing:
            raise HTTPException(status_code=400, detail="Email is already in use")
        current_user.email = update.email

    if update.name is not None:
        current_user.name = update.name
    if update.phone_num is not None:
        current_user.phone_num = update.phone_num
    if update.city is not None:
        current_user.city = update.city

    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/change-password")
def change_my_password(
    payload: schemas.PasswordChange,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must differ from current password")
    if not validate_password(payload.new_password):
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 6 characters and contain letters and numbers",
        )
    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"detail": "Password updated successfully"}


@router.delete("/me")
def delete_my_account(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    current_user.is_active = False
    db.commit()
    return {"detail": "Account deactivated"}


@router.get("/me/stats", response_model=schemas.UserDashboardStats)
def get_my_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    my_conv_ids = [
        p.conv_id for p in db.query(models.ConversationParticipant)
        .filter(models.ConversationParticipant.user_id == current_user.user_id)
        .all()
    ]
    unread = (
        db.query(models.Message)
        .filter(
            models.Message.conv_id.in_(my_conv_ids),
            models.Message.sender_id != current_user.user_id,
            models.Message.is_read == False,
        )
        .count()
    ) if my_conv_ids else 0

    if current_user.role == "client":
        documents = (
            db.query(models.Document)
            .filter(models.Document.user_id == current_user.user_id)
            .count()
        )
        qa_sessions = (
            db.query(models.QAInteraction.session_id)
            .filter(models.QAInteraction.user_id == current_user.user_id)
            .distinct()
            .count()
        )
        appointments = (
            db.query(models.Appointment)
            .filter(models.Appointment.user_id == current_user.user_id)
            .count()
        )
        open_cases = (
            db.query(models.Case)
            .filter(
                models.Case.user_id == current_user.user_id,
                models.Case.status != "closed",
            )
            .count()
        )
        return schemas.UserDashboardStats(
            documents=documents,
            qa_sessions=qa_sessions,
            appointments=appointments,
            open_cases=open_cases,
            unread_messages=unread,
        )

    elif current_user.role == "lawyer":
        active_cases = (
            db.query(models.CaseAssignment)
            .filter(
                models.CaseAssignment.lawyer_id == current_user.user_id,
                models.CaseAssignment.status == "active",
            )
            .count()
        )
        pending_requests = (
            db.query(models.Request)
            .filter(
                models.Request.lawyer_id == current_user.user_id,
                models.Request.status == "pending",
            )
            .count()
        )
        week_ago = datetime.utcnow() - timedelta(days=7)
        appointments_week = (
            db.query(models.Appointment)
            .filter(
                models.Appointment.lawyer_id == current_user.user_id,
                models.Appointment.scheduled_at >= week_ago,
            )
            .count()
        )
        return schemas.UserDashboardStats(
            documents=0,
            qa_sessions=0,
            appointments=appointments_week,
            open_cases=active_cases,
            unread_messages=unread,
        )

    return schemas.UserDashboardStats()
