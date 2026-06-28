from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from jose import JWTError, jwt

from security import SECRET_KEY, ALGORITHM

router = APIRouter(tags=["Frontend"])


@router.get("/")
def serve_frontend(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return FileResponse("frontend/login.html")
    try:
        scheme, _, param = token.partition(" ")
        jwt.decode(param, SECRET_KEY, algorithms=[ALGORITHM])
        return FileResponse("frontend/calculator.html")
    except JWTError:
        return FileResponse("frontend/login.html")
