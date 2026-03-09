# app/routers/inheritance.py
from fastapi import APIRouter
from app import schemas
from app.services.inheritance_service import calculate_inheritance

router = APIRouter(
    prefix="/inheritance",
    tags=["inheritance"],
)


@router.post("/calculate", response_model=schemas.InheritanceResult)
def calculate(inp: schemas.HeirInput):

    return calculate_inheritance(inp)
