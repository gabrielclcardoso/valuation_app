# Usa uma versão oficial e enxuta do Python
FROM python:3.11-slim

# Define a pasta de trabalho dentro do contêiner
WORKDIR /app

# Instala o uv no contêiner
RUN pip install --no-cache-dir uv

# Copia os arquivos de configuração do uv PRIMEIRO (para aproveitar o cache do Docker)
# O asterisco permite copiar o uv.lock caso ele exista, sem dar erro se não existir
COPY pyproject.toml uv.lock* ./

# Usa o uv para instalar as dependências do pyproject.toml diretamente no sistema do contêiner
RUN uv pip install --system -r pyproject.toml

# Copia o restante do código (main.py, pasta frontend/, etc.)
COPY . .

# Expõe a porta 8000 internamente
EXPOSE 8000

# Comando para iniciar o servidor
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
