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
def get_my_profile(
    current_user: models.User = Depends(get_current_user),
):
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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already in use",
            )
        current_user.email = update.email

    if update.name is not None:
        current_user.name = update.name

    if update.phone_num is not None:
        current_user.phone_num = update.phone_num

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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )
    
    if not validate_password(payload.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
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


