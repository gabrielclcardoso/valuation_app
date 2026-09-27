# Imagem enxuta oficial do Python
FROM python:3.11-slim

WORKDIR /app

# Otimizações de ambiente Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copia o binário estático do uv diretamente (evita overhead de usar pip para instalar o uv)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copia arquivos de dependência primeiro para aproveitar cache do Docker
COPY pyproject.toml uv.lock* ./

# Instala as dependências diretamente no Python do sistema sem gerar cache desnecessário
RUN uv pip install --system -r pyproject.toml

# Copia o restante da aplicação
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
