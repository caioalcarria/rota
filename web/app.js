/* Rota — frontend. Sem build, sem dependência.
   Cinco telas, uma pergunta cada:
     1. Quando eu me formo?        caminhos, plano e o cenário "e se eu reprovar"
     2. Montar o semestre          a ação: marcar, ver a semana, ver o choque
     3. O que falta?               cursando, obrigatórias e optativas
     4. Como a conta é feita?      as variáveis, o k-médias, o apriori e a fila
     5. Relatório                  a folha que sai do sistema
   Regra que manda em tudo: apoio à decisão, não recomendação. A tela
   hierarquiza, mostra a conta, aceita cenário e para. */

const S = {
  token: sessionStorage.getItem('rota_token') || null,
  d: null,
  vista: 'formatura',
  escolhidos: new Set(),
  alvo: null,
  caminhos: null,
  limites: null,
  pular: null,
  reprovar: '',
  seq: 0,
  seqBarra: 0,
  eSeCache: {},
  planoPorN: {},
};

const VISTAS = ['formatura', 'montar', 'falta', 'conta', 'relatorio'];
// endereços antigos (#decisao, #faltam…) continuam abrindo a tela certa: o
// script de captura e os links já publicados usam esses nomes
const APELIDO = { decisao: 'formatura', agora: 'falta', faltam: 'falta', optativas: 'falta' };

const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const n = (v, d = 0) => (v ?? 0).toLocaleString('pt-BR', { minimumFractionDigits: d, maximumFractionDigits: d });
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const plural = (q, um, varios) => `${q} ${q === 1 ? um : varios}`;
const ehTCC = (cod) => /^GICC/.test(cod || '');
// as frases do veredito vêm da API com ponto decimal ("aprovando 3.2"); na
// tela, vírgula. Só troca número de UMA casa colado em palavra, nunca
// semestre ("2028.2" tem quatro dígitos antes do ponto).
const virgula = (s) => String(s || '').replace(/(^|[^\d.])(\d{1,2})\.(\d)(?!\d)/g, '$1$2,$3');

// "Seg 20:20 · Seg 21:15 · Qua 20:20…" é ruído. Agrupa por dia e mostra a faixa.
function h(horarios) {
  if (!(horarios || []).length) return '—';
  const porDia = new Map();
  horarios.forEach(x => {
    const d = (x.dia || '').slice(0, 3);
    const f = porDia.get(d) || { ini: x.inicio, fim: x.fim };
    if (x.inicio < f.ini) f.ini = x.inicio;
    if (x.fim > f.fim) f.fim = x.fim;
    porDia.set(d, f);
  });
  const faixas = [...porDia.values()];
  const igual = faixas.every(f => f.ini === faixas[0].ini && f.fim === faixas[0].fim);
  return igual
    ? `${[...porDia.keys()].join(', ')} ${faixas[0].ini}–${faixas[0].fim}`
    : [...porDia].map(([d, f]) => `${d} ${f.ini}–${f.fim}`).join(' · ');
}

// "2028.2" -> número que ordena; serve para comparar com o prazo máximo
const ordem = (p) => { const [a, s] = String(p || '').split('.').map(Number); return a * 2 + (s || 1); };
const somaSem = (p, k) => { const [a, b] = String(p).split('.').map(Number); const i = a * 2 + (b - 1) + k; return `${Math.floor(i / 2)}.${i % 2 + 1}`; };
const depoisDoPrazo = (c) => { const pm = S.d?.aluno?.prazo_maximo; return !!(pm && c && ordem(c) > ordem(pm)); };

async function api(caminho, corpo) {
  const r = await fetch(caminho, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + S.token },
    body: JSON.stringify(corpo || {}),
  });
  return r.json();
}

/* estado vazio: ícone acima do título, e o título diz o que fazer */
const ICONE_VAZIO = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"
  stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2"/>
  <path d="M3 9h18M8 14h8"/></svg>`;
function vazio(titulo, texto) {
  return `<div class="vazio">${ICONE_VAZIO}<div class="vazio-t">${esc(titulo)}</div>${
    texto ? `<div>${esc(texto)}</div>` : ''}</div>`;
}

/* `o.num` = colunas numéricas (alinhadas à direita); `o.cls` = classe por
   coluna; `o.empilha` = no celular a linha vira ficha em vez de rolar de lado.
   Aceita também só o array de colunas numéricas, como antes. */
function tabela(cabecalho, linhas, o = {}) {
  if (Array.isArray(o)) o = { num: o };
  const num = o.num || [], cls = o.cls || {};
  if (!linhas.length) return vazio('Nada aqui.');
  const cl = (i) => {
    const c = [num.includes(i) ? 'num' : '', cls[i] || ''].filter(Boolean).join(' ');
    return c ? ` class="${c}"` : '';
  };
  // o.rotulos: no celular cada célula leva o nome da coluna na frente
  const rot = (i) => o.rotulos && !(cls[i] || '').includes('prim') && cabecalho[i]
    ? ` data-r="${esc(cabecalho[i])}"` : '';
  const corpo = linhas.map(l => {
    const lc = Array.isArray(l) ? '' : l.classe;
    const cels = Array.isArray(l) ? l : l.celulas;
    return `<tr class="${lc || ''}">${cels.map((c, i) => `<td${cl(i)}${rot(i)}>${c}</td>`).join('')}</tr>`;
  }).join('');
  return `<table${o.empilha ? ` class="empilha${o.rotulos ? ' rotula' : ''}"` : ''}><thead><tr>${cabecalho.map((c, i) => `<th${cl(i)}>${esc(c)}</th>`).join('')}</tr></thead>
    <tbody>${corpo}</tbody></table>`;
}

const codNome = (cod, nome) =>
  `<div class="duas"><span class="cod">${esc(cod)}</span><span class="nome">${esc(nome)}</span></div>`;

/* ------------------------------------------------------------- login
   `entrar()` é a única porta: na instância pública o formulário é removido,
   e o botão de demonstração não pode depender dele. */
async function entrar(usuario, senha, botao, rotulo) {
  const erro = $('#erro-login');
  if (botao) { botao.disabled = true; botao.textContent = 'entrando…'; }
  if (erro) erro.textContent = '';
  try {
    const r = await fetch('/api/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ usuario, senha }),
    });
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || 'não deu pra entrar');
    S.token = j.token; sessionStorage.setItem('rota_token', S.token);
    abrir();
  } catch (err) {
    if (erro) erro.textContent = err.message;
    else alert(err.message);
  } finally {
    if (botao) { botao.disabled = false; botao.textContent = rotulo; }
  }
}

$('#form-login').addEventListener('submit', (e) => {
  e.preventDefault();
  entrar($('#usuario').value, $('#senha').value, $('#btn-entrar'), 'Entrar com o SIGAA');
});
$('#btn-demo').addEventListener('click', () => {
  const b = $('#btn-demo');
  entrar('demo', 'demo', b, b.textContent);
});
$('#btn-sigaa').addEventListener('click', () => {
  const p = $('#sigaa-recusa'), aberto = p.classList.toggle('oculto') === false;
  $('#btn-sigaa').setAttribute('aria-expanded', String(aberto));
});

/* A instância pública (ROTA_MODO=demo) recusa login do SIGAA. Um campo de
   senha institucional num endereço público seria pior do que inútil: o
   formulário é REMOVIDO do documento, não só escondido, e no lugar dele fica
   a explicação e o caminho de rodar na própria máquina. Rodando local, o
   formulário aparece e funciona. Se /api/status não responder, vale o caminho
   seguro: nada de campo de senha. */
(async () => {
  let s = null;
  try { s = await (await fetch('/api/status')).json(); } catch (e) { s = null; }
  if (s && s.so_demo === false) {
    $('#sigaa-local').classList.remove('oculto');
    $('#sigaa-publico').remove();
  } else {
    $('#sigaa-local').remove();
    $('#sigaa-publico').classList.remove('oculto');
  }
})();

/* /?demo=1#montar entra e abre a tela; ?tema=claro abre no tema claro. Serve
   ao link do trabalho e à captura de tela por script, sempre no mesmo estado. */
{
  const q = new URLSearchParams(location.search);
  if (q.get('tema') === 'claro') {
    document.documentElement.dataset.tema = 'claro';
    $('#btn-tema').textContent = 'Tema escuro';
  }
  if (q.has('demo') && !sessionStorage.getItem('rota_token')) entrar('demo', 'demo', null, null);
}

$('#btn-sair').addEventListener('click', () => { sessionStorage.removeItem('rota_token'); location.reload(); });
$('#btn-tema').addEventListener('click', () => {
  const r = document.documentElement, claro = r.dataset.tema === 'claro';
  r.dataset.tema = claro ? 'escuro' : 'claro';
  $('#btn-tema').textContent = claro ? 'Tema claro' : 'Tema escuro';
});

/* A tela mora no endereço (#formatura, #montar…). Antes o menu não mudava o
   endereço: o F5 voltava sempre para a primeira tela e o "voltar" do celular
   saía do sistema. Agora cada troca de tela é uma entrada no histórico. */
const vistaDoEndereco = () => APELIDO[location.hash.slice(1)] || location.hash.slice(1);
function ir(v, o = {}) {
  v = APELIDO[v] || v;
  if (!VISTAS.includes(v)) v = 'formatura';
  S.vista = v;
  $$('.nav-i').forEach(x => {
    const on = x.dataset.v === v;
    x.classList.toggle('ativa', on);
    if (on) x.setAttribute('aria-current', 'page'); else x.removeAttribute('aria-current');
  });
  mostra(); botaoTopo();
  const url = location.pathname + location.search + '#' + v;
  if (o.historico === 'push' && location.hash !== '#' + v) history.pushState({ v }, '', url);
  if (o.historico === 'replace') history.replaceState({ v }, '', url);
  if (o.topo !== false) window.scrollTo(0, 0);
  // o relatório depende do caminho escolhido na tela 1: redesenha ao entrar
  if (v === 'relatorio') vRelatorio();
}
const peloEndereco = () => { if (S.d && vistaDoEndereco() !== S.vista) ir(vistaDoEndereco()); };
window.addEventListener('popstate', peloEndereco);
window.addEventListener('hashchange', peloEndereco);
$$('.nav-i').forEach(b => b.addEventListener('click', () => ir(b.dataset.v, { historico: 'push' })));
document.addEventListener('click', (ev) => {
  const a = ev.target.closest && ev.target.closest('[data-ir]');
  if (a) { ev.preventDefault(); ir(a.dataset.ir, { historico: 'push' }); }
  if (ev.target && ev.target.id === 'btn-imprimir') window.print();
  // atalhos dentro da tela: rolam até a parte, sem mexer no # (o # é a tela)
  const r = ev.target.closest && ev.target.closest('[data-rola]');
  if (r) {
    if (r.dataset.rola === 'topo') window.scrollTo({ top: 0, behavior: 'smooth' });
    else document.getElementById(r.dataset.rola)?.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }
  if (ev.target && ev.target.id === 'btn-topo') window.scrollTo({ top: 0, behavior: 'smooth' });
});

function mostra() {
  if (!S.d) return;
  VISTAS.forEach(v => $('#v-' + v).classList.toggle('oculto', v !== S.vista));
}

/* -------------------------------------------------------------- dados */
async function abrir() {
  $('#tela-login').classList.add('oculto');
  $('#tela-app').classList.remove('oculto');
  await carregar();
}

async function carregar() {
  $('#carregando').classList.remove('oculto');
  $$('.vista').forEach(v => v.classList.add('oculto'));
  try {
    const r = await fetch('/api/painel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + S.token },
      body: '{}',
    });
    if (r.status === 401) {
      sessionStorage.removeItem('rota_token');
      $('#tela-app').classList.add('oculto');
      $('#tela-login').classList.remove('oculto');
      const er = $('#erro-login');
      if (er) er.textContent = 'Sua sessão do SIGAA caiu. Entre de novo.';
      return;
    }
    if (r.status === 503) {
      $('#carregando').textContent = 'O SIGAA está congestionado agora. Tente de novo em alguns instantes.';
      return;
    }
    const j = await r.json();
    if (!r.ok) throw new Error(j.detail || 'erro');
    S.d = j;
  } catch (e) { $('#carregando').textContent = 'erro: ' + e.message; return; }
  $('#carregando').classList.add('oculto');

  const q = new URLSearchParams(location.search);
  let alvo = (location.hash || '').replace('#', '');
  // links antigos "#decisao&rolar=grupos": os blocos de mineração moraram na
  // tela de Decisão e agora moram em "Como a conta é feita"
  if (['grupos', 'cooferta', 'fila'].includes(q.get('rolar'))) alvo = 'conta';
  render();
  ir(alvo || 'formatura', { historico: 'replace', topo: false });

  // &marcar=3 marca as três primeiras disciplinas em "Montar o semestre": a
  // grade da semana só mostra algo depois de o aluno marcar
  const marcar = parseInt(q.get('marcar'), 10);
  // cada clique redesenha a tabela: o checkbox antigo sai do documento e um
  // checkbox fora do documento não dispara 'change'. Por isso busca de novo.
  if (marcar > 0) setTimeout(() => { for (let i = 0; i < marcar; i++) { const c = $$('#t-montar .sel:not(:checked)')[0]; if (c) c.click(); } }, 400);

  // &rolar=id posiciona a página num bloco; espera o bloco ter conteúdo
  const rolar = q.get('rolar');
  if (rolar) {
    let t = 0;
    const tenta = () => {
      const el = document.getElementById(rolar);
      if (el && el.offsetHeight > 80) { el.scrollIntoView({ block: 'start' }); return; }
      if (++t < 60) setTimeout(tenta, 200);
    };
    tenta();
  }
}

/* De que semestre vêm estes dados. A matrícula do semestre atual já
   aconteceu: a lista serve de referência, não de cardápio. */
function fonteDosDados(extra) {
  const o = S.d.oferta || {};
  const de = o.oferta_de || S.d.aluno.semestre;
  return `<p class="fonte">Turmas e horários de <b>${esc(de)}</b>, como referência: a oferta
    de <b>${esc(o.semestre_alvo || '')}</b> ainda não saiu.</p>`;
}

const linha = (cat) => (S.d.integralizacao.carga_horaria || [])
  .find(x => (x.categoria || '').toLowerCase().startsWith(cat)) || {};

function render() {
  const a = S.d.aluno;
  $('#quem').innerHTML = `<b>${esc(a.nome_abreviado || a.nome)}</b>
    ${esc(a.curso)} · ${a.periodo_letivo}º período · ${esc(a.semestre)}`;
  vFormatura(); vMontar(); vFalta(); vConta(); vRelatorio();
}

/* ===================================================================
   1. QUANDO EU ME FORMO?
   Cada caminho é uma data de formatura e o que ela custa em matérias por
   semestre. O aluno compara com o próprio ritmo e escolhe; o plano e o
   cenário de reprovação respondem à escolha dele.
   =================================================================== */
async function vFormatura() {
  const d = S.d, o = d.oferta || {};
  if (!S.caminhos) {
    const j = await api('/api/caminhos');
    if (j.detail) { $('#caminhos').innerHTML = vazio('Não deu para calcular os caminhos.', j.detail); return; }
    S.caminhos = j.caminhos || [];
    S.media = j.media_aprovadas_por_semestre;
    S.ritmo = j.ritmo || null;
    S.maisCedo = j.mais_cedo_possivel;
    S.inicio = j.inicio_do_plano;
    // Abre marcado o MAIS CEDO QUE CABE no ritmo do aluno E termina até o
    // prazo máximo. Antes abria no segundo da lista (2028.2, 5 por semestre),
    // que a própria tela chamava de "arriscado": a primeira coisa vista era um
    // plano que o histórico dele não sustenta. Caminho além do prazo não é
    // opção, então não abre marcado nem quando é o de carga mais leve. A regra
    // está escrita na tela.
    const noPrazo = S.caminhos.filter(c => c.diante_do_prazo !== 'passa');
    const cabe = noPrazo.filter(c => c.folga >= 0);
    const folgado = (noPrazo.length ? noPrazo : S.caminhos).slice().sort((a, b) => b.folga - a.folga)[0];
    S.alvo = S.alvo || (cabe[0] || folgado || {}).alvo;
    vConta();   // a tela 4 mostra o ritmo, que só chega aqui
  }
  const mt = d.situacao.materias;
  $('#r-formatura').innerHTML = `Faltam <b>${mt.total_a_cursar} matérias</b> (${mt.obrigatorias_a_cursar}
    obrigatórias, cerca de ${mt.optativas_a_cursar} optativas). Ritmo: <b>${n(S.media, 1)} por semestre</b>.
    Prazo máximo: <b>${esc(d.aluno.prazo_maximo || '—')}</b>. Todo caminho começa em
    <b>${esc(o.semestre_alvo || S.inicio || '')}</b>.`;
  desenhaCaminhos();
}

/* O rótulo do caminho junta a carga contra o ritmo E a data contra o prazo
   máximo, o mesmo juízo do veredito (_veredito em app.py). Antes só a carga
   entrava: o 2031.2, com 2 por semestre, saía "cabe no seu ritmo" em verde
   enquanto o plano embaixo avisava que ele passa do prazo. */
function leituraCaminho(c) {
  const f = c.folga, acima = n(Math.abs(f), 1);
  const pm = S.d?.aluno?.prazo_maximo;
  const lado = c.diante_do_prazo || (depoisDoPrazo(c.alvo) ? 'passa' : null);
  if (lado === 'passa') return { cls: 'f-ri', txt: f >= 0
    ? `abaixo do seu ritmo, mas passa do prazo (${pm})` : `passa do prazo máximo (${pm})` };
  const noLimite = lado === 'no_limite';
  if (f >= 0) return noLimite ? { cls: 'f-ap', txt: 'cabe no seu ritmo, mas termina no prazo máximo' }
                              : { cls: 'f-ok', txt: 'cabe no seu ritmo' };
  const e = noLimite ? ', e termina no prazo máximo' : '';
  return f >= -1.5 ? { cls: 'f-ap', txt: `apertado: ${acima} acima do seu ritmo${e}` }
                   : { cls: 'f-ri', txt: `arriscado: ${acima} acima do seu ritmo${e}` };
}

function desenhaCaminhos() {
  $('#caminhos').innerHTML = S.caminhos.map(c => {
    const l = leituraCaminho(c), on = c.alvo === S.alvo;
    return `<button class="cam ${on ? 'on' : ''}" role="radio" aria-checked="${on}" data-alvo="${esc(c.alvo)}">
      <span class="cam-d">${esc(c.alvo)}</span>
      <span class="cam-u">${plural(c.semestres, 'semestre', 'semestres')}</span>
      <span class="cam-n">${c.por_semestre}</span>
      <span class="cam-u">matérias por semestre</span>
      <span class="cam-f ${l.cls}">${l.txt}</span>
    </button>`;
  }).join('');
  $$('.cam').forEach(b => b.addEventListener('click', () => {
    if (S.alvo === b.dataset.alvo) return;
    S.alvo = b.dataset.alvo; S.reprovar = '';
    desenhaCaminhos(); vVariaveis();
  }));
  desenhaPlano();
}

async function desenhaPlano() {
  const seq = ++S.seq, alvo = S.alvo;
  if (!alvo) return;
  const restr = { limites: S.limites || null, pular: S.pular || null };
  $('#plano').innerHTML = '<p class="fraco">calculando…</p>';

  const base = await api('/api/plano', { alvo, ...restr });
  if (seq !== S.seq) return;
  if (base.detail) { $('#plano').innerHTML = vazio('Não deu para montar o plano.', base.detail); return; }
  S.planoBase = base;
  const carga = base.carga_necessaria || 8;

  let mostrado = base, cen = null;
  if (S.reprovar) {
    cen = await api('/api/plano', { alvo, por_semestre: carga, reprovar: [S.reprovar], ...restr });
    if (seq !== S.seq) return;
    if (!cen.detail) mostrado = cen; else cen = null;
  }

  // com uma reprovação escolhida, o plano mostrado é o RECALCULADO: o título
  // diz isso, senão "até 2028.2" aparecia sob o veredito do caminho de 2028.1
  $('#plano-t').textContent = cen
    ? `O plano refeito com ${S.reprovar} reprovada: até ${mostrado.conclusao}`
    : `O plano até ${mostrado.conclusao}, semestre a semestre`;
  $('#plano-v').textContent = virgula((base.comparacao || {}).veredito);
  grafico(mostrado, cen);
  plano(mostrado, cen);
  cenario(carga, base, cen, restr, seq);
}

/* O único gráfico que ficou: o que sustenta a decisão. Ele põe lado a lado o
   que o caminho pede (as barras) e o que você costuma aprovar (a linha). O de
   "quanto do curso fica concluído" saiu: é uma reta até 100% que não muda
   nenhuma escolha. Em HTML, não SVG, para o texto ficar no tamanho real. */
function grafico(p, cen) {
  const sems = p.semestres || [];
  const ritmo = S.media || 0;
  const topo = Math.max(ritmo, ...sems.map(s => s.componentes.length), 1) * 1.08;
  const cols = sems.map(s => {
    const tot = s.componentes.length;
    const ob = s.obrigatorias ?? s.componentes.filter(x => x.tipo !== 'optativa').length;
    const op = tot - ob;
    const seg = (q, cls) => q ? `<i class="${cls}" style="height:${(q / tot) * 100}%"></i>` : '';
    return `<div class="gr-col">
      <div class="gr-barra" style="height:${(tot / topo) * 100}%">${seg(ob, 'gr-obr')}${seg(op, 'gr-opt')}</div>
    </div>`;
  }).join('');
  // a contagem fica no eixo, embaixo do semestre: em cima da barra ela batia
  // na linha tracejada sempre que a carga ficava perto do ritmo
  const eixo = sems.map(s => `<span><span class="longo">${esc(s.periodo)}</span><span class="curto">${
    esc(String(s.periodo).slice(2))}</span><b>${s.componentes.length}</b></span>`).join('');

  $('#gr-t').textContent = cen ? 'Carga por semestre neste cenário' : 'Carga por semestre neste caminho';
  $('#gr-s').innerHTML = S.ritmo ? 'Barra acima do tracejado: semestre acima do seu ritmo.' : '';
  $('#grafico').innerHTML = sems.length ? `
    <div class="gr" role="img" aria-label="${esc(sems.map(s => `${s.periodo}: ${s.componentes.length}`).join(', '))}; ritmo ${n(ritmo, 1)}">
      ${cols}
      <div class="gr-ritmo" style="bottom:calc((100% - var(--e5)) * ${(ritmo / topo).toFixed(4)})"></div>
    </div>
    <div class="gr-eixo">${eixo}</div>
    <div class="gr-leg">
      <span><i class="pt obrig"></i> obrigatórias</span>
      <span><i class="pt opt"></i> optativas</span>
      <span><i class="tr"></i> seu ritmo (${n(ritmo, 1)})</span>
      <span>número embaixo = matérias no semestre</span>
    </div>` : vazio('Sem semestres para mostrar.');
}

/* Semestre que depende de matéria de oferta PARCIAL (abre em menos de 95%
   dos semestres daquele lado do ano). O planejador aceita a partir de 50%,
   então pode juntar duas de 50% no mesmo semestre. A conta da chance conjunta
   não supõe nada: olha nos semestres do mesmo lado do ano, na matriz de
   oferta, em quantos TODAS abriram juntas. */
function riscoDeOferta(s) {
  const parc = (s.componentes || []).filter(x => x.chance_oferta != null && x.chance_oferta < 0.95);
  if (!parc.length) return null;
  const mz = S.d?.mineracao?.matriz_oferta;
  const lado = String(s.periodo).split('.')[1];
  let juntas = null, de = null;
  if (mz && mz.periodos?.length && parc.every(x => mz.abriu[x.codigo])) {
    const mesmos = mz.periodos.filter(p => p.split('.')[1] === lado);
    de = mesmos.length;
    juntas = mesmos.filter(p => parc.every(x => mz.abriu[x.codigo].includes(p))).length;
    // a contagem crua de cada uma, para não mostrar só a porcentagem ponderada
    parc.forEach(x => { x.abriu_k = mesmos.filter(p => mz.abriu[x.codigo].includes(p)).length; x.abriu_n = de; });
  }
  return { parc, juntas, de, lado: lado === '1' ? 'ímpares' : 'pares' };
}
function textoRisco(r) {
  const lista = r.parc.map(x => `<b>${esc(x.codigo)}</b> (${x.abriu_n ? `abriu em ${x.abriu_k} de ${x.abriu_n} ${r.lado}, ` : ''}chance ponderada ${Math.round(100 * x.chance_oferta)}%)`).join(', ');
  const um = r.parc.length === 1;
  let t = `Oferta incerta: este semestre depende de ${plural(r.parc.length, 'matéria', 'matérias')} que
    não ${um ? 'abre' : 'abrem'} sempre neste lado do ano: ${lista}.`;
  if (!um && r.de) t += ` Nos ${r.de} semestres ${r.lado} analisados, ${r.parc.length === 2 ? 'as duas' : 'todas'}
    abriram juntas em <b>${r.juntas}</b>.`;
  return t;
}

function plano(p, cen) {
  const visto = new Set();
  const corpo = (p.semestres || []).map(s => {
    const pulado = (S.pular || []).includes(s.periodo);
    const lim = (S.limites || {})[s.periodo] || (S.planoBase || {}).carga_necessaria;
    const itens = s.componentes.map(x => {
      const tipo = x.tipo === 'optativa' ? 'opt' : (ehTCC(x.codigo) ? 'tcc' : 'obrig');
      // "todo semestre" e a vaga de optativa ("há várias") são iguais em todas
      // as linhas: viram uma frase na legenda em vez de repetir em cada matéria
      let nota = x.codigo === 'OPTATIVA' || /^ofertada todo semestre/.test(x.padrao_oferta || '') ? '' : (x.padrao_oferta || '');
      let cls = x.tipo === 'optativa' ? 'sem-opt' : '';
      if (cen && x.reprovada) nota = 'hipótese: cursa e reprova aqui';
      else if (cen && x.codigo === S.reprovar && visto.has(x.codigo)) cls += ' repete';
      if (cen && x.codigo === S.reprovar) visto.add(x.codigo);
      return `<div class="sem-item ${cls}">
        <i class="pt ${tipo}"></i>
        <span class="cod">${esc(x.codigo === 'OPTATIVA' ? 'optativa' : x.codigo)}</span>
        <span class="nm">${esc(x.codigo === 'OPTATIVA' ? 'qualquer optativa ofertada' : x.nome)}</span>
        ${nota ? `<span class="pq">${esc(nota)}</span>` : ''}
      </div>`;
    }).join('');
    return `<div class="sem">
      <div class="sem-cab">
        <span class="sem-per">${esc(s.periodo)}${riscoDeOferta(s) ? ' <span class="tag aviso">oferta incerta</span>' : ''}</span>
        <span class="sem-meta"><span>${plural(s.componentes.length, 'matéria', 'matérias')} · ${n(s.carga_horaria)} h</span>
          <label>máximo aqui
            <select class="lim-sel" data-per="${esc(s.periodo)}" aria-label="Máximo de matérias em ${esc(s.periodo)}">
              <option value="0" ${pulado ? 'selected' : ''}>não vou cursar</option>
              ${[1, 2, 3, 4, 5, 6, 7, 8].map(v => `<option value="${v}" ${!pulado && lim === v ? 'selected' : ''}>${v}</option>`).join('')}
            </select></label></span>
      </div>
      ${(() => { const r = riscoDeOferta(s); return r ? `<p class="aviso sem-risco">${textoRisco(r)}</p>` : ''; })()}
      ${s.componentes.length ? `<div class="sem-lista">${itens}</div>`
        : `<p class="fraco">${esc(s.nota || 'semestre sem matéria')}</p>`}
    </div>`;
  }).join('');
  const naoCoube = (p.nao_coube || []).length
    ? `<p class="aviso">Não couberam até ${esc(S.alvo)}: <b>${esc(p.nao_coube.map(x => x.codigo).join(', '))}</b>.</p>` : '';
  const pm = S.d.aluno.prazo_maximo;
  const prazo = depoisDoPrazo(p.conclusao)
    ? `<p class="aviso">Este plano termina em <b>${esc(p.conclusao)}</b>, depois do prazo máximo do curso
       (<b>${esc(pm)}</b>).</p>` : '';
  const incertos = (p.semestres || []).filter(riscoDeOferta).map(s => s.periodo);
  const resumoRisco = incertos.length ? `<p class="aviso">Este plano é incerto em
    <b>${plural(incertos.length, 'semestre', 'semestres')}</b> (${esc(incertos.join(', '))}): ${incertos.length === 1 ? 'ele depende' : 'eles dependem'} de
    matéria que não abre sempre. O plano pode propor um semestre que não acontece; o motivo está no semestre.</p>` : '';
  $('#plano').innerHTML = prazo + resumoRisco + corpo + naoCoube;
  // uma vez por código: no cenário de reprovação a matéria aparece duas vezes
  const itens = [...new Map((p.semestres || []).flatMap(s => s.componentes)
    .filter(x => x.codigo !== 'OPTATIVA' && x.padrao_oferta && !/^não abre turma/.test(x.padrao_oferta))
    .map(x => [x.codigo, x])).values()];
  const todas = itens.filter(x => /^ofertada todo semestre/.test(x.padrao_oferta));
  const nAn = (S.d.mineracao?.matriz_oferta?.periodos || []).length || 8;
  $('#leg-nota').innerHTML = [
    todas.length ? (todas.length === itens.length
      ? `As ${todas.length} disciplinas obrigatórias abriram nos ${nAn} semestres analisados.`
      : `${todas.length} das ${itens.length} disciplinas obrigatórias abriram nos ${nAn} semestres; as outras dizem quando abrem.`) : '',
    itens.some(x => x.chance_oferta != null && x.chance_oferta < 0.95)
      ? '"Abriu em k de n": semestres do mesmo lado do ano. Chance ponderada: os 2 mais recentes pesam o dobro.' : '',
  ].filter(Boolean).join(' ');

  $$('.lim-sel').forEach(el => el.addEventListener('change', () => {
    const per = el.dataset.per, v = Number(el.value);
    const pular = new Set(S.pular || []);
    if (v === 0) pular.add(per);
    else { pular.delete(per); S.limites = { ...(S.limites || {}), [per]: v }; }
    S.pular = [...pular];
    desenhaPlano();
  }));
}

/* "E se eu reprovar?" — análise de sensibilidade, como CONTROLE do plano.
   A lista diz quanto cada reprovação custaria no ritmo deste caminho; ao
   escolher uma, o plano acima passa a mostrar o cenário com ela refeita. */
async function cenario(carga, base, cen, restr, seq) {
  const chave = JSON.stringify([carga, restr]);
  let e = S.eSeCache[chave];
  if (!e) {
    e = await api('/api/e-se', { por_semestre: carga, ...restr });
    if (seq !== S.seq) return;
    if (!e.detail) S.eSeCache[chave] = e;
  }
  if (e.detail) { $('#cenario').innerHTML = `<p class="fraco">${esc(e.detail)}</p>`; return; }

  const custo = (x) => x.atraso_semestres > 0 ? `+${plural(x.atraso_semestres, 'semestre', 'semestres')}` : 'sem atraso';
  const opcoes = e.impactos.map(x => `<option value="${esc(x.codigo)}" ${x.codigo === S.reprovar ? 'selected' : ''}>
      ${esc(x.codigo)} (${custo(x)}) · ${esc(x.nome || '')}</option>`).join('');

  let r;
  if (cen) {
    const de = base.conclusao, para = cen.conclusao;
    const d = (e.impactos.find(x => x.codigo === S.reprovar) || {}).atraso_semestres;
    r = de === para
      ? `Reprovando <b>${esc(S.reprovar)}</b>, a formatura continua em <b>${esc(de)}</b>: o plano tem
         folga para refazer a matéria. O plano abaixo já mostra a matéria refeita.`
      : `Reprovando <b>${esc(S.reprovar)}</b>, a formatura passa de <b>${esc(de)}</b> para
         <b>${esc(para)}</b>${d ? ` (+${plural(d, 'semestre', 'semestres')})` : ''}. O plano abaixo já mostra a matéria refeita.`;
  } else {
    r = esc(fraseESe(e));
  }
  $('#cenario').innerHTML = `
    <label for="sel-reprovar">E se eu reprovar em</label>
    <select id="sel-reprovar">
      <option value="">nenhuma (o plano como está)</option>${opcoes}
    </select>
    <p class="cenario-r">${r}</p>`;
  $('#sel-reprovar').addEventListener('change', (ev) => { S.reprovar = ev.target.value; desenhaPlano(); });
}

/* A frase da API lista "o que custa mais caro". Quando TODAS custam o mesmo
   (ritmo sem folga), a lista de onze códigos não informa nada: diz-se isso. */
function fraseESe(e) {
  const im = e.impactos || [], custam = im.filter(x => x.atraso_semestres > 0);
  if (!custam.length) return virgula(e.frase);
  const pior = Math.max(...custam.map(x => x.atraso_semestres));
  const quais = custam.filter(x => x.atraso_semestres === pior).map(x => x.codigo);
  const sem = plural(pior, 'semestre', 'semestres');
  if (quais.length === im.length)
    return `Com ${e.por_semestre} por semestre não há folga: reprovar em qualquer uma das ${im.length} custa ${sem}.`;
  if (quais.length <= 4)
    return `Com ${e.por_semestre} por semestre, reprovar em ${quais.join(', ')} é o que custa mais: ${sem} a mais.`
      + (custam.length > quais.length ? ` Outras ${custam.length - quais.length} custam menos.` : '');
  return `Com ${e.por_semestre} por semestre, ${quais.length} das ${im.length} custam ${sem} a mais se reprovadas.`;
}

/* ===================================================================
   2. MONTAR O SEMESTRE
   =================================================================== */
function disponiveis() {
  const d = S.d;
  return [...d.obrigatorias_ofertadas, ...d.optativas].filter(c => c.turmas.length);
}

function slots(c) {
  const t = c.turmas[0] || {};
  return new Set((t.horarios || []).map(x => `${x.dia_numero}-${x.turno}-${x.aula}`));
}

/* O que esta matéria pesa na decisão — só fato verificável. Aqui havia um
   escore 0–100; saiu porque a validação mostrou que ele não previa nada
   (AUC 0,57). Ficou o que o SIGAA diz. */
function porQueImporta(c) {
  const t = [];
  const nd = (c.desbloqueia || []).length;
  if (nd) t.push(`<span class="tag ok" title="${esc((c.desbloqueia || []).join(', '))}">destrava ${nd}</span>`);
  const po = c.padrao_oferta || '';
  if (po.startsWith('costuma abrir')) t.push(`<span class="tag aviso" title="${esc(po)}">abre 1× por ano</span>`);
  if (c.atraso > 0) t.push(`<span class="tag off" title="nível ${esc(String(c.nivel))} da matriz; seu semestre de avaliação é o ${esc(String((S.d.fila || {}).sa || '—'))}º">${c.atraso} sem. atrasada</span>`);
  return t.length ? `<div class="tags">${t.join('')}</div>` : '<span class="fraco">—</span>';
}

function vMontar() {
  const lista = disponiveis();
  $('#r-montar').innerHTML = `Marque o que pensa pegar: a semana se monta ao lado e o choque
    aparece em vermelho. <b>${lista.length}</b> liberadas.`;
  $('#fonte-montar').innerHTML = fonteDosDados();

  // conflito calculado contra as OUTRAS marcadas, inclusive para quem já está
  // marcado: senão a linha que é o problema fica com cara de normal
  const donoDoSlot = new Map();
  S.escolhidos.forEach(cod => {
    const c = lista.find(x => x.codigo === cod);
    if (c) slots(c).forEach(s => (donoDoSlot.get(s) || donoDoSlot.set(s, []).get(s)).push(cod));
  });
  const conflitaCom = (c) => {
    const outros = new Set();
    slots(c).forEach(s => (donoDoSlot.get(s) || []).forEach(cod => { if (cod !== c.codigo) outros.add(cod); }));
    return [...outros];
  };

  $('#t-montar').innerHTML = tabela(
    ['', 'Disciplina', 'Quando', 'Por que importa'],
    lista.map(c => {
      const marcado = S.escolhidos.has(c.codigo);
      const colide = marcado || S.escolhidos.size ? conflitaCom(c) : [];
      const t = c.turmas[0] || {};
      return {
        classe: colide.length ? 'conflito' : (marcado ? 'escolhida' : ''),
        celulas: [
          `<input type="checkbox" class="sel" data-cod="${esc(c.codigo)}"
             aria-label="Marcar ${esc(c.codigo)} ${esc(c.nome)}" ${marcado ? 'checked' : ''}>`,
          `<div class="duas"><span class="cod">${esc(c.codigo)}</span><span class="nome">${esc(c.nome)}</span>
            <span class="fraco">${c.natureza === 'OBRIGATORIO' ? 'obrigatória' : 'optativa'} · ${c.carga_horaria} h</span></div>`,
          `<div class="duas"><span>${esc(h(t.horarios))}</span><span class="fraco">${
            esc((t.docentes || []).join(', ')) || '—'}</span>${colide.length
            ? `<span class="tag err" style="align-self:flex-start;margin-top:4px">choca com ${esc(colide.join(', '))}</span>` : ''}</div>`,
          porQueImporta(c),
        ],
      };
    }), { cls: { 0: 'ck', 1: 'prim' }, empilha: true });

  $$('#t-montar .sel').forEach(el => el.addEventListener('change', () => {
    el.checked ? S.escolhidos.add(el.dataset.cod) : S.escolhidos.delete(el.dataset.cod);
    vMontar();
  }));
  barra(lista);
  agenda(lista);
}

const DIAS_AG = [[2, 'Seg'], [3, 'Ter'], [4, 'Qua'], [5, 'Qui'], [6, 'Sex'], [7, 'Sáb']];
const TURNOS_AG = [['M', 1, 6], ['T', 1, 6], ['N', 1, 4]];

function agenda(lista) {
  const sel = [...S.escolhidos].map(c => lista.find(x => x.codigo === c)).filter(Boolean);
  if (!sel.length) {
    $('#agenda-s').textContent = '';
    $('#agenda').innerHTML = vazio('Nenhuma disciplina marcada.', 'Marque uma na lista para ver a semana se montar aqui.');
    return;
  }
  const ocup = new Map();   // slot -> códigos (mais de um = choque)
  sel.forEach(c => (c.turmas[0] || {}).horarios?.forEach(x => {
    const k = `${x.dia_numero}-${x.turno}-${x.aula}`;
    ocup.set(k, [...(ocup.get(k) || []), c.codigo]);
  }));
  const faixas = [];
  TURNOS_AG.forEach(([t, de, ate]) => {
    for (let a = de; a <= ate; a++) if (DIAS_AG.some(([d]) => ocup.has(`${d}-${t}-${a}`))) faixas.push([t, a]);
  });
  const dias = new Set(); ocup.forEach((_, k) => dias.add(k.split('-')[0]));
  const idx = new Map(sel.map((c, i) => [c.codigo, i + 1]));

  let g = `<div class="ag-grade" role="img" aria-label="Grade da semana"><div class="ag-h"></div>` +
    DIAS_AG.map(([, nome]) => `<div class="ag-h">${nome}</div>`).join('');
  faixas.forEach(([t, a]) => {
    g += `<div class="ag-hora">${t}${a}</div>`;
    DIAS_AG.forEach(([d]) => {
      const cods = ocup.get(`${d}-${t}-${a}`) || [];
      if (!cods.length) { g += '<div class="ag-c"></div>'; return; }
      const choca = cods.length > 1;
      // na célula vai o NÚMERO da disciplina (legenda embaixo): o código
      // inteiro não cabe a 14 px numa célula de celular e saía "MATC7"
      g += `<div class="ag-c ${choca ? 'ch' : 'on'}" title="${esc(cods.join(' × '))}">
        <span class="ag-cod">${choca ? '!' : idx.get(cods[0])}</span></div>`;
    });
  });
  g += '</div>';
  g += `<div class="ag-lista">${sel.map(c => `<div class="ag-i"><span class="ag-n">${idx.get(c.codigo)}</span>
    <span><b>${esc(c.codigo)}</b> ${esc(c.nome)}</span></div>`).join('')}
    ${[...ocup.values()].some(v => v.length > 1) ? '<div class="ag-i"><span class="ag-n" style="background:var(--err);color:var(--err-sobre)">!</span><span>choque de horário</span></div>' : ''}</div>`;
  $('#agenda-s').innerHTML = `<b>${plural(dias.size, 'dia', 'dias')}</b> na universidade ·
    <b>${sel.reduce((s2, c) => s2 + c.carga_horaria, 0)} h</b>`;
  $('#agenda').innerHTML = g;
}

/* A formatura daqui sai da MESMA conta da tela "Quando eu me formo": o
   planejador, com pré-requisito e oferta, pegando por semestre o número de
   matérias marcadas. Antes ela dividia as HORAS pendentes pela carga marcada
   e contradizia a tela 1 justamente no ritmo real do aluno (2030.1 contra
   2029.2 com 3 marcadas), e passava do prazo máximo sem aviso. */
async function barra(lista) {
  const sel = [...S.escolhidos].map(c => lista.find(x => x.codigo === c)).filter(Boolean);
  const ch = sel.reduce((s, c) => s + c.carga_horaria, 0);
  const dono = new Map(); const choques = [];
  sel.forEach(c => slots(c).forEach(s => {
    if (dono.has(s) && dono.get(s) !== c.codigo) {
      const par = `${dono.get(s)} × ${c.codigo}`;
      if (!choques.includes(par)) choques.push(par);
    } else dono.set(s, c.codigo);
  }));
  // toda chamada vira a "mais recente": uma resposta atrasada de uma marcação
  // anterior não pode sobrescrever a barra (era o que acontecia ao marcar três
  // seguidas com choque: ficava "Marcadas 1" e a formatura de 1 por semestre)
  const seq = ++S.seqBarra;
  // semestre que não pode ser cursado não tem previsão de formatura
  const valido = sel.length > 0 && choques.length === 0;
  const nps = Math.min(sel.length, 8);
  const desenha = (formatura, aviso) => {
    $('#barra').innerHTML = `
      <div class="bf-item"><span class="bf-r">Marcadas</span><span class="bf-v">${sel.length}</span></div>
      <div class="bf-item"><span class="bf-r">Carga</span><span class="bf-v">${ch} h</span></div>
      <div class="bf-item"><span class="bf-r">${valido ? `Formatura com ${nps} por semestre` : 'Formatura'}</span>
        <span class="bf-v">${esc(formatura)}</span></div>
      ${valido ? '<p class="bf-nota">a mesma conta de "Quando eu me formo"</p>' : ''}
      ${aviso ? `<div class="bf-aviso">${aviso}</div>` : ''}
      <button type="button" class="btn-ghost" data-rola="topo" aria-label="Voltar ao topo, onde fica o menu">↑ Topo</button>`;
  };
  if (!valido) {
    // curto de propósito: no celular esta barra fica fixa embaixo da tela
    desenha('—', choques.length ? `Choque de horário: ${esc(choques.join(' · '))}. Desmarque uma para ver a formatura.` : '');
    return;
  }
  desenha('…');
  let p = S.planoPorN[nps];
  if (!p) {
    p = await api('/api/plano', { por_semestre: nps });
    if (!p.detail) S.planoPorN[nps] = p;
  }
  if (seq !== S.seqBarra) return;
  if (p.detail) { desenha('—', esc(p.detail)); return; }
  const pm = S.d.aluno.prazo_maximo;
  desenha(p.conclusao, depoisDoPrazo(p.conclusao)
    ? `Passa do prazo máximo (${esc(pm)}).` : '');
}

/* ===================================================================
   3. O QUE FALTA?
   Eram três telas ("Cursando agora", "Falta pegar", "Optativas") para a
   mesma pergunta. Agora é uma tela com três seções.
   =================================================================== */
function vFalta() {
  const d = S.d, sit = d.situacao, hs = sit.horas, m = sit.materias;
  $('#r-falta').innerHTML = `Faltam <b>${m.total_a_cursar} matérias</b> (${m.obrigatorias_a_cursar}
    obrigatórias, cerca de ${m.optativas_a_cursar} optativas), fora as ${d.cursando.length} que você cursa agora.`;

  const barraP = (pct, cheia) => `<div class="barra-p"><i class="${cheia ? 'cheia' : ''}" style="width:${Math.min(100, pct)}%"></i></div>`;
  $('#progresso').innerHTML = `<div class="prog">
    <div><div class="prog-r">Curso concluído</div>
      <div class="prog-v">${n(sit.percentual, 1)}%</div>${barraP(sit.percentual)}
      <div class="prog-x">${n(hs.concluido)} de ${n(hs.exigido)} h · faltam ${n(hs.pendente)} h</div></div>
    ${sit.categorias.map(c => `<div><div class="prog-r">${esc(c.nome)}</div>
      <div class="prog-v">${n(c.feito_h)}<small> / ${n(c.exigido_h)} h</small></div>${barraP(c.percentual, c.concluida)}
      <div class="prog-x">${c.concluida ? (c.excedente_h ? `concluída · ${n(c.excedente_h)} h a mais não contam` : 'concluída')
        : `faltam ${n(c.pendente_h)} h${c.materias_a_fazer != null ? ' · ' + plural(c.materias_a_fazer, 'matéria', 'matérias') : ''}`}</div></div>`).join('')}
  </div>`;
  $('#fonte-falta').innerHTML = fonteDosDados();

  // cursando agora
  $('#h-cursando').textContent = `Cursando agora (${d.cursando.length})`;
  $('#t-cursando').innerHTML = tabela(['Disciplina', 'CH', 'Quando', 'Onde'],
    d.cursando.map(c => [
      codNome(c.codigo, c.nome), `${c.carga_horaria} h`,
      `<div class="duas"><span>${esc((c.encontros || []).map(e => `${(e.dia || '').slice(0, 3)} ${e.inicio}–${e.fim}`).join(' · ')) || '—'}</span>
        <span class="fraco">${esc((c.docentes || []).join(', '))}</span></div>`,
      `<span class="fraco">${esc(c.local || '—')}</span>`,
    ]), { num: [1], cls: { 0: 'prim' }, empilha: true });

  // obrigatórias que faltam
  const ordem = p => p.matriculado ? 0 : (p.ofertada && p.apto ? 1 : (p.ofertada ? 2 : 3));
  const nf = filaPorCodigo();
  $('#h-faltam').textContent = `Obrigatórias que faltam (${d.pendentes.length})`;
  $('#t-faltam').innerHTML = tabela(['Disciplina', 'CH', 'Neste semestre', 'Fila', 'Pré-requisito'],
    d.pendentes.slice().sort((a, b) => ordem(a) - ordem(b)).map(p => [
      codNome(p.codigo, p.nome), `${p.carga_horaria} h`, situacao(p), tagFila(nf[p.codigo]),
      p.faltando && p.faltando.length
        ? `<span class="tag err">falta ${esc(p.faltando.join(', '))}</span>`
        : `<span class="fraco" title="${esc(p.pre_requisitos || '')}">${p.pre_requisitos ? 'cumprido' : '—'}</span>`,
    ]), { num: [1], cls: { 0: 'prim' }, empilha: true });

  // optativas
  const opt = linha('optat'), podem = d.optativas.filter(o => o.turmas.length);
  $('#h-optativas').textContent = `Optativas ofertadas para você (${podem.length})`;
  const emCurso = m.optativas_cursando_h || 0;
  $('#s-optativas').innerHTML = `Faltam <b>${n(Math.max(0, (opt.pendente || 0) - emCurso))} h</b> de
    optativas${emCurso ? ` (${n(opt.pendente)} h menos ${n(emCurso)} h em curso)` : ''}. Qualquer uma conta.`;
  $('#t-optativas').innerHTML = podem.length ? tabela(['Disciplina', 'CH', 'Quando', 'Por que importa'],
    podem.map(o => {
      const t = o.turmas[0] || {};
      return [codNome(o.codigo, o.nome), `${o.carga_horaria} h`,
        `<div class="duas"><span>${esc(h(t.horarios))}</span><span class="fraco">${esc((t.docentes || []).join(', ')) || '—'}</span></div>`,
        porQueImporta(o)];
    }), { num: [1], cls: { 0: 'prim' }, empilha: true }) : vazio('Nenhuma optativa ofertada para o seu curso neste semestre.');
}

function situacao(p) {
  if (p.matriculado) return '<span class="tag ok">cursando</span>';
  if (p.ofertada && p.apto) return '<span class="tag ok">pode pegar</span>';
  if (p.ofertada && p.apto === false) return '<span class="tag err">travada</span>';
  return '<span class="tag off">não ofertada</span>';
}

/* fila de vaga (Resolução CAE 02/2017): destravar o pré-requisito e
   CONSEGUIR a vaga são problemas diferentes */
function filaPorCodigo() {
  const m = {};
  ((S.d || {}).fila?.componentes || []).forEach(c => { m[c.codigo] = c; });
  return m;
}
function tagFila(c) {
  if (!c) return '<span class="fraco">—</span>';
  const cor = c.nivel <= 2 ? 'ok' : c.nivel === 3 ? 'aviso' : 'off';
  return `<span class="tag ${cor}" title="${esc(c.rotulo)} — ${esc(c.porque)}">nível ${esc(c.romano)}</span>`;
}

/* ===================================================================
   4. COMO A CONTA É FEITA?
   O pedido: "entender facilmente onde estão as variáveis". Cada variável
   com o nome em português, o valor de agora, de onde o SIGAA tira e qual
   função usa. O k-médias e o apriori moram aqui, cada um ao lado da
   entrada que consome e com o número de qualidade à mostra.
   =================================================================== */
function vConta() {
  if (!S.d) return;
  vVariaveis(); vGrupos(); vCooferta(); vFila();
}

function vVariaveis() {
  const d = S.d, sit = d.situacao, hs = sit.horas, m = sit.materias, f = d.fila || {};
  const of = d.mineracao?.associacao || {};
  const ritmo = S.ritmo;
  const cam = (S.caminhos || []).find(c => c.alvo === S.alvo);
  const travadas = d.pendentes.filter(p => (p.faltando || []).length);
  const optCh = linha('optat');

  const al = d.aluno, susp = al.suspensoes || [];
  const prorrog = parseInt(al.prorrogacoes, 10) || 0;
  // o prazo refeito a partir do campo da estrutura: entrada + (N - 1)
  // semestres, mais um por trancamento total e por prorrogação
  const prazoConta = al.prazo_maximo_semestres && al.ingresso
    ? somaSem(al.ingresso, al.prazo_maximo_semestres - 1 + susp.length + prorrog) : null;
  const cs = S.caminhos || [];
  const noPrazo = cs.filter(c => c.diante_do_prazo === 'no_limite').map(c => c.alvo);
  const alem = cs.filter(c => c.diante_do_prazo === 'passa').map(c => c.alvo);
  const optEmCurso = m.optativas_cursando_h || 0;
  const optPend = (sit.por_categoria?.optativas?.pendente) ?? optCh.pendente;

  const V = [
    {
      nome: 'Ritmo de aprovação', o: 'aprovadas por semestre',
      valor: ritmo ? `${n(ritmo.media, 1)} por semestre` : '…',
      det: ritmo ? ritmo.semestres.map(x => `${x.periodo}: ${x.aprovadas}`).join(' · ') : '',
      fonte: `Histórico: últimos ${ritmo ? ritmo.janela : 5} semestres cursados, sem trancamento total e sem o semestre em curso.`,
      usa: '<code>_ritmo()</code> · carga do caminho menos ritmo: cabe, apertado ou arriscado.',
    },
    {
      nome: 'Prazo máximo do curso', o: 'último semestre para se formar',
      valor: al.prazo_maximo || '—',
      det: [al.prazo_maximo_semestres ? `${al.prazo_maximo_semestres} semestres desde ${al.ingresso}${susp.length
        ? ` + ${susp.length} de trancamento total` : ''}${prorrog ? ` + ${prorrog} de prorrogação` : ''}${prazoConta
        ? (prazoConta === al.prazo_maximo ? ' (confere)' : ` = ${prazoConta}, o SIGAA diz ${al.prazo_maximo}`) : ''}` : '',
        noPrazo.length ? `termina nele: ${noPrazo.join(', ')}` : '', alem.length ? `passa dele: ${alem.join(', ')}` : '']
        .filter(Boolean).join(' · '),
      fonte: 'Estrutura curricular (<code>prazo_maximo</code>) e histórico (ingresso, trancamentos).',
      usa: '<code>_veredito()</code> · depois do prazo não é opção; no prazo, sem margem.',
    },
    {
      nome: 'Matérias por semestre', o: 'a carga, pelo caminho',
      valor: cam ? `${cam.por_semestre} no caminho ${cam.alvo}` : '…',
      det: 'a única variável que você escolhe',
      fonte: 'Você: o caminho, ou o "máximo aqui" de cada semestre.',
      usa: '<code>menor_carga_para()</code> · a menor carga, de 1 a 8, que fecha até a data.',
    },
    {
      nome: 'Carga horária', o: 'exigida, feita e faltando',
      valor: `${n(hs.pendente)} h faltando`,
      det: `${n(hs.concluido)} de ${n(hs.exigido)} h (${n(sit.percentual, 1)}%)`,
      fonte: 'Integralização: horas por categoria.',
      usa: '<code>resumo()</code> · o percentual; hora a mais numa categoria não cobre outra.',
    },
    {
      nome: 'Obrigatórias que faltam', o: 'o que o plano encaixa',
      valor: `${m.obrigatorias_a_cursar} matérias`,
      det: d.pendentes.map(p => p.codigo).join(', '),
      fonte: 'Integralização (<code>obrigatorios_pendentes</code>), sem as que você cursa e sem o ENADE.',
      usa: '<code>monta()</code> · uma a uma nos semestres.',
    },
    {
      nome: 'Optativas que faltam', o: 'vagas genéricas no plano',
      valor: `cerca de ${m.optativas_a_cursar}`,
      det: `${optEmCurso ? `(${n(optCh.pendente)} h − ${n(optEmCurso)} h em curso)` : `${n(optPend)} h`} ÷ ${m.optativa_ch_tipica} h`,
      fonte: 'Integralização (horas) e optativas ofertadas (carga mediana).',
      usa: '<code>monta()</code> · vagas de "qualquer optativa" depois das obrigatórias.',
    },
    {
      nome: 'Pré-requisitos', o: 'o que vem antes',
      valor: `${plural(travadas.length, 'matéria travada', 'matérias travadas')}`,
      det: travadas.length ? travadas.map(p => `${p.codigo} pede ${p.faltando.join(', ')}`).join(' · ') : 'nenhuma travada agora',
      fonte: 'Planejamento de matrícula: <code>requisitos</code> e <code>apto</code>.',
      usa: '<code>_liberado()</code> · só entra depois do pré-requisito.',
    },
    {
      nome: 'Padrão de oferta', o: 'quando cada matéria abre',
      valor: `${of.transacoes || '—'} semestres analisados`,
      det: (of.periodos || []).length ? `${of.periodos[0]} a ${of.periodos[of.periodos.length - 1]}` : '',
      fonte: 'Previsão de oferta: semestres com turma.',
      usa: '<code>sera_ofertada()</code> · matéria de par não vai para ímpar; os 2 semestres mais recentes de cada lado pesam o dobro. Entrada do apriori.',
    },
    {
      nome: 'Primeiro semestre do plano', o: 'de onde todo caminho parte',
      valor: S.inicio || d.oferta?.semestre_alvo || '—',
      det: `${d.aluno.semestre} já teve matrícula`,
      fonte: 'Semestre atual mais um.',
      usa: 'Todo o plano · o que você cursa agora conta como aprovado.',
    },
    {
      nome: 'Semestre de avaliação', o: 'contra o cronológico',
      valor: f.sa ? `${f.sa}º contra ${f.sc}º` : '—',
      det: f.sa ? (f.semestralizado ? 'semestralizado' : 'dessemestralizado') : '',
      fonte: 'Estrutura e histórico: 1º nível com mais da metade por cumprir.',
      usa: '<code>posicao()</code> · nível I a VI de cada pedido de vaga; e o atraso de cada matéria ("Montar" e k-médias), contado a partir dele.',
    },
    {
      nome: 'IAP', o: 'índice de aproveitamento',
      valor: f.desempate?.iap != null ? n(f.desempate.iap, 4) : '—',
      det: f.desempate ? `${plural(f.desempate.reprovacoes_por_falta, 'reprovação por falta', 'reprovações por falta')} · ${plural(f.desempate.trancamentos, 'trancamento', 'trancamentos')}` : '',
      fonte: 'Índices, recalculado e conferido com o oficial.',
      usa: '<code>posicao()</code> · desempate no mesmo nível da fila.',
    },
  ];

  $('#variaveis').innerHTML = `<div class="vars">
    <div class="var cab-var" aria-hidden="true"><div>Variável</div><div>Valor agora</div><div>De onde vem</div><div>Quem usa e para quê</div></div>
    ${V.map(v => `<div class="var">
      <div class="var-n">${esc(v.nome)}<span>${esc(v.o)}</span></div>
      <div class="var-v">${esc(v.valor)}${v.det ? `<span>${esc(v.det)}</span>` : ''}</div>
      <div class="var-f"><span class="var-rot">De onde vem: </span>${v.fonte}</div>
      <div class="var-u"><span class="var-rot">Quem usa: </span>${v.usa}</div>
    </div>`).join('')}
  </div>`;
}

/* Faixas de Kaufman e Rousseeuw (1990) para a silhueta média: acima de 0,70
   estrutura forte; de 0,51 a 0,70 razoável; de 0,26 a 0,50 fraca; até 0,25,
   nenhuma estrutura substancial. Antes, tudo de 0,25 a 0,50 saía "razoável" e
   0,257 aparecia como separação razoável: era generoso com o próprio método. */
function leituraSilhueta(s) {
  if (s > 0.70) return { cls: 'f-ok', txt: 'separação forte' };
  if (s > 0.50) return { cls: 'f-ok', txt: 'separação razoável' };
  if (s > 0.25) return { cls: 'f-ap', txt: 'separação fraca' };
  return { cls: 'f-ri', txt: 'sem estrutura substancial' };
}

function vGrupos() {
  const mi = (S.d || {}).mineracao || {}, g = mi.agrupamento;
  if (!g || !g.aplicavel) {
    $('#b-grupos').innerHTML = vazio('Sem agrupamento.', ((g && g.motivo) || 'Sem dados suficientes para agrupar.')
      + ((g && g.tentativas || []).length ? ' ' + g.tentativas.map(t => `k = ${t.k}: ${t.silhueta != null ? n(t.silhueta, 3) : '—'}`).join(' · ') : ''));
    return;
  }
  const grupoDe = {};
  g.grupos.forEach(gr => gr.componentes.forEach(c => { grupoDe[c.codigo] = gr.nome; }));
  const esc_ = {}; (g.escalas || []).forEach(e => { esc_[e.eixo] = e; });
  const ls = leituraSilhueta(g.silhueta);

  // ENTRADA: as linhas exatas que o k-médias recebeu
  const ent = (mi.entradas_agrupamento || []).filter(e => !e.fora_de_oferta);
  const entrada = ent.length ? `<div class="rola">${tabela(
    ['Disciplina', 'Destrava', 'Abriu em', 'Atraso', 'Carga', 'Grupo'],
    ent.map(e => [
      `<span class="cod">${esc(e.codigo)}</span>`,
      `${e.destrava}`, `${Math.round(100 * (1 - e.raridade))}%`,
      `${e.atraso} sem.`, `${e.carga} h`,
      `<span class="fraco">${esc(grupoDe[e.codigo] || '—')}</span>`,
    ]).concat([[
      '<span class="fraco">média · desvio</span>',
      `<span class="fraco">${n(esc_.destrava?.media, 2)} · ${n(esc_.destrava?.desvio, 2)}</span>`,
      `<span class="fraco">${Math.round(100 * (1 - (esc_.raridade?.media || 0)))}% · ${n(esc_.raridade?.desvio, 2)}</span>`,
      `<span class="fraco">${n(esc_.atraso?.media, 2)} · ${n(esc_.atraso?.desvio, 2)}</span>`,
      `<span class="fraco">${n(esc_.carga?.media, 0)} · ${n(esc_.carga?.desvio, 2)}</span>`, '']]),
    { num: [1, 2, 3, 4], cls: { 0: 'prim' }, empilha: true, rotulos: true })}</div>`
    : `<p class="fraco">A tabela de entrada precisa do servidor atualizado (campo <code>entradas_agrupamento</code>).</p>`;

  // o nome do grupo lê a MÉDIA do grupo; matéria que não tem o traço do nome
  // precisa aparecer escrita, senão o rótulo promete o que ela não faz
  const porCod = Object.fromEntries(ent.map(e => [e.codigo, e]));
  const furos = g.grupos.filter(gr => /^Destrava/.test(gr.nome)).flatMap(gr =>
    gr.componentes.filter(c => porCod[c.codigo] && !porCod[c.codigo].destrava).map(c => ({ cod: c.codigo, g: gr.nome })));
  // Qual eixo mais separa os grupos, medido na escala de cada eixo (diferença
  // entre o maior e o menor grupo, dividida pelo desvio do eixo). Antes a frase
  // dizia, fixa, que o agrupamento "confirma" a ordem por destravamento, e com
  // outro aluno ele separou por frequência de oferta: a frase mentia.
  const EIXO = {
    destrava: { rot: 'quantas matérias cada uma destrava', val: gr => n(gr.perfil.destrava, 1) },
    raridade: { rot: 'com que frequência cada uma abre turma', val: gr => `${gr.perfil.abre_em_pct}%` },
    atraso: { rot: 'o atraso na matriz', val: gr => `${n(gr.perfil.atraso, 1)} sem.` },
    carga: { rot: 'a carga horária', val: gr => `${gr.perfil.carga} h` },
  };
  const bruto = { destrava: gr => gr.perfil.destrava, raridade: gr => 1 - gr.perfil.abre_em_pct / 100,
                  atraso: gr => gr.perfil.atraso, carga: gr => gr.perfil.carga };
  const separa = g.grupos.length > 1 ? Object.keys(EIXO).map(e => {
    const vs = g.grupos.map(bruto[e]), dp = esc_[e]?.desvio || 0;
    return { e, d: dp ? (Math.max(...vs) - Math.min(...vs)) / dp : 0 };
  }).sort((x, y) => y.d - x.d).map(x => ({
    rot: EIXO[x.e].rot, det: g.grupos.map(gr => `${gr.nome}: ${EIXO[x.e].val(gr)}`).join('; '),
  }))[0] : null;
  const grupos = g.grupos.map(gr => `<div class="grupo">
      <div class="grupo-cab"><span class="h3">${esc(gr.nome)}</span>
        <span class="fraco">${plural(gr.quantos, 'matéria', 'matérias')} · destrava ${n(gr.perfil.destrava, 1)} ·
        abriu em ${gr.perfil.abre_em_pct}% · atraso ${n(gr.perfil.atraso, 1)} · ${gr.perfil.carga} h</span></div>
      <p class="fraco">${esc(gr.porque)}</p>
      <div class="tags">${gr.componentes.map(c => `<span class="tag off" title="${esc(c.nome || '')}">${esc(c.codigo)}</span>`).join('')}</div>
    </div>`).join('');

  $('#b-grupos').innerHTML = `
    <div class="parte">
      <div class="parte-t">Entrada · ${g.n} obrigatórias que dependem de oferta</div>
      <p class="mn"><b>destrava</b>: quantas libera · <b>abriu em</b>: semestres com turma, de
        ${(mi.associacao || {}).transacoes || 8} · <b>atraso</b>: semestre de avaliação menos o nível da matéria ·
        <b>carga</b>. Cada coluna em z-score antes de agrupar.</p>
      ${entrada}
      ${(g.fora || []).length ? `<p class="mn">Fora, porque não abrem turma: ${g.fora.map(x => `<b>${esc(x.codigo)}</b>`).join(', ')}.</p>` : ''}
    </div>
    <div class="parte">
      <div class="parte-t">Qualidade</div>
      <div class="qual">
        <div><span>grupos escolhidos</span><b>k = ${g.k}</b></div>
        <div><span>silhueta média</span><b>${n(g.silhueta, 3)}</b></div>
        <div><span>leitura</span><b class="${ls.cls}">${ls.txt}</b></div>
      </div>
      <p class="mn">${g.tentativas.map(t => `k = ${t.k}: ${t.silhueta != null ? n(t.silhueta, 3) : '—'}${t.nota ? ' (grupo de um só, descartado)' : ''}`).join(' · ')}.
        Fica a maior silhueta sem grupo de um só. Escala de Kaufman e Rousseeuw: acima de 0,70 forte;
        0,51 a 0,70 razoável; 0,26 a 0,50 fraca; até 0,25 nenhuma.
        ${g.silhueta <= 0.5 ? '<b>Leia os grupos como indício.</b>' : ''}</p>
    </div>
    <div class="parte">
      <div class="parte-t">Resultado · ${plural(g.grupos.length, 'grupo', 'grupos')}</div>
      ${grupos}
      <p class="mn aviso" style="margin-top:var(--e3)">${separa ? `O que mais separa os grupos: ${separa.rot}.` : ''}
        O plano não usa os grupos: a ordem vem do pré-requisito.${furos.length
        ? ` O nome descreve a média: ${furos.map(f => `<b>${esc(f.cod)}</b>`).join(', ')} não ${furos.length === 1 ? 'destrava' : 'destravam'} nada.` : ''}</p>
    </div>`;
}

function vCooferta() {
  const mi = (S.d || {}).mineracao || {}, a = mi.associacao;
  if (!a || !a.aplicavel) {
    $('#b-cooferta').innerHTML = vazio('Sem associação.', (a && a.motivo) || 'Sem histórico de oferta suficiente.');
    return;
  }
  // ENTRADA: a matriz disciplina × semestre (cada semestre é uma transação)
  const mz = mi.matriz_oferta;
  const entrada = mz && mz.periodos?.length ? `<div class="rola"><table class="mtz">
      <thead><tr><th>Disciplina</th>${mz.periodos.map(p => `<th><span class="longo">${esc(p)}</span><span class="curto">${
        esc(String(p).slice(2, 4))}<br>.${esc(String(p).slice(5))}</span></th>`).join('')}<th class="num">Abriu</th></tr></thead>
      <tbody>${Object.keys(mz.abriu).sort((x, y) => mz.abriu[x].length - mz.abriu[y].length || x.localeCompare(y)).map(cod => `<tr>
        <td><span class="cod">${esc(cod)}</span></td>
        ${mz.periodos.map(p => `<td><i class="s ${mz.abriu[cod].includes(p) ? 'on' : ''}" aria-label="${mz.abriu[cod].includes(p) ? 'abriu' : 'não abriu'}"></i></td>`).join('')}
        <td class="num">${mz.abriu[cod].length}/${mz.periodos.length}</td></tr>`).join('')}</tbody></table></div>`
    : `<p class="mn">${(a.frequencia || []).map(f => `<b>${esc(f.codigo)}</b> ${f.abriu_n}/${f.de_n}`).join(' · ')}</p>`;

  // RESULTADO: os pares que pesam na decisão
  const chave = (p) => `${p.a}|${p.b}`;
  const juntar = new Map();
  (a.nunca_juntas || []).forEach(p => juntar.set(chave(p), { ...p, suporte_n: 0, de_n: a.transacoes, confianca_min: 0, lift: 0, ler: 'nunca abriram juntas: não planeje as duas no mesmo semestre', cls: 'err' }));
  (a.arriscadas || []).forEach(p => juntar.set(chave(p), { ...p, ler: 'coincidem pouco: planejar as duas juntas é aposta', cls: 'aviso' }));
  (a.pares || []).filter(p => p.lift > 1.05 && !juntar.has(chave(p)))
    .forEach(p => juntar.set(chave(p), { ...p, ler: 'andam juntas mais que o acaso', cls: 'ok' }));
  const pesa = [...juntar.values()];
  const resto = (a.pares || []).length - pesa.filter(p => p.cls !== 'err').length;
  const rotulo = { err: 'nunca', aviso: 'aposta', ok: 'juntas' };
  const regras = a.regras || [];
  const topo = regras.slice().sort((x, y) => y.lift - x.lift)[0];
  const possiveis = a.itens * (a.itens - 1);

  $('#b-cooferta').innerHTML = `
    <div class="parte">
      <div class="parte-t">Entrada · ${a.transacoes} semestres (transações) × ${a.itens} disciplinas (itens)</div>
      <p class="mn">Semestre = transação, disciplina que abriu = item; quadrado cheio = abriu.
        ${(a.fora || []).length ? `Fora, porque não abrem turma: ${a.fora.map(c => `<b>${esc(c)}</b>`).join(', ')}.` : ''}</p>
      ${entrada}
    </div>
    <div class="parte">
      <div class="parte-t">Parâmetros</div>
      <div class="qual">
        <div><span>suporte mínimo</span><b>${a.min_suporte_n} de ${a.transacoes} semestres</b></div>
        <div><span>pares encontrados</span><b>${(a.pares || []).length}</b></div>
        <div><span>nunca juntas</span><b>${(a.nunca_juntas || []).length}</b></div>
        <div><span>abaixo de 60%</span><b>${(a.arriscadas || []).length}</b></div>
        <div><span>maior lift</span><b>${topo ? n(topo.lift, 2) : '—'}</b></div>
        <div><span>regras que passam</span><b>${regras.length} de ${possiveis}</b></div>
      </div>
      <p class="mn"><b>Suporte</b>: semestres em que as duas abriram juntas · <b>confiança</b>: a menor
        das duas direções · <b>lift</b>: 1 é independente, acima de 1 andam juntas, abaixo se evitam.</p>
      <p class="mn aviso" style="margin-top:var(--e2)">${regras.length >= possiveis
        ? `Todas as ${possiveis} regras passam no suporte mínimo: o filtro não separa nada.`
        : `${regras.length} das ${possiveis} regras passam no suporte mínimo.`}
        ${topo && topo.lift > 1.05 ? `Maior lift: ${n(topo.lift, 2)} (${esc(topo.se)} e ${esc(topo.entao)}).`
          : 'Nenhum par abre junto mais do que o acaso explica.'} Nenhuma escolha do plano muda por causa dela.</p>
    </div>
    <div class="parte">
      <div class="parte-t">Resultado</div>
      <p class="sub" style="margin-bottom:var(--e2)">${esc(a.veredito)}</p>
      ${pesa.length ? `<div class="rola">${tabela(['Par', 'Suporte', 'Confiança', 'Lift', 'Leitura'],
        pesa.map(p => [
          `<span class="cod">${esc(p.a)} + ${esc(p.b)}</span>`,
          `${p.suporte_n}/${p.de_n}`, `${n(100 * (p.confianca_min || 0), 0)}%`, n(p.lift, 2),
          `<span class="tag ${p.cls}">${rotulo[p.cls]}</span> <span class="fraco">${esc(p.ler)}</span>`,
        ]), { num: [1, 2, 3], cls: { 0: 'prim' }, empilha: true, rotulos: true })}</div>` : ''}
      ${pesa.length ? `<p class="mn" style="margin-top:var(--e2)">Os outros ${resto} pares: lift perto de 1, independentes.</p>` : ''}
    </div>`;
}

function vFila() {
  const f = (S.d || {}).fila;
  if (!f || !f.sa) { $('#b-fila').innerHTML = vazio('Sem dados da fila.', 'A estrutura do curso não veio do SIGAA.'); return; }
  const d = f.desempate || {}, nm = f.norma || {};
  const conta = (f.componentes || []).reduce((a, c) => { a[c.romano] = (a[c.romano] || 0) + 1; return a; }, {});
  const resumo = Object.keys(conta).map(k => `${conta[k]} no nível ${k}`).join(', ');
  $('#b-fila').innerHTML = `
    <div class="fila-n">
      <div><span>Semestre cronológico</span><b>${f.sc}º</b></div>
      <div><span>Semestre de avaliação</span><b>${f.sa}º</b></div>
      <div><span>Você está</span><b>${f.semestralizado ? 'semestralizado' : 'dessemestralizado'}</b></div>
      <div><span>Provável concluinte</span><b>${f.provavel_concluinte ? 'sim' : `não (${n(f.percentual_ch, 1)}% da carga)`}</b></div>
    </div>
    <p class="fila-p"><b>${f.semestralizado ? 'Semestralizado' : 'Fora do grupo prioritário'}</b>: avaliação
      ${f.sa}º ${f.semestralizado ? 'alcança o' : 'menor que o'} cronológico ${f.sc}º. Pedidos: ${esc(resumo)}.</p>
    <p class="fila-p">Desempate: IAP <b>${d.iap != null ? n(d.iap, 4) : '—'}</b> → reprovações por falta
      (<b>${d.reprovacoes_por_falta}</b>) → trancamentos (<b>${d.trancamentos}</b>) → ingresso
      (<b>${esc(d.periodo_ingresso || '—')}</b>).</p>
    ${(f.niveis_da_matriz || []).length ? `<div class="rola" style="margin-bottom:var(--e3)">${tabela(
      ['Nível da matriz', 'Cumpridos', 'Mais da metade?', 'Faltando'],
      f.niveis_da_matriz.map(nv => [
        `<b>${nv.nivel}º</b>${nv.nivel === f.sa ? ' <span class="tag aviso">é o seu SA</span>' : ''}`,
        `${nv.cumpridos} de ${nv.componentes}`,
        nv.mais_da_metade ? 'sim' : '<b>não</b>',
        `<span class="fraco">${esc((nv.faltando || []).join(', ') || '—')}</span>`,
      ]), { num: [1], cls: { 0: 'prim' }, empilha: true, rotulos: true })}</div>` : ''}
    <p class="mn"><a class="link" href="${esc(nm.url || '#')}" target="_blank" rel="noopener">${esc(nm.nome || '')}</a>,
      Art. 2º, 4º e 6º · <code>posicao()</code> em <code>nucleo/fila.py</code>.</p>`;
}

/* ===================================================================
   5. RELATÓRIO — a folha que sai do sistema e vai ao colegiado. Repete dados
   de outras telas (um relatório tem que se bastar) e assina a procedência.
   =================================================================== */
async function vRelatorio() {
  const d = S.d;
  if (!d) return;
  const sit = d.situacao, hs = sit.horas, o = d.oferta || {};
  const agora = new Date();
  const emitido = agora.toLocaleDateString('pt-BR') + ' às ' +
    agora.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  $('#r-relatorio').innerHTML = `Uma folha para imprimir. Emitido em <b>${esc(emitido)}</b>.`;

  const id = `<section class="bloco"><h2 class="h2">Identificação</h2>
    <div class="rel-id">
      <div><span>Aluno</span><b>${esc(d.aluno.nome || '—')}</b></div>
      <div><span>Curso</span><b>${esc(d.aluno.curso || '—')}</b></div>
      <div><span>Semestre atual</span><b>${esc(d.aluno.semestre || '—')}</b></div>
      <div><span>Período letivo</span><b>${esc(String(d.aluno.periodo_letivo ?? '—'))}</b></div>
      <div><span>Currículo</span><b>${esc(d.aluno.curriculo || '—')}</b></div>
      <div><span>Prazo máximo</span><b>${esc(d.aluno.prazo_maximo || '—')}</b></div>
    </div></section>`;

  const integ = `<section class="bloco"><h2 class="h2">Integralização</h2>
    <div class="rel-tot"><b>${n(sit.percentual, 1)}%</b>
      <span>${n(hs.concluido)} h de ${n(hs.exigido)} h · faltam ${n(hs.pendente)} h</span></div>
    <div class="rola">${tabela(['Categoria', 'Feito', 'Exigido', 'Falta', '%', 'Situação'], (sit.categorias || []).map(c => [
      esc(c.nome), `${n(c.feito_h)} h`, `${n(c.exigido_h)} h`, `${n(c.pendente_h)} h`, `${n(c.percentual, 1)}%`,
      c.concluida ? '<span class="tag ok">concluída</span>'
        : (c.materias_a_fazer != null ? `<span class="fraco">faltam ${c.materias_a_fazer}</span>` : '—'),
    ]), { num: [1, 2, 3, 4], cls: { 0: 'prim' }, empilha: true, rotulos: true })}</div>
    ${hs.excedente_que_nao_conta ? `<p class="rel-pe" style="padding-bottom:var(--e4)">${n(hs.excedente_que_nao_conta)} h
      acima do exigido em alguma categoria não contam no total.</p>` : ''}
  </section>`;

  const falta = `<section class="bloco"><h2 class="h2">O que falta cursar</h2>
    <div class="rel-tot"><b>${sit.materias.total_a_cursar}</b>
      <span>matérias: ${sit.materias.obrigatorias_a_cursar} obrigatórias e cerca de ${sit.materias.optativas_a_cursar} optativas</span></div>
    <div class="rola">${tabela(['Código', 'Disciplina', 'CH', 'Oferta e pré-requisito'], d.pendentes.map(p => [
      `<span class="cod">${esc(p.codigo)}</span>`, `<span class="nome">${esc(p.nome)}</span>`, `${p.carga_horaria} h`,
      esc(p.padrao_oferta || '—') + ((p.faltando || []).length ? ` <span class="tag err">falta ${esc(p.faltando.join(', '))}</span>` : ''),
    ]), { num: [2], cls: { 1: 'prim' }, empilha: true, rotulos: true })}</div>
  </section>`;

  const cursa = `<section class="bloco"><h2 class="h2">Cursando agora (${d.cursando.length})</h2>
    <div class="rola">${tabela(['Código', 'Disciplina', 'CH', 'Professor', 'Quando'], d.cursando.map(c => [
      `<span class="cod">${esc(c.codigo)}</span>`, `<span class="nome">${esc(c.nome)}</span>`, `${c.carga_horaria} h`,
      esc((c.docentes || []).join(', ')) || '—',
      `<span class="fraco">${esc((c.encontros || []).map(e => `${e.dia} ${e.inicio}–${e.fim}`).join(' · ')) || '—'}</span>`,
    ]), { num: [2], cls: { 1: 'prim' }, empilha: true, rotulos: true })}</div>
  </section>`;

  let plano = '';
  if (S.alvo) {
    try {
      const j = await api('/api/plano', { alvo: S.alvo, limites: S.limites || null, pular: S.pular || null });
      if (!j.detail && (j.semestres || []).length) {
        plano = `<section class="bloco"><h2 class="h2">Caminho até a formatura em ${esc(j.conclusao)}</h2>
          <div class="rel-tot"><b>${j.carga_necessaria ?? '—'}</b>
            <span>matérias por semestre · ${j.total_semestres} semestres</span></div>
          <p class="rel-pe" style="margin-bottom:var(--e2)">${esc(virgula((j.comparacao || {}).veredito))}</p>
          ${(() => { const inc = (j.semestres || []).filter(riscoDeOferta);
            return inc.length ? `<p class="aviso" style="margin-bottom:var(--e2)">Oferta incerta em ${esc(inc.map(s => s.periodo).join(', '))}: ${
              inc.map(s => { const r = riscoDeOferta(s); return r.parc.map(x => `${esc(x.codigo)} ${x.abriu_n ? `${x.abriu_k} de ${x.abriu_n} ${r.lado}, ` : ''}ponderada ${Math.round(100 * x.chance_oferta)}%`).join(', '); }).join(' · ')}.</p>` : ''; })()}
          <div class="rola">${tabela(['Semestre', 'Matérias', 'CH', 'O que cursar'], j.semestres.map(s2 => [
            `<b>${esc(s2.periodo)}</b>`, `${s2.componentes.length}`, `${n(s2.carga_horaria)} h`,
            s2.componentes.length ? esc(s2.componentes.map(x => x.codigo === 'OPTATIVA' ? 'optativa' : x.codigo).join(', '))
              : `<span class="fraco">${esc(s2.nota || '—')}</span>`,
          ]), { num: [1, 2], cls: { 0: 'prim' }, empilha: true, rotulos: true })}</div>
        </section>`;
      }
    } catch (e) { /* sem plano, o relatório continua válido */ }
  }

  const fonte = d.dados && d.dados.demo
    ? 'Aluno fictício sobre a estrutura, os pré-requisitos e a oferta reais do curso.'
    : `SIGAA da UFBA${d.dados && d.dados.carregado_em
        ? ', lido em ' + new Date(d.dados.carregado_em * 1000).toLocaleString('pt-BR') : ''}.`;
  const pe = `<section class="bloco"><p class="rel-pe">
      <b>Procedência.</b> ${esc(fonte)} Oferta de referência: <b>${esc(o.oferta_de || '—')}</b>${o.proxy
        ? ` (a de ${esc(o.semestre_alvo || '')} ainda não saiu)` : ''}; padrão de oferta desde 2023.1.
      <b>Não é documento oficial</b>: para fins formais, use o histórico da UFBA.
    </p></section>`;

  $('#relatorio').innerHTML = id + integ + falta + cursa + plano + pe;
}

/* Rede de segurança: se alguma caixa ainda rolar de lado (tabela de matriz no
   celular), ela ganha um aviso escrito em cima. Corte sem sinal de que dá
   para arrastar foi o "quebrado" que o Caio viu no telefone. */
// O aviso vai DENTRO da caixa que rola, grudado à esquerda. Fora dela, como
// irmão, ele virava item de grade em "Montar" e empurrava a tabela para a
// coluna estreita (achado na captura das figuras, janela de 1240 px).
function marcaRolagem() {
  $$('.rola').forEach(el => {
    const dica = el.firstElementChild?.classList.contains('rola-dica') ? el.firstElementChild : null;
    const corta = el.scrollWidth > el.clientWidth + 1;
    if (corta && !dica) el.insertAdjacentHTML('afterbegin', '<p class="rola-dica">↔ arraste a tabela para o lado: há mais colunas</p>');
    if (!corta && dica) dica.remove();
  });
}
let _mr = 0;
new MutationObserver(() => { clearTimeout(_mr); _mr = setTimeout(marcaRolagem, 120); })
  .observe(document.querySelector('.conteudo'), { childList: true, subtree: true });
window.addEventListener('resize', () => { clearTimeout(_mr); _mr = setTimeout(marcaRolagem, 120); });

// botão de topo: aparece depois de uma tela e meia de rolagem. Em "Montar" a
// barra de baixo já tem o dela, e dois botões fixos brigariam pelo canto.
function botaoTopo() {
  const b = $('#btn-topo'); if (!b) return;
  b.classList.toggle('oculto', !S.d || S.vista === 'montar' || window.scrollY < innerHeight * 1.5);
}
window.addEventListener('scroll', botaoTopo, { passive: true });

if (S.token) abrir();
