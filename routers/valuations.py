# routers/valuations.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import json

from database import get_db
from models import ValuationDB
from schemas import ValuationCreate, ValuationResponse
from security import get_current_user_id

router = APIRouter(tags=["Valuations"])


@router.post("/valuations", response_model=ValuationResponse)
def save_valuation(
    valuation: ValuationCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    # Converte a lista do front em String para o Banco de Dados
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

    resposta = novo_valuation.__dict__.copy()
    resposta["taxas_crescimento"] = json.loads(novo_valuation.taxas_crescimento)

    return resposta


@router.get("/valuations", response_model=List[ValuationResponse])
def list_valuations(
    db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)
):
    history = db.query(ValuationDB).filter(ValuationDB.usuario_id == user_id).all()

    resultado = []
    for item in history:
        dados = item.__dict__.copy()
        dados["taxas_crescimento"] = json.loads(item.taxas_crescimento)
        resultado.append(dados)

    return resultado


@router.delete("/valuations/{valuation_id}")
def delete_valuation(
    valuation_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    valuation = (
        db.query(ValuationDB)
        .filter(ValuationDB.id == valuation_id, ValuationDB.usuario_id == user_id)
        .first()
    )
    if not valuation:
        raise HTTPException(status_code=404, detail="Registo não encontrado.")
    db.delete(valuation)
    db.commit()
    return {"message": "Valuation eliminado."}
