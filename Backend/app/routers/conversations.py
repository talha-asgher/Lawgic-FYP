from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy import func

from app import models, schemas
from app.deps import get_db
from app.routers.auth import get_current_user, SECRET_KEY, ALGORITHM
from app.ws.connection_manager import manager

router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
)

def _get_conv_or_404(conv_id: int, db: Session) -> models.Conversation:
    conv = db.get(models.Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


def _verify_participant(conv: models.Conversation, user: models.User) -> None:
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
        title=conv.title,
        participants=participants,
        last_message=last_msg.content if last_msg else None,
        last_message_at=last_msg.created_at if last_msg else None,
        unread_count=unread,
        created_at=conv.created_at,
    )


def _find_existing_conversation(
    db: Session, user_a_id: int, user_b_id: int
) -> models.Conversation | None:
    candidate_ids = (
        db.query(models.ConversationParticipant.conv_id)
        .filter(models.ConversationParticipant.user_id.in_([user_a_id, user_b_id]))
        .group_by(models.ConversationParticipant.conv_id)
        .having(func.count(func.distinct(models.ConversationParticipant.user_id)) == 2)
        .subquery()
    )

    conversations = (
        db.query(models.Conversation)
        .filter(models.Conversation.conv_id.in_(candidate_ids))
        .all()
    )

    for conv in conversations:
        participant_ids = {
            p.user_id
            for p in db.query(models.ConversationParticipant)
            .filter(models.ConversationParticipant.conv_id == conv.conv_id)
            .all()
        }
        if participant_ids == {user_a_id, user_b_id}:
            return conv

    return None

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

    if current_user.role == "client" and other_user.role == "lawyer":
        active_assignment = (
            db.query(models.CaseAssignment)
            .join(models.Case)
            .filter(
                models.Case.user_id == current_user.user_id,
                models.CaseAssignment.lawyer_id == other_user.user_id,
                models.CaseAssignment.status == "active",
            )
            .first()
        )
        if not active_assignment:
            raise HTTPException(
                status_code=403,
                detail="You can only message a lawyer after they have accepted one of your case requests",
            )

    if current_user.role == "lawyer" and other_user.role == "client":
        active_assignment = (
            db.query(models.CaseAssignment)
            .join(models.Case)
            .filter(
                models.Case.user_id == other_user.user_id,
                models.CaseAssignment.lawyer_id == current_user.user_id,
                models.CaseAssignment.status == "active",
            )
            .first()
        )
        if not active_assignment:
            raise HTTPException(
                status_code=403,
                detail="You can only message a client who has an active case assigned to you",
            )

    existing = _find_existing_conversation(db, current_user.user_id, body.other_user_id)

    try:
        if existing:
            if body.initial_message is not None:
                content = body.initial_message.strip() if body.initial_message else None
                if content == "":
                    raise HTTPException(status_code=400, detail="Initial message cannot be blank")

                if content:
                    db.add(
                        models.Message(
                            conv_id=existing.conv_id,
                            sender_id=current_user.user_id,
                            content=content,
                            is_read=False,
                        )
                    )
                    existing.updated_at = datetime.now(timezone.utc)
                    db.commit()
                    db.refresh(existing)

            return _build_conv_out(existing, current_user.user_id)

        title = body.title.strip() if body.title and body.title.strip() else None

        conv = models.Conversation(
            title=title,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(conv)
        db.flush()

        for uid in (current_user.user_id, body.other_user_id):
            db.add(
                models.ConversationParticipant(
                    conv_id=conv.conv_id,
                    user_id=uid,
                )
            )

        if body.initial_message is not None:
            content = body.initial_message.strip() if body.initial_message else None
            if content == "":
                raise HTTPException(status_code=400, detail="Initial message cannot be blank")

            if content:
                db.add(
                    models.Message(
                        conv_id=conv.conv_id,
                        sender_id=current_user.user_id,
                        content=content,
                        is_read=False,
                    )
                )

        db.commit()
        db.refresh(conv)
        return _build_conv_out(conv, current_user.user_id)

    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error — transaction rolled back")


@router.get("/", response_model=List[schemas.ConversationOut])
def list_my_conversations(
    skip: int = Query(0, ge=0, description="Number of conversations to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max conversations to return"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """List all conversations the current user participates in, newest first."""
    conv_ids = (
        db.query(models.ConversationParticipant.conv_id)
        .filter(models.ConversationParticipant.user_id == current_user.user_id)
        .subquery()
    )
    convs = (
        db.query(models.Conversation)
        .filter(models.Conversation.conv_id.in_(conv_ids))
        .order_by(models.Conversation.updated_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [_build_conv_out(c, current_user.user_id) for c in convs]


@router.get("/{conv_id}/messages", response_model=List[schemas.MessageOut])
def list_messages(
    conv_id: int,
    skip: int = Query(0, ge=0, description="Number of messages to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max messages to return"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    conv = _get_conv_or_404(conv_id, db)
    _verify_participant(conv, current_user)

    messages = (
        db.query(models.Message)
        .filter(models.Message.conv_id == conv_id)
        .order_by(models.Message.created_at.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )

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


@router.post("/{conv_id}/messages", response_model=schemas.MessageOut, status_code=201)
async def send_message(
    conv_id: int,
    msg_in: schemas.MessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    conv = _get_conv_or_404(conv_id, db)
    _verify_participant(conv, current_user)

    try:
        msg = models.Message(
            conv_id=conv_id,
            sender_id=current_user.user_id,
            content=msg_in.content,
        )
        db.add(msg)
        conv.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(msg)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error — transaction rolled back")

    out = schemas.MessageOut(
        message_id=msg.message_id,
        conv_id=msg.conv_id,
        sender_id=msg.sender_id,
        sender_name=current_user.name,
        content=msg.content,
        is_read=msg.is_read,
        created_at=msg.created_at,
    )
    await manager.broadcast(conv_id, out.model_dump(mode="json"))
    return out


@router.patch("/{conv_id}/read")
def mark_as_read(
    conv_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    conv = _get_conv_or_404(conv_id, db)
    _verify_participant(conv, current_user)

    try:
        unread = (
            db.query(models.Message)
            .filter(
                models.Message.conv_id == conv_id,
                models.Message.sender_id != current_user.user_id,
                models.Message.is_read == False,  # noqa: E712
            )
            .all()
        )
        for m in unread:
            m.is_read = True
        db.commit()
        return {"marked_read": len(unread)}

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error — transaction rolled back")


@router.websocket("/ws/{conv_id}")
async def ws_conversation(
    conv_id: int,
    websocket: WebSocket,
    token: str = Query(...),
):
    db = next(get_db())
    try:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = int(payload.get("sub"))
        except (JWTError, TypeError, ValueError):
            await websocket.close(code=4001)
            return

        user = db.get(models.User, user_id)
        if not user or not user.is_active:
            await websocket.close(code=4001)
            return

        conv = db.get(models.Conversation, conv_id)
        if not conv:
            await websocket.close(code=4004)
            return

        if user_id not in {p.user_id for p in conv.participants}:
            await websocket.close(code=4003)
            return
    finally:
        db.close()

    await manager.connect(conv_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(conv_id, websocket)
