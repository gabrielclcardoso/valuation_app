# routers/pages.py
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from security import SECRET_KEY, ALGORITHM

router = APIRouter(tags=["Frontend"])

# Configura o Jinja2 para ler a pasta de templates
templates = Jinja2Templates(directory="frontend/templates")


@router.get("/")
def serve_frontend(request: Request):
    token = request.cookies.get("access_token")

    # Se não tem cookie, renderiza a tela de login
    if not token:
        return templates.TemplateResponse(request=request, name="login.html")

    try:
        # Se o cookie for válido, renderiza a calculadora
        scheme, _, param = token.partition(" ")
        jwt.decode(param, SECRET_KEY, algorithms=[ALGORITHM])
        return templates.TemplateResponse(request=request, name="calculator.html")
    except JWTError:
        # Se expirou, volta pro login
        return templates.TemplateResponse(request=request, name="login.html")
