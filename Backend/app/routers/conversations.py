from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.deps import get_db
from app.routers.auth import get_current_user

router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
)


def _get_conv_or_404(conv_id: int, db: Session) -> models.Conversation:
    conv = db.get(models.Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


def _verify_participant(conv: models.Conversation, user: models.User):
    ids = {p.user_id for p in conv.participants}
    if user.user_id not in ids:
        raise HTTPException(status_code=403, detail="Access denied")


def _build_conv_out(conv: models.Conversation, current_user_id: int) -> schemas.ConversationOut:
    participants = [
        schemas.ConversationParticipantOut(user_id=p.user.user_id, name=p.user.name)
        for p in conv.participants
    ]
    last_msg = conv.messages[-1] if conv.messages else None
    unread = sum(
        1 for m in conv.messages
        if not m.is_read and m.sender_id != current_user_id
    )
    return schemas.ConversationOut(
        conv_id=conv.conv_id,
        case_id=conv.case_id,
        title=conv.title,
        participants=participants,
        last_message=last_msg.content if last_msg else None,
        last_message_at=last_msg.created_at if last_msg else None,
        unread_count=unread,
        created_at=conv.created_at,
    )


@router.post("/", response_model=schemas.ConversationOut)
def get_or_create_conversation(
    body: schemas.ConversationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):

    other_user = db.get(models.User, body.other_user_id)
    if not other_user:
        raise HTTPException(status_code=404, detail="User not found")
    if other_user.user_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="Cannot start a conversation with yourself")

    my_convs = (
        db.query(models.ConversationParticipant.conv_id)
        .filter(models.ConversationParticipant.user_id == current_user.user_id)
        .subquery()
    )
    other_convs = (
        db.query(models.ConversationParticipant.conv_id)
        .filter(models.ConversationParticipant.user_id == body.other_user_id)
        .subquery()
    )
    shared = (
        db.query(models.Conversation)
        .filter(
            models.Conversation.conv_id.in_(my_convs),
            models.Conversation.conv_id.in_(other_convs),
        )
        .first()
    )

    if shared:
        if body.initial_message:
            msg = models.Message(
                conv_id=shared.conv_id,
                sender_id=current_user.user_id,
                content=body.initial_message,
            )
            db.add(msg)
            db.commit()
            db.refresh(shared)
        return _build_conv_out(shared, current_user.user_id)

    conv = models.Conversation(case_id=body.case_id)
    db.add(conv)
    db.flush()

    for uid in [current_user.user_id, body.other_user_id]:
        db.add(models.ConversationParticipant(conv_id=conv.conv_id, user_id=uid))

    if body.initial_message:
        db.add(models.Message(
            conv_id=conv.conv_id,
            sender_id=current_user.user_id,
            content=body.initial_message,
        ))

    db.commit()
    db.refresh(conv)
    return _build_conv_out(conv, current_user.user_id)


@router.get("/", response_model=List[schemas.ConversationOut])
def list_my_conversations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    participants = (
        db.query(models.ConversationParticipant)
        .filter(models.ConversationParticipant.user_id == current_user.user_id)
        .all()
    )
    conv_ids = [p.conv_id for p in participants]
    convs = (
        db.query(models.Conversation)
        .filter(models.Conversation.conv_id.in_(conv_ids))
        .order_by(models.Conversation.updated_at.desc())
        .all()
    )
    return [_build_conv_out(c, current_user.user_id) for c in convs]


@router.get("/{conv_id}/messages", response_model=List[schemas.MessageOut])
def list_messages(
    conv_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    conv = _get_conv_or_404(conv_id, db)
    _verify_participant(conv, current_user)

    messages = (
        db.query(models.Message)
        .filter(models.Message.conv_id == conv_id)
        .order_by(models.Message.created_at.asc())
        .all()
    )

    for m in messages:
        if not m.is_read and m.sender_id != current_user.user_id:
            m.is_read = True
    db.commit()

    return [
        schemas.MessageOut(
            message_id=m.message_id,
            conv_id=m.conv_id,
            sender_id=m.sender_id,
            sender_name=m.sender.name if m.sender else None,
            content=m.content,
            is_read=m.is_read,
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.post("/{conv_id}/messages", response_model=schemas.MessageOut)
def send_message(
    conv_id: int,
    msg_in: schemas.MessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    conv = _get_conv_or_404(conv_id, db)
    _verify_participant(conv, current_user)

    if not msg_in.content.strip():
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    msg = models.Message(
        conv_id=conv_id,
        sender_id=current_user.user_id,
        content=msg_in.content.strip(),
    )
    db.add(msg)
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(msg)

    return schemas.MessageOut(
        message_id=msg.message_id,
        conv_id=msg.conv_id,
        sender_id=msg.sender_id,
        sender_name=current_user.name,
        content=msg.content,
        is_read=msg.is_read,
        created_at=msg.created_at,
    )


@router.patch("/{conv_id}/read")
def mark_as_read(
    conv_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    conv = _get_conv_or_404(conv_id, db)
    _verify_participant(conv, current_user)

    updated = (
        db.query(models.Message)
        .filter(
            models.Message.conv_id == conv_id,
            models.Message.sender_id != current_user.user_id,
            models.Message.is_read == False,
        )
        .all()
    )
    for m in updated:
        m.is_read = True
    db.commit()
    return {"marked_read": len(updated)}
