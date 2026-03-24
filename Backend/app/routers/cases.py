from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db
from app.routers.auth import get_current_user

router = APIRouter(
    prefix="/cases",
    tags=["cases"],
)

VALID_CASE_STATUSES = {"open", "in_progress", "closed"}
VALID_REQUEST_STATUSES = {"pending", "accepted", "rejected"}


def ensure_client(user: models.User):
    if user.role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only clients can perform this action",
        )


def ensure_lawyer(user: models.User):
    if user.role != "lawyer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only lawyers can perform this action",
        )


def ensure_case_access(case: models.Case, user: models.User, db: Session):
    if user.role == "client":
        if case.user_id != user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this case",
            )
    elif user.role == "lawyer":
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
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this case",
            )


@router.post("/", response_model=schemas.CaseOut)
def create_case(
    case_in: schemas.CaseCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_client(current_user)

    case = models.Case(
        user_id=current_user.user_id,
        title=case_in.title,
        description=case_in.description,
        law_domain=case_in.law_domain,
        jurisdiction=case_in.jurisdiction,
        status="open",
    )
    db.add(case)
    db.flush()

    if case_in.lawyer_ids:
        for lawyer_user_id in case_in.lawyer_ids:
            lawyer_profile = (
                db.query(models.LawyerProfile)
                .filter(models.LawyerProfile.lawyer_id == lawyer_user_id)
                .first()
            )
            if not lawyer_profile:
                continue

            existing = (
                db.query(models.Request)
                .filter(
                    models.Request.case_id == case.case_id,
                    models.Request.lawyer_id == lawyer_user_id,
                )
                .first()
            )
            if existing:
                continue

            req = models.Request(
                user_id=current_user.user_id,
                case_id=case.case_id,
                lawyer_id=lawyer_user_id,
                status="pending",
            )
            db.add(req)

    db.commit()
    db.refresh(case)
    return _build_case_out(case)


def _build_case_out(case: models.Case) -> schemas.CaseOut:
    client_name = case.user.name if case.user else None
    assigned_lawyer_name = None
    for assignment in case.assignments:
        if assignment.status == "active" and assignment.lawyer_profile and assignment.lawyer_profile.user:
            assigned_lawyer_name = assignment.lawyer_profile.user.name
            break
    return schemas.CaseOut(
        case_id=case.case_id,
        user_id=case.user_id,
        title=case.title,
        description=case.description,
        law_domain=case.law_domain,
        jurisdiction=case.jurisdiction,
        status=case.status,
        created_at=case.created_at,
        client_name=client_name,
        assigned_lawyer_name=assigned_lawyer_name,
    )


@router.get("/my", response_model=List[schemas.CaseOut])
def list_my_cases(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    status_filter: Optional[str] = None,
):
    if current_user.role == "client":
        query = db.query(models.Case).filter(models.Case.user_id == current_user.user_id)
    elif current_user.role == "lawyer":
        query = (
            db.query(models.Case)
            .join(models.CaseAssignment)
            .filter(models.CaseAssignment.lawyer_id == current_user.user_id)
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unsupported role",
        )

    if status_filter:
        s = status_filter.lower()
        if s not in VALID_CASE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status_filter. Allowed: {', '.join(sorted(VALID_CASE_STATUSES))}",
            )
        query = query.filter(models.Case.status == s)

    return [_build_case_out(c) for c in query.order_by(models.Case.created_at.desc()).all()]

@router.get("/requests/my", response_model=List[schemas.CaseRequestOut])
def list_my_requests(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    status_filter: Optional[str] = "pending",
):
    ensure_lawyer(current_user)

    query = db.query(models.Request).filter(
        models.Request.lawyer_id == current_user.user_id
    )

    if status_filter:
        s = status_filter.lower()
        if s not in VALID_REQUEST_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status_filter. Allowed: {', '.join(sorted(VALID_REQUEST_STATUSES))}",
            )
        query = query.filter(models.Request.status == s)

    requests = query.order_by(models.Request.created_at.desc()).all()
    result = []
    for req in requests:
        result.append(schemas.CaseRequestOut(
            request_id=req.request_id,
            case_id=req.case_id,
            lawyer_id=req.lawyer_id,
            status=req.status,
            created_at=req.created_at,
            case_title=req.case.title if req.case else None,
            case_description=req.case.description if req.case else None,
            case_law_domain=req.case.law_domain if req.case else None,
            client_name=req.user.name if req.user else None,
            lawyer_name=current_user.name,
        ))
    return result


@router.get("/client-requests/my", response_model=List[schemas.CaseRequestOut])
def list_client_requests(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    status_filter: Optional[str] = None,
):
    ensure_client(current_user)

    query = db.query(models.Request).filter(
        models.Request.user_id == current_user.user_id
    )

    if status_filter:
        s = status_filter.lower()
        if s not in VALID_REQUEST_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status_filter. Allowed: {', '.join(sorted(VALID_REQUEST_STATUSES))}",
            )
        query = query.filter(models.Request.status == s)

    requests = query.order_by(models.Request.created_at.desc()).all()
    result = []
    for req in requests:
        lawyer_name = None
        if req.lawyer_profile and req.lawyer_profile.user:
            lawyer_name = req.lawyer_profile.user.name
        result.append(schemas.CaseRequestOut(
            request_id=req.request_id,
            case_id=req.case_id,
            lawyer_id=req.lawyer_id,
            status=req.status,
            created_at=req.created_at,
            case_title=req.case.title if req.case else None,
            case_description=req.case.description if req.case else None,
            case_law_domain=req.case.law_domain if req.case else None,
            client_name=current_user.name,
            lawyer_name=lawyer_name,
        ))
    return result


@router.post("/requests/{request_id}/respond")
def respond_to_request(
    request_id: int,
    resp: schemas.RequestResponse,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_lawyer(current_user)

    new_status = resp.status.lower()
    if new_status not in {"accepted", "rejected"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status must be 'accepted' or 'rejected'",
        )

    req = db.get(models.Request, request_id)
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Request not found",
        )

    if req.lawyer_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This request is not assigned to you",
        )

    if req.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Request is already {req.status}",
        )

    case = db.get(models.Case, req.case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    if new_status == "rejected":
        req.status = "rejected"
        db.commit()
        return {"detail": "Request rejected", "request_id": request_id, "status": "rejected"}


    existing_assignment = (
        db.query(models.CaseAssignment)
        .filter(
            models.CaseAssignment.case_id == case.case_id,
            models.CaseAssignment.status == "active",
        )
        .first()
    )
    if existing_assignment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Case is already assigned to another lawyer",
        )

    req.status = "accepted"

    assignment = models.CaseAssignment(
        case_id=case.case_id,
        lawyer_id=current_user.user_id,
        status="active",
    )
    db.add(assignment)
    case.status = "in_progress"

    other_pending = (
        db.query(models.Request)
        .filter(
            models.Request.case_id == case.case_id,
            models.Request.request_id != req.request_id,
            models.Request.status == "pending",
        )
        .all()
    )
    for r in other_pending:
        r.status = "rejected"

    db.commit()
    db.refresh(assignment)
    return schemas.CaseAssignmentOut(
        assignment_id=assignment.assignment_id,
        case_id=assignment.case_id,
        lawyer_id=assignment.lawyer_id,
        status=assignment.status,
        created_at=assignment.created_at,
    )


@router.get("/{case_id}", response_model=schemas.CaseOut)
def get_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    case = db.get(models.Case, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    ensure_case_access(case, current_user, db)
    return _build_case_out(case)


@router.post("/{case_id}/invite", response_model=List[schemas.CaseRequestOut])
def invite_lawyers(
    case_id: int,
    lawyer_ids: List[int],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ensure_client(current_user)

    case = db.get(models.Case, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    if case.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this case",
        )

    if case.status == "closed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot invite lawyers on a closed case",
        )

    created_requests: List[models.Request] = []

    for lawyer_user_id in lawyer_ids:
        lawyer_profile = (
            db.query(models.LawyerProfile)
            .filter(models.LawyerProfile.lawyer_id == lawyer_user_id)
            .first()
        )
        if not lawyer_profile:
            continue

        existing = (
            db.query(models.Request)
            .filter(
                models.Request.case_id == case.case_id,
                models.Request.lawyer_id == lawyer_user_id,
            )
            .first()
        )
        if existing:
            continue

        req = models.Request(
            user_id=current_user.user_id,
            case_id=case.case_id,
            lawyer_id=lawyer_user_id,
            status="pending",
        )
        db.add(req)
        created_requests.append(req)

    db.commit()
    return created_requests


@router.patch("/{case_id}/status", response_model=schemas.CaseOut)
def update_case_status(
    case_id: int,
    update: schemas.CaseStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    new_status = update.status.lower()
    if new_status not in VALID_CASE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Allowed: {', '.join(sorted(VALID_CASE_STATUSES))}",
        )

    case = db.get(models.Case, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Case not found",
        )

    ensure_case_access(case, current_user, db)

    if case.status == "closed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Closed cases cannot be reopened",
        )

    if new_status == "in_progress":
        active = (
            db.query(models.CaseAssignment)
            .filter(
                models.CaseAssignment.case_id == case.case_id,
                models.CaseAssignment.status == "active",
            )
            .first()
        )
        if not active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot mark case in_progress without an active assignment",
            )

    case.status = new_status
    if new_status == "closed":
        assignments = (
            db.query(models.CaseAssignment)
            .filter(models.CaseAssignment.case_id == case.case_id)
            .all()
        )
        for a in assignments:
            a.status = "closed"

    db.commit()
    db.refresh(case)
    return _build_case_out(case)
