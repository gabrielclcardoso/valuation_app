from fastapi import APIRouter, Depends, HTTPException
import httpx
import os

from security import get_current_user_id

router = APIRouter(tags=["Cotações"])
BRAPI_TOKEN = os.getenv("BRAPI_TOKEN")
http_client = httpx.AsyncClient(timeout=10.0)


@router.get("/api/quote/{ticker}")
async def get_quote(ticker: str, user_id: int = Depends(get_current_user_id)):
    if not BRAPI_TOKEN:
        raise HTTPException(status_code=500, detail="Token da Brapi não configurado.")

    try:
        url = f"https://brapi.dev/api/quote/{ticker}?token={BRAPI_TOKEN}"
        resposta = await http_client.get(url)

        if resposta.status_code != 200:
            raise HTTPException(
                status_code=400, detail="Erro ao buscar cotação na Brapi"
            )

        return resposta.json()
    except httpx.RequestError:
        raise HTTPException(
            status_code=502, detail="Erro ao comunicar com a Brapi"
        )
