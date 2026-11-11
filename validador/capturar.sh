#!/usr/bin/env bash
# Captura as figuras do documento (atividade/trabalho-final.html), sempre no
# mesmo estado.
#
# Por que por script e não no braço: print tirado à mão nunca sai duas vezes
# igual — muda o scroll, muda a largura, muda o que está marcado.
#
# Como: abre um Chrome sem tela e o `capturar.mjs` (Node, sem dependência)
# dirige cada tela por link direto (?demo=1&tema=claro#<tela>), em escala 2 (o
# papel precisa de densidade) e tema claro (fundo preto em documento come
# tinta). Cada figura é recortada PELO NAVEGADOR, no retângulo dos blocos que
# ela mostra — e não mais por posição em pixel anotada à mão no recortar.py,
# que quebrou quando o layout mudou e dependia do PIL, ausente nesta máquina.
#
# Saem as oito figuras com os nomes que o documento usa (2-decisao-caminhos …
# 9-relatorio) e duas extras que ele não usa (extra-*).
#
# uso: ./capturar.sh <pasta-de-saida> [url-base]
#      CHROME=/outro/chrome ./capturar.sh …   se o Chrome estiver noutro lugar
set -euo pipefail

SAIDA="${1:?informe a pasta de saída}"
BASE="${2:-http://127.0.0.1:8012}"
CHROME="${CHROME:-$HOME/.local/opt/chrome/chrome}"
PORTA="${PORTA:-9444}"
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

[ -x "$CHROME" ] || { echo "ERRO: não achei o Chrome em $CHROME (ver atividade/gerar-pdf.sh)"; exit 1; }
command -v node >/dev/null || { echo "ERRO: precisa do node (22 ou mais novo)"; exit 1; }
curl -sf --max-time 5 "$BASE/api/status" >/dev/null || { echo "ERRO: o Rota não respondeu em $BASE"; exit 1; }

# perfil descartável em caminho CURTO: com TMPDIR longo o Chrome morre com
# "Socket path too long"
PERFIL="$(mktemp -d /tmp/rota-cap.XXXXXX)"
# --no-sandbox: esta VPS não tem sandbox de usuário; a página é a do próprio Rota
"$CHROME" --headless=new --no-sandbox --disable-gpu --hide-scrollbars --no-first-run \
  --remote-debugging-port="$PORTA" --user-data-dir="$PERFIL" about:blank >/dev/null 2>&1 &
PID=$!
trap 'kill "$PID" 2>/dev/null; sleep 1; rm -rf "$PERFIL"' EXIT

for _ in $(seq 1 30); do
  curl -sf "http://127.0.0.1:$PORTA/json/version" >/dev/null && break
  sleep 0.3
done

echo "capturando $BASE em $SAIDA:"
node "$AQUI/capturar.mjs" "$SAIDA" "$BASE" "$PORTA"
echo "pronto."
