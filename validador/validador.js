/* Validador de usabilidade do Rota.
   Roda dentro da página e devolve JSON com os problemas encontrados.
   Checa o que dá pra medir objetivamente: contraste, tamanho de fonte,
   alvo clicável, rótulo de campo, comprimento de linha e densidade.
   Critérios: WCAG 2.2 AA (contraste 4.5:1 e 3:1, alvo mínimo 24x24). */

(() => {
  const achados = [];
  const add = (nivel, regra, msg, el) => achados.push({
    nivel, regra, msg,
    alvo: el ? (el.tagName.toLowerCase()
      + (el.id ? '#' + el.id : '')
      + (el.className && typeof el.className === 'string'
          ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : ''))
      : null,
    texto: el ? (el.textContent || '').trim().slice(0, 48) : null,
  });

  /* ---------------------------------------------------------- cores */
  const rgb = (s) => {
    const m = (s || '').match(/[\d.]+/g);
    if (!m) return null;
    return { r: +m[0], g: +m[1], b: +m[2], a: m[3] === undefined ? 1 : +m[3] };
  };
  const lum = (c) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const mistura = (frente, fundo) => frente.a >= 1 ? frente : {
    r: frente.r * frente.a + fundo.r * (1 - frente.a),
    g: frente.g * frente.a + fundo.g * (1 - frente.a),
    b: frente.b * frente.a + fundo.b * (1 - frente.a), a: 1,
  };
  const contraste = (a, b) => {
    const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
    return (x + 0.05) / (y + 0.05);
  };
  const fundoDe = (el) => {
    let no = el;
    while (no && no !== document.documentElement) {
      const c = rgb(getComputedStyle(no).backgroundColor);
      if (c && c.a > 0.95) return c;
      no = no.parentElement;
    }
    return rgb(getComputedStyle(document.body).backgroundColor) || { r: 255, g: 255, b: 255, a: 1 };
  };

  const visivel = (el) => {
    const s = getComputedStyle(el), r = el.getBoundingClientRect();
    return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.05
      && r.width > 0 && r.height > 0;
  };

  const comTexto = Array.from(document.querySelectorAll('body *')).filter(el => {
    if (!visivel(el)) return false;
    return Array.from(el.childNodes).some(no => no.nodeType === 3 && no.textContent.trim().length > 1);
  });

  /* ------------------------------------------------- 1. contraste */
  comTexto.forEach(el => {
    const s = getComputedStyle(el);
    const fg = rgb(s.color), bg = fundoDe(el);
    if (!fg || !bg) return;
    const px = parseFloat(s.fontSize);
    const peso = parseInt(s.fontWeight) || 400;
    const grande = px >= 24 || (px >= 18.66 && peso >= 700);
    const minimo = grande ? 3 : 4.5;
    const r = contraste(mistura(fg, bg), bg);
    if (r < minimo) {
      add(r < minimo - 1 ? 'erro' : 'aviso', 'contraste',
        `${r.toFixed(2)}:1, abaixo do mínimo ${minimo}:1 para ${px.toFixed(0)}px`, el);
    }
  });

  /* ---------------------------------------------- 2. fonte pequena */
  comTexto.forEach(el => {
    const px = parseFloat(getComputedStyle(el).fontSize);
    if (px < 14) add(px < 12 ? 'erro' : 'aviso', 'fonte', `${px.toFixed(1)}px — o professor pediu mínimo 16 em tela projetada; abaixo de 14px é ilegível`, el);
  });

  /* ------------------------------------------------ 3. alvo pequeno */
  document.querySelectorAll('button, a, input, select, [role=button], [role=option]').forEach(el => {
    if (!visivel(el)) return;
    const r = el.getBoundingClientRect();
    // tolerância de meio pixel: borda e zoom fazem 24px virar 23,99 no rect
    if (r.width < 23.5 || r.height < 23.5) {
      add('erro', 'alvo', `${r.width.toFixed(1)}x${r.height.toFixed(1)}px — mínimo 24x24`, el);
    }
  });

  /* ------------------------------------------------- 4. campo sem rótulo */
  document.querySelectorAll('input, select, textarea').forEach(el => {
    if (!visivel(el) || el.type === 'hidden') return;
    const temRotulo = el.labels?.length || el.getAttribute('aria-label')
      || el.getAttribute('aria-labelledby') || el.getAttribute('title');
    if (!temRotulo) add('erro', 'rotulo', 'campo sem rótulo associado', el);
  });

  /* ------------------------------------------- 5. linha longa demais */
  comTexto.forEach(el => {
    const s = getComputedStyle(el), px = parseFloat(s.fontSize);
    const largura = el.getBoundingClientRect().width;
    const chars = largura / (px * 0.5);
    const txt = (el.textContent || '').trim();
    if (txt.length > 120 && chars > 110) {
      add('aviso', 'linha', `~${Math.round(chars)} caracteres por linha — acima de 110 cansa a leitura`, el);
    }
  });

  /* ----------------------------------------------- 6. foco visível
     Não dá para ler o estilo de foco num elemento que não está focado:
     :focus-visible é pseudo-classe. Então a checagem é na folha de estilo. */
  let temRegraDeFoco = false;
  for (const folha of document.styleSheets) {
    let regras;
    try { regras = folha.cssRules; } catch { continue; }  // folha de outra origem
    for (const r of regras || []) {
      if (r.selectorText && /:focus(-visible)?\b/.test(r.selectorText)
          && /outline|box-shadow|border/.test(r.cssText)) { temRegraDeFoco = true; break; }
    }
    if (temRegraDeFoco) break;
  }
  if (!temRegraDeFoco) {
    add('erro', 'foco', 'nenhuma regra de :focus-visible declarada nas folhas de estilo', null);
  }

  /* ------------------------------------------------- 7. densidade */
  const alturaTexto = comTexto.reduce((s, el) => s + el.getBoundingClientRect().height, 0);
  const area = document.body.getBoundingClientRect().height;
  const densidade = area ? alturaTexto / area : 0;
  if (densidade > 1.8) {
    add('aviso', 'densidade',
      `proporção de texto ${densidade.toFixed(2)} — tela carregada demais`, null);
  }

  const porNivel = (n) => achados.filter(a => a.nivel === n).length;
  return {
    url: location.pathname,
    titulo: document.title,
    verificados: comTexto.length,
    erros: porNivel('erro'),
    avisos: porNivel('aviso'),
    nota: Math.max(0, 100 - porNivel('erro') * 8 - porNivel('aviso') * 3),
    achados: achados.slice(0, 40),
  };
})()
