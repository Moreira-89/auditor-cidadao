/**
 * =============================================================================
 * AUDITOR CIDADÃO — APRESENTAÇÃO DATA MASTER
 * script.js — Navegação (setas do teclado: ← volta · → avança) + motor de
 * coreografia por slide:
 *   · reveals escalonados dos blocos (focus-pull via CSS);
 *   · diagramas que se "montam" — nós surgem em sequência, arestas são
 *     traçadas (stroke-dashoffset);
 *   · números que contam de 0 ao valor final;
 *   · capa: re-encenação do streaming real do produto (status das ferramentas
 *     → laudo digitado → score subindo), um callback ao home.js do site.
 * =============================================================================
 */
(function () {
    'use strict';

    var slides = Array.prototype.slice.call(document.querySelectorAll('.slide'));
    var total = slides.length;
    if (!total) return;

    var progressFill = document.querySelector('.deck-progress-fill');
    var counterCur = document.querySelector('.deck-counter-cur');
    var counterTot = document.querySelector('.deck-counter-tot');

    // Respeita "reduzir movimento" do sistema, mas permite forçar as animações
    // com ?motion=1 na URL (útil se o SO do apresentador tem o flag ligado).
    var forceMotion = /[?&]motion=1\b/.test(window.location.search);
    var reduced = !forceMotion && !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

    var current = 0;
    var animating = false;
    var gen = 0;                 // geração de coreografia — invalida animações do slide anterior
    var lenCache = new WeakMap();

    function clamp(n) { return Math.max(0, Math.min(total - 1, n)); }

    function raf2(fn) { requestAnimationFrame(function () { requestAnimationFrame(fn); }); }

    function lenOf(path) {
        if (lenCache.has(path)) return lenCache.get(path);
        var L = 300;
        try { L = path.getTotalLength() || 300; } catch (e) { L = 300; }
        lenCache.set(path, L);
        return L;
    }

    /** Conta um número de 0 até `to` com desaceleração cúbica, enquanto `alive()`. */
    function countNumber(el, to, dec, dur, alive) {
        var start = null;
        function frame(ts) {
            if (!alive()) return;
            if (start === null) start = ts;
            var p = Math.min(1, (ts - start) / dur);
            var e = 1 - Math.pow(1 - p, 3);
            el.textContent = (to * e).toFixed(dec);
            if (p < 1) requestAnimationFrame(frame);
            else el.textContent = to.toFixed(dec);
        }
        requestAnimationFrame(frame);
    }


    /* =========================================================================
       REVEALS ESCALONADOS
       ========================================================================= */
    function applyReveals(slide) {
        var els = slide.querySelectorAll('[data-reveal]');
        for (var i = 0; i < els.length; i++) {
            els[i].style.transitionDelay = (70 + i * 80) + 'ms';
        }
    }
    function clearReveals(slide) {
        var els = slide.querySelectorAll('[data-reveal]');
        for (var i = 0; i < els.length; i++) {
            els[i].style.transitionDelay = '0ms';
        }
    }


    /* =========================================================================
       DIAGRAMAS — nós surgem em sequência, arestas são traçadas
       ========================================================================= */
    function animateDiagram(slide) {
        if (reduced) return;
        var dg = slide.querySelector('.dg');
        if (!dg) return;

        var nodes = dg.querySelectorAll('rect, polygon, text');
        var edges = dg.querySelectorAll('.dg-edge');
        var base = 240, nStep = 45;

        Array.prototype.forEach.call(nodes, function (el, i) {
            var d = base + i * nStep;
            el.style.transition = 'none';
            el.style.opacity = '0';
            el.style.transform = 'scale(0.86) translateY(8px)';
            raf2(function () {
                el.style.transition = 'opacity 0.5s var(--ease-out) ' + d + 'ms, transform 0.7s var(--ease-back) ' + d + 'ms';
                el.style.opacity = '1';
                el.style.transform = 'none';
            });
        });

        var eBase = base + Math.round(nodes.length * nStep * 0.45) + 120;
        Array.prototype.forEach.call(edges, function (el, i) {
            var solid = !el.classList.contains('dg-edge-dim') && !el.classList.contains('dg-edge-loop');
            // Preserva a hierarquia visual: arestas tracejadas (secundárias) entram
            // já esmaecidas, não em opacidade cheia.
            var target = el.classList.contains('dg-edge-dim') ? '0.75'
                       : el.classList.contains('dg-edge-loop') ? '0.9' : '1';
            var d = eBase + i * 90;
            el.style.transition = 'none';
            el.style.opacity = '0';
            if (solid) {
                var L = lenOf(el);
                el.style.strokeDasharray = L;
                el.style.strokeDashoffset = L;
            }
            raf2(function () {
                el.style.transition = solid
                    ? 'opacity 0.4s var(--ease-out) ' + d + 'ms, stroke-dashoffset 0.9s var(--ease-io) ' + d + 'ms'
                    : 'opacity 0.6s var(--ease-out) ' + d + 'ms';
                el.style.opacity = target;
                if (solid) el.style.strokeDashoffset = '0';
            });
        });
    }

    function resetDiagram(slide) {
        if (reduced) return;
        var dg = slide.querySelector('.dg');
        if (!dg) return;
        Array.prototype.forEach.call(dg.querySelectorAll('rect, polygon, text'), function (el) {
            el.style.transition = 'none';
            el.style.opacity = '0';
            el.style.transform = 'scale(0.86) translateY(8px)';
        });
        Array.prototype.forEach.call(dg.querySelectorAll('.dg-edge'), function (el) {
            el.style.transition = 'none';
            el.style.opacity = '0';
            var solid = !el.classList.contains('dg-edge-dim') && !el.classList.contains('dg-edge-loop');
            if (solid) el.style.strokeDashoffset = lenOf(el);
        });
    }


    /* =========================================================================
       CONTADORES ([data-count])
       ========================================================================= */
    function animateCounts(slide, myGen) {
        var els = slide.querySelectorAll('[data-count]');
        Array.prototype.forEach.call(els, function (el, i) {
            var s = el.getAttribute('data-count');
            var to = parseFloat(s);
            var dec = (s.split('.')[1] || '').length;
            if (reduced) { el.textContent = to.toFixed(dec); return; }
            el.textContent = (0).toFixed(dec);
            window.setTimeout(function () {
                if (myGen !== gen) return;
                countNumber(el, to, dec, 900, function () { return myGen === gen; });
            }, 260 + i * 90);
        });
    }
    function resetCounts(slide) {
        var els = slide.querySelectorAll('[data-count]');
        Array.prototype.forEach.call(els, function (el) {
            var dec = ((el.getAttribute('data-count').split('.')[1]) || '').length;
            el.textContent = (0).toFixed(dec);
        });
    }


    /* =========================================================================
       CAPA — re-encenação do streaming do produto
       ========================================================================= */
    var heroTimers = [];
    var heroGen = 0;

    function hid(id) { return document.getElementById(id); }

    function stopHero() {
        for (var i = 0; i < heroTimers.length; i++) clearTimeout(heroTimers[i]);
        heroTimers = [];
        heroGen++;
    }

    function heroHide(el) {
        if (!el) return;
        el.style.transition = 'none';
        el.style.opacity = '0';
        el.style.transform = 'translateY(8px)';
    }
    function heroShow(el) {
        if (!el) return;
        el.style.transition = 'opacity 0.5s var(--ease-out), transform 0.6s var(--ease-out)';
        el.style.opacity = '1';
        el.style.transform = 'none';
    }

    function swapStatus(el, txt, myGen) {
        el.style.transition = 'opacity 0.16s var(--ease-out)';
        el.style.opacity = '0';
        heroTimers.push(setTimeout(function () {
            if (myGen !== heroGen) return;
            el.textContent = txt;
            el.style.opacity = '1';
        }, 160));
    }

    function typeInto(el, text, cps, myGen) {
        el.textContent = '';
        var caret = document.createElement('span');
        caret.className = 'stream-caret';
        caret.setAttribute('aria-hidden', 'true');
        caret.textContent = '▍';
        el.appendChild(caret);
        var i = 0;
        var step = Math.max(22, 1000 / cps);
        function tick() {
            if (myGen !== heroGen) return;
            i++;
            el.textContent = text.slice(0, i);
            el.appendChild(caret);
            if (i < text.length) {
                heroTimers.push(setTimeout(tick, step));
            } else {
                heroTimers.push(setTimeout(function () {
                    if (myGen !== heroGen) return;
                    if (caret.parentNode) caret.parentNode.removeChild(caret);
                }, 550));
            }
        }
        heroTimers.push(setTimeout(tick, step));
    }

    function setHeroFinal() {
        var heading = hid('hero-heading'), scoreLine = hid('hero-score-line'), score = hid('hero-score'),
            cls = hid('hero-class'), row = hid('hero-row'), evLine = hid('hero-evidence-line'),
            status = hid('hero-status'), statusText = hid('hero-status-text'), dot = hid('hero-dot');
        if (!heading) return;
        heading.textContent = '# Resumo Executivo';
        if (score) score.textContent = '0.87';
        [scoreLine, cls, row, evLine].forEach(function (el) {
            if (el) { el.style.transition = 'none'; el.style.opacity = '1'; el.style.transform = 'none'; }
        });
        if (statusText) statusText.textContent = 'Laudo pronto';
        if (dot) dot.classList.remove('is-live');
        if (status) status.classList.add('is-done');
    }

    function playHero() {
        var win = hid('hero-window');
        if (!win) return;
        stopHero();
        if (reduced) { setHeroFinal(); return; }

        var myGen = heroGen;
        var heading = hid('hero-heading'), scoreLine = hid('hero-score-line'), score = hid('hero-score'),
            cls = hid('hero-class'), row = hid('hero-row'), evLine = hid('hero-evidence-line'),
            status = hid('hero-status'), statusText = hid('hero-status-text'), dot = hid('hero-dot');

        function T(ms, fn) {
            heroTimers.push(setTimeout(function () { if (myGen === heroGen) fn(); }, ms));
        }

        // Estado inicial: só o status "trabalhando", laudo vazio, score zerado.
        status.classList.remove('is-done');
        dot.classList.add('is-live');
        statusText.style.transition = 'none';
        statusText.style.opacity = '1';
        statusText.textContent = 'Consultando Receita Federal…';
        heading.textContent = '';
        score.textContent = '0.00';
        heroHide(scoreLine); heroHide(cls); heroHide(row); heroHide(evLine);

        // Fase 1 — as ferramentas consultam as fontes oficiais em sequência.
        T(780,  function () { swapStatus(statusText, 'Consultando PNCP…', myGen); });
        T(1580, function () { swapStatus(statusText, 'Cruzando sanções (CEIS/CNEP)…', myGen); });

        // Fase 2 — o laudo chega: heading digitado, score subindo, anomalia entra.
        T(2380, function () { typeInto(heading, '# Resumo Executivo', 34, myGen); });
        T(3180, function () {
            heroShow(scoreLine);
            countNumber(score, 0.87, 2, 1050, function () { return myGen === heroGen; });
        });
        T(3560, function () { heroShow(row); });
        T(3960, function () { heroShow(evLine); });
        T(4320, function () { heroShow(cls); });

        // Fase 3 — encerramento: status resolve para "Laudo pronto".
        T(4800, function () {
            swapStatus(statusText, 'Laudo pronto', myGen);
            dot.classList.remove('is-live');
            status.classList.add('is-done');
        });
    }


    /* =========================================================================
       CICLO DE VIDA DO SLIDE
       ========================================================================= */
    function activate(slide, myGen) {
        applyReveals(slide);
        animateDiagram(slide);
        animateCounts(slide, myGen);
        if (slide.id === 'slide-1') playHero();
    }
    function deactivate(slide) {
        clearReveals(slide);
        resetDiagram(slide);
        resetCounts(slide);
        if (slide.id === 'slide-1') { stopHero(); setHeroFinal(); }
    }

    function render(previous) {
        gen++;
        var myGen = gen;

        for (var i = 0; i < total; i++) {
            var s = slides[i];
            s.classList.remove('is-active', 'is-past', 'is-future');
            if (i === current) {
                s.classList.add('is-active');
                s.setAttribute('aria-hidden', 'false');
            } else {
                s.classList.add(i < current ? 'is-past' : 'is-future');
                s.setAttribute('aria-hidden', 'true');
            }
        }

        if (previous != null && previous !== current) {
            deactivate(slides[previous]);
        }
        activate(slides[current], myGen);

        if (progressFill) {
            progressFill.style.transform = 'scaleX(' + ((current + 1) / total) + ')';
        }
        if (counterCur) {
            counterCur.textContent = ('0' + (current + 1)).slice(-2);
        }
        try { history.replaceState(null, '', '#' + (current + 1)); } catch (e) { /* file:// */ }
    }

    function go(target) {
        var next = clamp(target);
        if (next === current) return;
        var previous = current;
        current = next;
        animating = true;
        render(previous);
        window.setTimeout(function () { animating = false; }, 420);
    }


    /* =========================================================================
       NAVEGAÇÃO — exclusivamente pelas setas do teclado
       ========================================================================= */
    document.addEventListener('keydown', function (e) {
        if (e.defaultPrevented) return;
        if (e.key === 'ArrowRight') {
            e.preventDefault();
            if (!animating) go(current + 1);
        } else if (e.key === 'ArrowLeft') {
            e.preventDefault();
            if (!animating) go(current - 1);
        }
    });

    // Estado inicial — respeita um deep-link no hash, se houver.
    var fromHash = parseInt((window.location.hash || '').replace('#', ''), 10);
    if (!isNaN(fromHash)) current = clamp(fromHash - 1);
    if (counterTot) counterTot.textContent = ('0' + total).slice(-2);

    render(null);
})();
