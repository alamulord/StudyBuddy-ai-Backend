from fastapi import APIRouter, Depends
from typing import Annotated, Any
from app.core.deps import get_current_user

router = APIRouter()

@router.get("/me")
def read_users_me(current_user: Annotated[Any, Depends(get_current_user)]):
    return current_user
