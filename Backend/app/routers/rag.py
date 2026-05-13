# from fastapi import APIRouter, Depends, HTTPException

# from app import models, schemas
# from app.database import SessionLocal
# from app.routers.auth import get_current_user
# from app.services.ollama_service import OllamaServiceError
# from app.services.rag_service import finalize_rag_ask, retrieve_for_rag_ask

# router = APIRouter(prefix="/rag", tags=["rag"])


# @router.post("/ask", response_model=schemas.RagAskResponse)
# def rag_ask(
#     req: schemas.RagAskRequest,
#     current_user: models.User = Depends(get_current_user),
# ):
#     _ = current_user
#     db = SessionLocal()
#     try:
#         retrieval = retrieve_for_rag_ask(db, req)
#     finally:
#         db.close()
#     try:
#         return finalize_rag_ask(req, retrieval)
#     except OllamaServiceError as e:
#         raise HTTPException(status_code=503, detail=str(e)) from e
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e)) from e
