from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import jwt
import bcrypt

from database import get_db
from models import UserDB
from schemas import LoginRequest
from security import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, ACCESS_TOKEN_EXPIRE_MINUTES_LONG

router = APIRouter(tags=["Autenticação"])


def get_user_by_username(db: Session, username: str):
    return db.query(UserDB).filter(UserDB.username == username).first()


@router.post("/login")
def login(login_data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = get_user_by_username(db, login_data.username)
    if not user or not bcrypt.checkpw(
        login_data.senha.encode("utf-8"), user.senha_hash.encode("utf-8")
    ):
        raise HTTPException(status_code=400, detail="Usuário ou senha incorretos.")

    if login_data.remember_me:
        expire_minutes = ACCESS_TOKEN_EXPIRE_MINUTES_LONG
    else:
        expire_minutes = ACCESS_TOKEN_EXPIRE_MINUTES

    expire = datetime.utcnow() + timedelta(minutes=expire_minutes)
    to_encode = {"sub": str(user.id), "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    response.set_cookie(
        key="access_token",
        value=f"Bearer {encoded_jwt}",
        httponly=True,
        max_age=expire_minutes * 60,
        samesite="lax",
    )
    return {"message": "Login realizado com sucesso"}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logout realizado"}
