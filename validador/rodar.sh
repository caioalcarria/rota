#!/usr/bin/env bash
# Roda o validador de usabilidade nas telas do Rota, pelo nó web do DOT.
# uso: ./rodar.sh <nodeId>
NODE="${1:?informe o nodeId do web}"
CLI="$HOME/.config/dot/dot-web.js"
JS="$(dirname "$0")/validador.js"
for v in decisao agora faltam optativas montar relatorio; do
  node "$CLI" js "document.querySelector('.nav-i[data-v=\"$v\"]').click()" --node "$NODE" >/dev/null 2>&1
  sleep 1
  # "Montar semestre" começa VAZIO: a grade da semana só ganha texto depois que
  # o aluno marca disciplinas. Medir a tela sem marcar nada deixava a agenda
  # inteira fora do validador — e era justamente lá que moravam os textos de
  # 9,5 px. Marca três antes de medir.
  if [ "$v" = "montar" ]; then
    node "$CLI" js "Array.from(document.querySelectorAll('#t-montar .sel')).slice(0,3).forEach(c=>c.click()); 'ok'" --node "$NODE" >/dev/null 2>&1
    sleep 1
  fi
  echo "===== $v ====="
  node "$CLI" js "$(cat "$JS")" --node "$NODE" 2>/dev/null \
    | python3 -I -c "
import sys, json
d = json.load(sys.stdin).get('valor') or {}
print(f\"  nota {d.get('nota')}/100 · {d.get('erros')} erros · {d.get('avisos')} avisos · {d.get('verificados')} elementos\")
vistos = set()
for a in d.get('achados', []):
    ch = (a['regra'], a['msg'][:40])
    if ch in vistos: continue
    vistos.add(ch)
    print(f\"   [{a['nivel']:5}] {a['regra']:10} {a['msg']}\")
    if a.get('alvo'): print(f\"            em {a['alvo']}  {a.get('texto') or ''}\")
"
done
