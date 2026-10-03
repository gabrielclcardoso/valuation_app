# schemas.py
from pydantic import BaseModel
from datetime import datetime


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


class ValuationCreate(BaseModel):
    ticker: str
    preco_atual: float
    fclf_inicial: float
    anos_projecao: int
    taxas_crescimento: list[float]
    wacc: float
    cresc_perp: float
    divida_liquida: float
    num_acoes: float
    margem_seguranca: float
    preco_justo: float
    preco_teto: float
    modelo: str = "dcf_fcff"
    detalhes: dict | str | None = None


class ValuationResponse(BaseModel):
    id: int
    ticker: str
    preco_atual: float
    fclf_inicial: float
    anos_projecao: int
    taxas_crescimento: list[float]
    wacc: float
    cresc_perp: float
    divida_liquida: float
    num_acoes: float
    margem_seguranca: float
    preco_justo: float
    preco_teto: float
    modelo: str = "dcf_fcff"
    detalhes: dict | str | None = None
    criado_em: datetime

    class Config:
        from_attributes = True
