from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.dependencies import get_current_user
from app.mathtext import render

router = APIRouter(prefix="/math", tags=["math"], dependencies=[Depends(get_current_user)])


class MathIn(BaseModel):
    text: str = Field(max_length=50000)


class MathOut(BaseModel):
    html: str
    errors: list[str]
    has_math: bool


@router.post("/render", response_model=MathOut)
def render_math(payload: MathIn) -> dict:
    """Aperçu d'un texte contenant des formules LaTeX (élèves et administrateurs)."""
    return render(payload.text)
