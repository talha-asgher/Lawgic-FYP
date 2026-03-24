from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db
from app.routers.auth import get_current_user

router = APIRouter(
    prefix="/appointments",
    tags=["appointments"],
)

VALID_STATUSES = {"pending", "accepted", "rejected", "cancelled"}

VALID_MODES = {"online_meeting", "chat", "phone", "physical"}


def _build_appt_out(appt: models.Appointment) -> schemas.AppointmentOut:
    lawyer_name = None
    client_name = None
    if appt.lawyer and appt.lawyer.user:
        lawyer_name = appt.lawyer.user.name
    if appt.user:
        client_name = appt.user.name
    return schemas.AppointmentOut(
        appt_id=appt.appt_id,
        mode_of_comm=appt.mode_of_comm,
        scheduled_at=appt.scheduled_at,
        status=appt.status,
        notes=appt.notes,
        user_id=appt.user_id,
        lawyer_id=appt.lawyer_id,
        lawyer_name=lawyer_name,
        client_name=client_name,
    )

@router.post("/", response_model=schemas.AppointmentOut)
def create_appointment(
    appt_in: schemas.AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user.role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only clients can create appointments",
        )

    lawyer_profile = db.get(models.LawyerProfile, appt_in.lawyer_id)
    if not lawyer_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lawyer not found",
        )

    active_assignment = (
        db.query(models.CaseAssignment)
        .join(models.Case)
        .filter(
            models.Case.user_id == current_user.user_id,
            models.CaseAssignment.lawyer_id == appt_in.lawyer_id,
            models.CaseAssignment.status == "active",
        )
        .first()
    )
    if not active_assignment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only book appointments for cases that have been accepted by this lawyer",
        )

    mode = appt_in.mode_of_comm.lower() if appt_in.mode_of_comm else None
    if mode not in VALID_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid mode_of_comm. Allowed: online_meeting, chat, phone, physical",
        )

    appt = models.Appointment(
        mode_of_comm=mode,
        scheduled_at=appt_in.scheduled_at,
        status="pending",
        user_id=current_user.user_id,
        lawyer_id=appt_in.lawyer_id,
    )

    db.add(appt)
    db.commit()
    db.refresh(appt)
    return _build_appt_out(appt)


@router.get("/my", response_model=List[schemas.AppointmentOut])
def list_my_appointments(
    status_filter: Optional[str] = None,
    mode_filter: Optional[str] = None,
    from_datetime: Optional[datetime] = None,
    to_datetime: Optional[datetime] = None,
    upcoming_only: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Appointment)

    if current_user.role == "client":
        query = query.filter(models.Appointment.user_id == current_user.user_id)
    elif current_user.role == "lawyer":
        query = query.filter(models.Appointment.lawyer_id == current_user.user_id)

    if status_filter:
        s = status_filter.lower()
        if s not in VALID_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status_filter. Allowed: {', '.join(sorted(VALID_STATUSES))}",
            )
        query = query.filter(models.Appointment.status == s)

    if mode_filter:
        m = mode_filter.lower()
        if m not in VALID_MODES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid mode_filter. Allowed: online_meeting, chat, phone, physical",
            )
        query = query.filter(models.Appointment.mode_of_comm == m)

    now = datetime.utcnow()
    if upcoming_only:
        query = query.filter(models.Appointment.scheduled_at >= now)

    if from_datetime:
        query = query.filter(models.Appointment.scheduled_at >= from_datetime)

    if to_datetime:
        query = query.filter(models.Appointment.scheduled_at <= to_datetime)

    return [_build_appt_out(a) for a in query.order_by(models.Appointment.scheduled_at).all()]


@router.patch("/{appt_id}/status", response_model=schemas.AppointmentOut)
def update_appointment_status(
    appt_id: int,
    status_in: schemas.AppointmentStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    new_status = status_in.status.lower()

    if new_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Allowed: {', '.join(sorted(VALID_STATUSES))}",
        )

    appt = db.get(models.Appointment, appt_id)
    if not appt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found",
        )

    is_client = current_user.role == "client" and appt.user_id == current_user.user_id
    is_lawyer = current_user.role == "lawyer" and appt.lawyer_id == current_user.user_id

    if not (is_client or is_lawyer):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not allowed to modify this appointment",
        )

    current_status = appt.status.lower()

    if current_status in {"cancelled", "rejected"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot change status once it is {current_status}",
        )

    if is_client:
        if new_status != "cancelled":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Clients can only cancel appointments",
            )
        if current_status not in {"pending", "accepted"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel appointment in status {current_status}",
            )

    if is_lawyer:
        if new_status not in {"accepted", "rejected"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lawyers can only accept or reject appointments",
            )
        if current_status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Can only accept or reject appointments in pending status (current: {current_status})",
            )

    appt.status = new_status
    db.commit()
    db.refresh(appt)
    return _build_appt_out(appt)
