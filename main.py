from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base
from routers import auth, valuations, quotes, pages

Base.metadata.create_all(bind=engine)

app = FastAPI(title="API de Valuation FCD - 9 Passos")

# Configuração de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

app.include_router(auth.router)
app.include_router(valuations.router)
app.include_router(quotes.router)
app.include_router(pages.router)
