from sqlalchemy import Column, Integer, Float, String, ForeignKey, DateTime
from datetime import datetime
from database import Base


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
    taxas_crescimento = Column(String, nullable=False)
    wacc = Column(Float, nullable=False)
    cresc_perp = Column(Float, nullable=False)
    divida_liquida = Column(Float, nullable=False)
    num_acoes = Column(Float, nullable=False)
    margem_seguranca = Column(Float, nullable=False)
    preco_justo = Column(Float, nullable=False)
    preco_teto = Column(Float, nullable=False)
    criado_em = Column(DateTime, default=datetime.utcnow)
