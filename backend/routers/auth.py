from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from backend.core.auth import USERS_DB, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/auth/login")
async def login(request: LoginRequest):
    user = USERS_DB.get(request.username)
    if not user or not verify_password(request.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": request.username})
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": request.username,
        "role": user["role"]
    }

@router.get("/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "username": current_user["username"],
        "role": current_user["role"]
    }