# Imagem do Rota. Existe para que o protótipo rode igual em qualquer lugar —
# na máquina do professor, num host gratuito ou num servidor da universidade —
# sem depender de ter o Python certo instalado.
#
#   docker build -t rota .
#   docker run --rm -p 8012:8012 -e ROTA_MODO=demo rota
#
# ROTA_MODO=demo tranca o login do SIGAA: é o modo da instância pública.
FROM python:3.12-slim

WORKDIR /app

# as dependências primeiro, para o cache da camada sobreviver a mudança de código
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py dados_demo.json ./
COPY nucleo/ ./nucleo/
COPY web/ ./web/

# roda sem privilégio: a imagem não precisa de root para servir HTTP
RUN useradd --create-home rota && chown -R rota /app
USER rota

ENV ROTA_MODO=demo \
    PORT=8012
EXPOSE 8012

# o host usa a variável PORT; localmente cai no 8012
CMD ["sh", "-c", "python -m uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
