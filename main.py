from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Depends, HTTPException, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import List
import json
from datetime import datetime, timedelta
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Float,
    String,
    ForeignKey,
    DateTime,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from jose import JWTError, jwt
import bcrypt

# ==========================================
# CONFIGURAÇÕES DO BANCO DE DADOS (SQLITE)
# ==========================================
SQLALCHEMY_DATABASE_URL = "sqlite:///./data/valuations.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==========================================
# CONFIGURAÇÕES DE SEGURANÇA (JWT & HASH)
# ==========================================
SECRET_KEY = "sua_chave_secreta_super_segura_aqui"  # Mude isso em produção
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# ==========================================
# MODELOS DO BANCO DE DADOS (SQLAlchemy)
# ==========================================
class UserDB(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    senha_hash = Column(String, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)


class ValuationDB(Base):
    __tablename__ = "valuations"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(
        Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    ticker = Column(String, nullable=False)
    preco_atual = Column(Float, nullable=False)
    fclf_inicial = Column(Float, nullable=False)
    anos_projecao = Column(Integer, nullable=False)
    taxas_crescimento = Column(String, nullable=False)  # Salvo como String JSON
    wacc = Column(Float, nullable=False)
    cresc_perp = Column(Float, nullable=False)
    divida_liquida = Column(Float, nullable=False)
    num_acoes = Column(Float, nullable=False)
    margem_seguranca = Column(Float, nullable=False)
    preco_justo = Column(Float, nullable=False)
    preco_teto = Column(Float, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)


# Criar as tabelas no arquivo SQLite se não existirem
Base.metadata.create_all(bind=engine)


# Dependency para obter a sessão do banco
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==========================================
# SCHEMAS DE VALIDAÇÃO (Pydantic)
# ==========================================
class UserRegister(BaseModel):
    nome: str
    username: str
    senha: str


class UserResponse(BaseModel):
    id: int
    nome: str
    username: str

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    username: str
    senha: str


class Token(BaseModel):
    access_token: str
    token_type: str


class ValuationCreate(BaseModel):
    ticker: str
    preco_atual: float
    fclf_inicial: float
    anos_projecao: int
    taxas_crescimento: List[float]  # Recebe como Array do React
    wacc: float
    cresc_perp: float
    divida_liquida: float
    num_acoes: float
    margem_seguranca: float
    preco_justo: float
    preco_teto: float


class ValuationResponse(BaseModel):
    id: int
    ticker: str
    preco_atual: float
    fclf_inicial: float
    anos_projecao: int
    taxas_crescimento: List[float]
    wacc: float
    cresc_perp: float
    divida_liquida: float
    num_acoes: float
    margem_seguranca: float
    preco_justo: float
    preco_teto: float
    criado_em: datetime

    class Config:
        from_attributes = True


# ==========================================
# FUNÇÕES UTILITÁRIAS
# ==========================================
def get_user_by_username(db: Session, username: str):
    return db.query(UserDB).filter(UserDB.username == username).first()


def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token de autenticação inválido ou expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return int(user_id)
    except JWTError:
        raise credentials_exception


# ==========================================
# ROTAS DA API (FastAPI)
# ==========================================
app = FastAPI(title="API de Valuation FCD - 9 Passos")

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Configuração de CORS para permitir conexões do React (local ou VPS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, mude para a URL do seu frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/register", response_model=UserResponse, status_code=201)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    db_user = get_user_by_username(db, user_data.username)
    if db_user:
        raise HTTPException(
            status_code=400, detail="Este nome de usuário já está em uso."
        )

    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(user_data.senha.encode("utf-8"), salt).decode(
        "utf-8"
    )
    novo_usuario = UserDB(
        nome=user_data.nome, username=user_data.username, senha_hash=hashed_password
    )
    db.add(novo_usuario)
    db.commit()
    db.refresh(novo_usuario)
    return novo_usuario


@app.post("/valuations", response_model=ValuationResponse)
def save_valuation(
    valuation: ValuationCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    taxas_string = json.dumps(valuation.taxas_crescimento)

    novo_valuation = ValuationDB(
        usuario_id=user_id,
        ticker=valuation.ticker,
        preco_atual=valuation.preco_atual,
        fclf_inicial=valuation.fclf_inicial,
        anos_projecao=valuation.anos_projecao,
        taxas_crescimento=taxas_string,
        wacc=valuation.wacc,
        cresc_perp=valuation.cresc_perp,
        divida_liquida=valuation.divida_liquida,
        num_acoes=valuation.num_acoes,
        margem_seguranca=valuation.margem_seguranca,
        preco_justo=valuation.preco_justo,
        preco_teto=valuation.preco_teto,
    )
    db.add(novo_valuation)
    db.commit()
    db.refresh(novo_valuation)

    novo_valuation.taxas_crescimento = json.loads(novo_valuation.taxas_crescimento)
    return novo_valuation


@app.get("/valuations", response_model=List[ValuationResponse])
def list_valuations(
    db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)
):
    history = db.query(ValuationDB).filter(ValuationDB.usuario_id == user_id).all()

    for item in history:
        item.taxas_crescimento = json.loads(item.taxas_crescimento)

    return history


# 1. A Rota de Login agora salva o token direto em um Cookie seguro no navegador
@app.post("/login")
def login(login_data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = get_user_by_username(db, login_data.username)
    if not user or not bcrypt.checkpw(
        login_data.senha.encode("utf-8"), user.senha_hash.encode("utf-8")
    ):
        raise HTTPException(status_code=400, detail="Usuário ou senha incorretos.")

    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": str(user.id), "exp": expire}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    # Cria o Cookie (httponly=True impede que hackers roubem o cookie via JavaScript)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {encoded_jwt}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return {"message": "Login realizado com sucesso"}


# 2. A Rota Principal (A "Porta de Entrada" do site) decide qual HTML enviar
@app.get("/")
def serve_frontend(request: Request):
    token = request.cookies.get("access_token")

    # Se não tem cookie nenhum, entrega só a tela de login
    if not token:
        return FileResponse("frontend/login.html")

    # Se tem cookie, tenta validar
    try:
        scheme, _, param = token.partition(" ")
        jwt.decode(param, SECRET_KEY, algorithms=[ALGORITHM])
        # Cookie é válido! Envia o código secreto da calculadora
        return FileResponse("frontend/calculator.html")
    except JWTError:
        # Se o token expirou ou for falso, manda pra tela de login
        return FileResponse("frontend/login.html")


# 3. Rota para fazer Logout (apagar o Cookie)
@app.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logout realizado"}
