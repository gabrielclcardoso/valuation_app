from fastapi import APIRouter, Depends, HTTPException
import httpx
import os

from security import get_current_user_id

router = APIRouter(tags=["Cotações"])
BRAPI_TOKEN = os.getenv("BRAPI_TOKEN")


@router.get("/api/quote/{ticker}")
async def get_quote(ticker: str, user_id: int = Depends(get_current_user_id)):
    if not BRAPI_TOKEN:
        raise HTTPException(status_code=500, detail="Token da Brapi não configurado.")

    async with httpx.AsyncClient() as client:
        url = f"https://brapi.dev/api/quote/{ticker}?token={BRAPI_TOKEN}"
        resposta = await client.get(url)

        if resposta.status_code != 200:
            raise HTTPException(
                status_code=400, detail="Erro ao buscar cotação na Brapi"
            )

        return resposta.json()
