/**
 * =============================================================================
 * AUDITOR CIDADÃO — HOME
 * home.js — Coreografia do hero: uma simulação fiel do streaming do produto.
 *
 * A sequência reencena o que acontece num turno real do agente (ver
 * app/services/ai_engine.py): primeiro os status de ferramentas
 * ("Consultando…"), depois o texto do laudo chegando em chunks de SSE —
 * blocos pequenos e irregulares, não caractere a caractere — e o score
 * consolidado subindo com desaceleração. Roda UMA vez, ao carregar.
 *
 * Fallbacks (sempre para o estado final estático, que já está no HTML):
 *   - prefers-reduced-motion → o inline script do <head> nem adiciona a
 *     classe .hero-anim; este arquivo retorna cedo.
 *   - GSAP indisponível (CDN bloqueada) ou markup inesperado → remove a
 *     classe e o laudo pronto aparece direto.
 * =============================================================================
 */
(function () {
'use strict';

const root = document.documentElement;

// Sem a classe (reduced-motion ou JS parcial), o HTML já mostra o laudo pronto.
if (!root.classList.contains('hero-anim')) return;

/** Reverte para o estado final estático escrito no HTML — rede de segurança. */
function mostrarEstadoFinal() {
    root.classList.remove('hero-anim');
}

if (!window.gsap) {
    mostrarEstadoFinal();
    return;
}

const $ = (id) => document.getElementById(id);
const els = {
    body:         document.querySelector('.code-window-body'),
    heading:      $('hero-heading'),
    scoreLine:    $('hero-score-line'),
    score:        $('hero-score'),
    classWrap:    $('hero-class-wrap'),
    row:          $('hero-row'),
    evidenceLine: $('hero-evidence-line'),
    evidence:     $('hero-evidence'),
    status:       $('hero-status'),
    statusText:   $('hero-status-text'),
    statusDot:    $('hero-status-dot'),
};

if (Object.values(els).some((el) => !el)) {
    mostrarEstadoFinal();
    return;
}

const SCORE_FINAL = 0.87;
const STATUS_INICIAL = 'Consultando Receita Federal…';
const STATUS_PASSOS = [
    { texto: 'Consultando PNCP…',             em: 1.05 },
    { texto: 'Cruzando sanções (CEIS/CNEP)…', em: 2.0  },
];
const STATUS_FINAL = 'Laudo pronto';


/* =============================================================================
   PREPARAÇÃO — capturar o estado final e zerar a janela
   ============================================================================= */

// Congela as alturas medidas com o laudo completo (o HTML nasce no estado
// final) para que nada na janela "pule" enquanto o texto é digitado.
els.body.style.minHeight         = els.body.offsetHeight + 'px';
els.heading.style.minHeight      = els.heading.offsetHeight + 'px';
els.evidenceLine.style.minHeight = els.evidenceLine.offsetHeight + 'px';

// Textos finais lidos do próprio HTML — fonte única da verdade.
const textoHeading   = els.heading.textContent;
const textoEvidencia = els.evidence.textContent;

// Cursor de streaming (o mesmo ▍ do chat), movido para onde o texto está chegando.
const caret = document.createElement('span');
caret.className = 'stream-caret';
caret.setAttribute('aria-hidden', 'true');
caret.textContent = '▍';

/** Esvazia o elemento e devolve o text node que receberá os chunks. */
function prepararNode(el) {
    const node = document.createTextNode('');
    el.textContent = '';
    el.appendChild(node);
    return node;
}

const headingNode  = prepararNode(els.heading);
const evidenceNode = prepararNode(els.evidence);

// Estado inicial: só o status visível, laudo vazio, score zerado.
els.statusText.textContent = STATUS_INICIAL;
els.status.classList.remove('is-done');
els.statusDot.classList.add('is-live');
els.score.textContent = '0.00';
gsap.set([els.heading, els.scoreLine, els.row, els.evidenceLine], { autoAlpha: 0 });
gsap.set(els.classWrap, { autoAlpha: 0 });

// O JS assumiu (estados iniciais aplicados inline) — a classe que escondia o
// laudo no primeiro paint pode sair sem risco de flash.
root.classList.remove('hero-anim');


/* =============================================================================
   BLOCOS DA COREOGRAFIA
   ============================================================================= */

/** Divide o texto em prefixos cumulativos com "tokens" de 2 a 8 caracteres —
 * o tamanho irregular imita os chunks que o backend envia via SSE. */
function tokenizar(texto) {
    const prefixos = [];
    let i = 0;
    while (i < texto.length) {
        i = Math.min(texto.length, i + 2 + Math.floor(Math.random() * 7));
        prefixos.push(texto.slice(0, i));
    }
    return prefixos;
}

/** Agenda a chegada de `texto` no text node a partir de `inicio` (segundos) e
 * devolve o instante em que termina. A cadência é irregular, com pausas
 * ocasionais mais longas — jitter de rede, não metrônomo. */
function agendarChunks(tl, node, texto, inicio) {
    let t = inicio;
    tokenizar(texto).forEach((prefixo) => {
        tl.call(() => { node.data = prefixo; }, null, t);
        t += Math.random() < 0.15
            ? 0.14 + Math.random() * 0.18
            : 0.03 + Math.random() * 0.05;
    });
    return t;
}

/** Troca o texto do status com um crossfade curto. */
function agendarStatus(tl, texto, quando) {
    tl.to(els.statusText, { opacity: 0, duration: 0.12, ease: 'power1.in' }, quando);
    tl.call(() => { els.statusText.textContent = texto; }, null, quando + 0.12);
    tl.to(els.statusText, { opacity: 1, duration: 0.16, ease: 'power1.out' }, quando + 0.14);
}


/* =============================================================================
   TIMELINE
   ============================================================================= */

const tl = gsap.timeline({ delay: 0.4 });

// Fase 1 — as "ferramentas" consultam as fontes oficiais em sequência.
STATUS_PASSOS.forEach((p) => agendarStatus(tl, p.texto, p.em));

// Fase 2 — o laudo começa a chegar: primeiro o heading em Markdown…
tl.set(els.heading, { autoAlpha: 1 }, 2.75);
tl.call(() => els.heading.appendChild(caret), null, 2.75);
const fimHeading = agendarChunks(tl, headingNode, textoHeading, 2.8);

// …depois a linha de score, com o número subindo em desaceleração.
const tScore = fimHeading + 0.18;
tl.fromTo(els.scoreLine,
    { autoAlpha: 0, y: 4 },
    { autoAlpha: 1, y: 0, duration: 0.24, ease: 'power1.out' },
    tScore);

const contador = { v: 0 };
tl.to(contador, {
    v: SCORE_FINAL,
    duration: 1.15,
    ease: 'power2.out',
    onUpdate: () => { els.score.textContent = contador.v.toFixed(2); },
}, tScore + 0.08);

// A classificação (— CRÍTICO) só aparece quando o número assenta.
tl.fromTo(els.classWrap, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.2 }, tScore + 1.1);

// A anomalia mais grave entra enquanto o score ainda sobe.
tl.fromTo(els.row,
    { autoAlpha: 0, y: 5 },
    { autoAlpha: 1, y: 0, duration: 0.26, ease: 'power1.out' },
    tScore + 0.35);

// Fase 3 — a evidência chega em chunks, com o cursor acompanhando.
const tEvidencia = tScore + 0.6;
tl.fromTo(els.evidenceLine, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.18 }, tEvidencia);
tl.call(() => els.evidence.appendChild(caret), null, tEvidencia);
const fimEvidencia = agendarChunks(tl, evidenceNode, textoEvidencia, tEvidencia + 0.06);

// Fase 4 — encerramento: cursor some, status resolve para "Laudo pronto".
const tFim = Math.max(fimEvidencia + 0.35, tScore + 1.45);
agendarStatus(tl, STATUS_FINAL, tFim);
tl.call(() => {
    caret.remove();
    els.statusDot.classList.remove('is-live');
    els.status.classList.add('is-done');
}, null, tFim + 0.14);

})();
