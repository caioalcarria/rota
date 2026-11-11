// Captura as figuras do documento (atividade/trabalho-final.html), sempre no
// mesmo estado, por CDP num Chrome já aberto pelo capturar.sh.
//
// Como era: o capturar.sh tirava a página inteira e o recortar.py fatiava por
// POSIÇÃO EM PIXEL anotada à mão ("o plano vai de 660 a 1640 px"). Bastou o
// layout mudar para todos os cortes caírem no lugar errado, e o recortar.py
// dependia do PIL, que não existe nesta máquina.
//
// Como é: cada figura diz QUAIS BLOCOS da tela ela mostra (seletores CSS), e o
// próprio navegador recorta o retângulo desses blocos na hora da captura, em
// escala 2. O corte acompanha o layout em vez de quebrar com ele.
//
// Legibilidade: no PDF a figura tem no máximo 16 cm de largura e 20 cm de
// altura. Captura-se só a coluna de conteúdo, numa janela de 1120 px (a
// coluna fica com ~860 px): a letra de 14 px sai com ~7 pt no papel. Na
// janela antiga, de 1440 px, ela saía com ~4,4 pt.
//
// uso: node capturar.mjs <pasta-de-saida> <url-base> <porta-cdp> [--so-medir]
import { writeFileSync, mkdirSync } from 'node:fs';

const [SAIDA, BASE, PORTA, MODO] = process.argv.slice(2);
const SO_MEDIR = MODO === '--so-medir';
const ESCALA = 2;            // o papel precisa de densidade
const MARGEM = 16;           // px CSS de folga em volta dos blocos
const LARG_MM = 160, ALT_MM = 200;   // teto da figura no PDF (figure.larga)

// Cada figura: a tela, o que fazer antes, quando está pronta, e o retângulo.
// `recorte` roda na página e devolve {de, ate, x0, x1}: os elementos cujo topo
// abre e cujo fim fecha o recorte, e a faixa horizontal.
const FIGURAS = [
  {
    nome: '2-decisao-caminhos', vista: 'formatura', janela: 1120,
    pronto: `document.querySelectorAll('#caminhos .cam').length > 0 && document.querySelectorAll('#grafico .gr-col').length > 0`,
    // cabeçalho, os caminhos e o gráfico de carga contra o ritmo
    recorte: `({ de: '#v-formatura .cab', ateEl: document.querySelector('#grafico').closest('.bloco'), coluna: '#v-formatura' })`,
  },
  {
    nome: '3-decisao-plano', vista: 'formatura', janela: 1120,
    pronto: `document.querySelectorAll('#plano .sem').length >= 4 && !!document.querySelector('#sel-reprovar')`,
    // o plano até o primeiro semestre de oferta incerta, inclusive: os que
    // vêm depois são só "qualquer optativa" e esticariam a figura até a
    // letra ficar ilegível
    recorte: `(() => { const s = [...document.querySelectorAll('#plano .sem')];
      const i = s.findIndex(x => x.querySelector('.sem-risco'));
      return { de: '#bloco-plano', ateEl: s[i >= 0 ? i : Math.min(3, s.length - 1)], coluna: '#bloco-plano', fechaBloco: true, rente: true }; })()`,
  },
  {
    nome: '4-decisao-e-se', vista: 'formatura', janela: 1120,
    base: `!!document.querySelector('#sel-reprovar') && document.querySelectorAll('#plano .sem').length > 0`,
    // O "E se eu reprovar?" virou CONTROLE do plano. A figura mostra o
    // primeiro caminho dentro do prazo em que uma reprovação custa semestre,
    // com uma disciplina (não o TCC) reprovada. Sai da API, não de código
    // escrito aqui: com outro aluno a figura continua mostrando um custo real.
    antes: `(async () => {
      const espera = async (f) => { for (let i = 0; i < 80; i++) { if (f()) return true; await new Promise(r => setTimeout(r, 150)); } return false; };
      let alvo = null, cod = null;
      for (const c of S.caminhos.filter(c => c.diante_do_prazo !== 'passa')) {
        const p = await api('/api/plano', { alvo: c.alvo });
        const e = await api('/api/e-se', { por_semestre: p.carga_necessaria });
        const x = (e.custam || []).find(x => !/^GICC/.test(x.codigo)) || (e.custam || [])[0];
        if (x) { alvo = c.alvo; cod = x.codigo; break; }
      }
      if (!alvo) return 0;
      document.querySelector('.cam[data-alvo="' + alvo + '"]').click();
      await espera(() => document.querySelector('#plano-t')?.textContent.includes(alvo) && document.querySelector('#sel-reprovar'));
      const s = document.querySelector('#sel-reprovar'); s.value = cod; s.dispatchEvent(new Event('change'));
      await espera(() => document.querySelector('#cenario .cenario-r')?.textContent.includes('Reprovando'));
      // O navegador sem tela não fotografa a lista suspensa aberta. Para a
      // figura mostrar o que o aluno vê ao abrir o seletor (as onze
      // pendências, cada uma com o atraso que causaria), o MESMO seletor é
      // exibido como lista (atributo size). Só na captura.
      const l = document.querySelector('#sel-reprovar');
      l.size = l.options.length; l.style.flex = '1 1 100%'; l.style.height = 'auto';
      return 1; })()`,
    pronto: `document.querySelector('#sel-reprovar')?.size > 1 && document.querySelector('#cenario .cenario-r')?.textContent.includes('Reprovando')`,
    // do título do plano até o resultado do cenário
    recorte: `({ de: '#bloco-plano', ate: '#bloco-plano .legenda', coluna: '#bloco-plano', rente: true })`,
  },
  {
    nome: '5-agrupamento', vista: 'conta', janela: 1120,
    pronto: `document.querySelectorAll('#b-grupos .grupo').length > 0`,
    recorte: `({ de: '#b-grupos', ate: '#b-grupos', coluna: '#b-grupos', renteTopo: true })`,
  },
  {
    nome: '6-cooferta', vista: 'conta', janela: 1120,
    pronto: `!!document.querySelector('#b-cooferta .mtz')`,
    // dos parâmetros ao resultado: a matriz de entrada (disciplina x
    // semestre) sai numa figura à parte, senão a letra cai para 4 pt
    recorte: `({ de: document.querySelectorAll('#b-cooferta .parte')[1], ate: '#b-cooferta', coluna: '#b-cooferta', renteTopo: true })`,
  },
  {
    nome: 'extra-matriz-oferta', vista: 'conta', janela: 1120,
    pronto: `!!document.querySelector('#b-cooferta .mtz')`,
    recorte: `({ de: '#b-cooferta', ateEl: document.querySelectorAll('#b-cooferta .parte')[0], coluna: '#b-cooferta', rente: true, renteTopo: true })`,
  },
  {
    // A legenda da Figura 4 fala da posição na fila, da derivação e dos
    // critérios de desempate: isso mora agora em "Como a conta é feita".
    nome: '7-falta-pegar', vista: 'conta', janela: 1120,
    pronto: `document.querySelectorAll('#b-fila tbody tr').length > 0`,
    recorte: `({ de: '#b-fila', ate: '#b-fila', coluna: '#b-fila', renteTopo: true })`,
  },
  {
    nome: '8-montar', vista: 'montar', janela: 1240, extra: '&marcar=3',
    pronto: `document.querySelectorAll('#t-montar .sel:checked').length >= 3 && !!document.querySelector('#agenda .ag-grade')`,
    // a grade da semana inteira e as primeiras linhas da lista, até passar da
    // linha que choca com uma marcada (fica vermelha)
    recorte: `(() => { const tr = [...document.querySelectorAll('#t-montar tbody tr')];
      const ch = tr.findIndex(t => t.classList.contains('conflito'));
      const ult = tr[Math.max(ch + 1, 5)] || tr[tr.length - 1];
      const ag = document.querySelector('.agenda');
      return { de: '#v-montar .cab', ateEl: ult.getBoundingClientRect().bottom > ag.getBoundingClientRect().bottom ? ult : ag,
               coluna: '#v-montar', fechaBloco: true, blocoDoFim: '.montar-grade', rente: true }; })()`,
  },
  {
    nome: '9-relatorio', vista: 'relatorio', janela: 1120,
    pronto: `document.querySelectorAll('#relatorio .bloco').length >= 5`,
    // cabeçalho, identificação e integralização (o resto repete outras telas)
    recorte: `(() => ({ de: '#v-relatorio .cab', ateEl: document.querySelectorAll('#relatorio .bloco')[1], coluna: '#v-relatorio' }))()`,
  },
  {
    // fora do documento: a tela "O que falta", que nenhuma das oito mostra
    nome: 'extra-o-que-falta', vista: 'falta', janela: 1120,
    pronto: `document.querySelectorAll('#t-faltam tbody tr').length > 0`,
    recorte: `(() => ({ de: '#v-falta .cab', ateEl: document.querySelector('#t-cursando').closest('section'), coluna: '#v-falta' }))()`,
  },
];

// Na página: transforma a descrição do recorte num retângulo em px CSS.
const RETANGULO = (desc) => `(() => {
  const d = ${desc};
  const el = (x) => typeof x === 'string' ? document.querySelector(x) : x;
  const r = (x) => el(x).getBoundingClientRect();
  const top = r(d.de).top + scrollY;
  let fim = r(d.ateEl || d.ate).bottom + scrollY;
  // cortando no meio de um bloco com borda: fecha na borda do bloco só se o
  // fim do bloco estiver perto; senão corta logo abaixo do elemento
  if (d.fechaBloco) {
    const b = d.blocoDoFim ? el(d.blocoDoFim) : el(d.ateEl).closest('.bloco');
    if (b) { const bb = r(b).bottom + scrollY; if (bb - fim < 40) fim = bb; }
  }
  const c = r(d.coluna);
  return { x: c.left + scrollX, y: top, w: c.width, h: fim - top, rente: !!d.rente, renteTopo: !!d.renteTopo };
})()`;

const t = await (await fetch(`http://127.0.0.1:${PORTA}/json/new?about:blank`, { method: 'PUT' })).json();
const ws = new WebSocket(t.webSocketDebuggerUrl); let id = 0; const pend = new Map();
ws.onmessage = (m) => { const d = JSON.parse(m.data); if (pend.has(d.id)) { pend.get(d.id)(d); pend.delete(d.id); } };
await new Promise(r => { ws.onopen = r; });
const send = (method, params = {}) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (e) => {
  const r = await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true });
  if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || 'erro na página');
  return r.result?.result?.value;
};
const dorme = (ms) => new Promise(r => setTimeout(r, ms));
await send('Page.enable');
if (!SO_MEDIR) mkdirSync(SAIDA, { recursive: true });

console.log('figura                 px CSS      px do arquivo   no papel     letra de 14 px');
let k = 0;
for (const f of FIGURAS) {
  // janela alta: a barra fixa de "Montar" fica no lugar natural, fora do recorte
  await send('Emulation.setDeviceMetricsOverride', { width: f.janela, height: 3000, deviceScaleFactor: ESCALA, mobile: false });
  await send('Page.navigate', { url: `${BASE}/?demo=1&tema=claro${f.extra || ''}&cap=${++k}#${f.vista}` });
  await dorme(800);
  const espera = async (cond) => { for (let i = 0; i < 100; i++) { if (await ev(`(() => { try { return !!(${cond}); } catch (e) { return false; } })()`)) return true; await dorme(150); } return false; };
  if (f.base) await espera(f.base);
  if (f.antes) await ev(f.antes);
  const ok = await espera(f.pronto);
  // os botões de navegação da página ("voltar ao topo", "↑ Topo") não são
  // conteúdo: somem só na captura
  await ev(`(() => { const s = document.createElement('style'); s.textContent = '.volta, .topo { display: none !important; }'; document.head.appendChild(s); return 1; })()`);
  await ev(`window.scrollTo(0, 0); document.fonts.ready.then(() => 1)`);
  await dorme(500);
  const ret = await ev(RETANGULO(f.recorte));
  // "rente": o corte cai dentro de um bloco; sem folga embaixo (ou em cima),
  // senão aparece a lasca do item seguinte
  const mTopo = ret.renteTopo ? 4 : MARGEM, mFim = ret.rente ? 2 : MARGEM;
  const x = Math.max(0, Math.floor(ret.x - MARGEM)), y = Math.max(0, Math.floor(ret.y - mTopo));
  const w = Math.ceil(ret.w + 2 * MARGEM), h = Math.ceil(ret.h + mTopo + mFim);
  // tamanho no papel: a figura encolhe até caber em 16 x 20 cm
  const mmPorPx = Math.min(LARG_MM / w, ALT_MM / h);
  const pt14 = 14 * mmPorPx / 0.3528;
  console.log(`${f.nome.padEnd(22)} ${String(w).padStart(4)}x${String(h).padEnd(5)}  ${String(w * ESCALA).padStart(5)}x${String(h * ESCALA).padEnd(5)}    ${(w * mmPorPx / 10).toFixed(1)}x${(h * mmPorPx / 10).toFixed(1)} cm   ${pt14.toFixed(1)} pt${pronto(ok)}`);
  if (SO_MEDIR) continue;
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true,
    clip: { x, y, width: w, height: h, scale: 1 } });
  writeFileSync(`${SAIDA}/${f.nome}.png`, Buffer.from(shot.result.data, 'base64'));
}
function pronto(ok) { return ok ? '' : '   (!) não ficou pronta a tempo'; }
await send('Target.closeTarget', { targetId: t.id }).catch(() => {});
process.exit(0);
