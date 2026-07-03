/**
 * =============================================================================
 * AUDITOR CIDADÃO — CHAT
 * chat.js — Modal de upload, seleção de estado/município e streaming SSE
 * =============================================================================
 */
(function () {
'use strict';

const API_BASE = '';

/** Deve ficar em sincronia com MAX_BYTES em app/api/root_upload.py — checagem
 * client-side é só uma otimização de UX (feedback instantâneo), o backend
 * continua sendo a validação real. */
const MAX_UPLOAD_BYTES = 20 * 1024 * 1024;

const state = {
    estado:       '',
    municipio:    '',
    threadId:     generateUUID(),
    cnpjs:        [],
    ready:        false,
    isLoading:    false,
    selectedFile: null,
};

const $ = (id) => document.getElementById(id);

const dom = {
    // Nav
    locationPill:  $('location-pill'),
    locationLabel: $('location-label'),
    btnReset:      $('btn-reset'),

    // Modal
    modalOverlay:  $('modal-overlay'),
    inputEstado:      $('input-estado'),
    estadoListbox:    $('estado-listbox'),
    inputMunicipio:   $('input-municipio'),
    municipioListbox: $('municipio-listbox'),
    uploadZone:    $('upload-zone'),
    fileInput:     $('file-input'),
    fileInfo:      $('file-info'),
    fileNameDisplay: $('file-name-display'),
    btnRemoveFile: $('btn-remove-file'),
    modalError:    $('modal-error'),
    modalLoading:  $('modal-loading'),
    modalLoadingText: $('modal-loading-text'),
    btnConfirm:    $('btn-confirm'),

    // Chat
    chatHead:      $('chat-head'),
    chatScroll:    $('chat-scroll'),
    chatEmpty:     $('chat-empty'),
    chatMessages:  $('chat-messages'),
    chatInput:     $('chat-input'),
    btnSend:       $('btn-send'),
    btnJumpBottom: $('btn-jump-bottom'),
    suggestionChips: $('suggestion-chips'),

    // Toast
    toast: $('toast'),
};

/** true quando o usuário rolou pra cima manualmente durante uma resposta —
 * o auto-scroll para de forçar o fundo até ele voltar ou clicar em "Novo conteúdo". */
let userScrolledUp = false;

/** Controller da requisição de streaming em andamento, usado pelo botão de parar. */
let currentAbortController = null;

const SEND_ICON = `<svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18" aria-hidden="true"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>`;
const STOP_ICON = `<svg viewBox="0 0 24 24" fill="currentColor" width="16" height="16" aria-hidden="true"><rect x="5" y="5" width="14" height="14" rx="2"/></svg>`;


/* =============================================================================
   UTILITÁRIOS
   ============================================================================= */

function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = (Math.random() * 16) | 0;
        return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
    });
}

function agora() {
    return new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}

/** Remove acentos via decomposição NFD + filtro das marcas diacríticas combinantes
 * (código Unicode 0x0300–0x036F) que sobram depois da decomposição — usado tanto
 * na busca do combobox quanto para gerar as classes CSS .risk-baixo/.risk-medio/
 * .risk-alto/.risk-critico. Filtra por código numérico em vez de um character
 * class de regex para não depender de colar marcas combinantes literais no fonte. */
function removerAcentos(texto) {
    const DIACRITICO_INICIO = 0x0300;
    const DIACRITICO_FIM    = 0x036f;
    return Array.from((texto || '').normalize('NFD'))
        .filter((ch) => {
            const codigo = ch.codePointAt(0);
            return codigo < DIACRITICO_INICIO || codigo > DIACRITICO_FIM;
        })
        .join('');
}

function riskClass(nivel) {
    return removerAcentos(nivel).toLowerCase();
}

/** Rola o histórico pro fundo, a menos que o usuário tenha rolado pra cima
 * manualmente — nesse caso só o clique em "Novo conteúdo" (force=true) ou o
 * início de um novo turno força o scroll de volta. */
function scrollChatToBottom(force = false) {
    if (userScrolledUp && !force) return;
    dom.chatScroll.scrollTo({ top: dom.chatScroll.scrollHeight, behavior: 'smooth' });
}

function syncJumpButton() {
    dom.btnJumpBottom.classList.toggle('hidden', !userScrolledUp);
}

/** Renderiza Markdown do agente sanitizando o HTML gerado pelo `marked` com
 * DOMPurify antes de injetar via innerHTML — o texto passa por conteúdo de
 * fontes menos confiáveis que o próprio raciocínio do LLM (busca web, PDF do
 * edital), então tratamos como HTML potencialmente hostil. */
function renderMarkdown(el, texto) {
    el.innerHTML = DOMPurify.sanitize(marked.parse(texto));
}

function showToast(mensagem, tipo = 'info') {
    dom.toast.textContent = mensagem;
    dom.toast.className = `toast ${tipo}`;
    dom.toast.classList.remove('hidden');

    clearTimeout(dom.toast._timer);
    dom.toast._timer = setTimeout(() => {
        dom.toast.classList.add('hidden');
    }, 4000);
}

function syncLocationPill() {
    if (!state.ready) {
        dom.locationPill.classList.add('hidden');
        return;
    }
    dom.locationLabel.textContent = `${state.municipio} · ${state.estado.toUpperCase()}`;
    dom.locationPill.classList.remove('hidden');
}


/* =============================================================================
   COMBOBOX DE ESTADO E MUNICÍPIO
   ============================================================================= */

const ESTADOS = [
    { sigla: 'AC', nome: 'Acre' }, { sigla: 'AL', nome: 'Alagoas' }, { sigla: 'AP', nome: 'Amapá' },
    { sigla: 'AM', nome: 'Amazonas' }, { sigla: 'BA', nome: 'Bahia' }, { sigla: 'CE', nome: 'Ceará' },
    { sigla: 'DF', nome: 'Distrito Federal' }, { sigla: 'ES', nome: 'Espírito Santo' }, { sigla: 'GO', nome: 'Goiás' },
    { sigla: 'MA', nome: 'Maranhão' }, { sigla: 'MT', nome: 'Mato Grosso' }, { sigla: 'MS', nome: 'Mato Grosso do Sul' },
    { sigla: 'MG', nome: 'Minas Gerais' }, { sigla: 'PA', nome: 'Pará' }, { sigla: 'PB', nome: 'Paraíba' },
    { sigla: 'PR', nome: 'Paraná' }, { sigla: 'PE', nome: 'Pernambuco' }, { sigla: 'PI', nome: 'Piauí' },
    { sigla: 'RJ', nome: 'Rio de Janeiro' }, { sigla: 'RN', nome: 'Rio Grande do Norte' }, { sigla: 'RS', nome: 'Rio Grande do Sul' },
    { sigla: 'RO', nome: 'Rondônia' }, { sigla: 'RR', nome: 'Roraima' }, { sigla: 'SC', nome: 'Santa Catarina' },
    { sigla: 'SP', nome: 'São Paulo' }, { sigla: 'SE', nome: 'Sergipe' }, { sigla: 'TO', nome: 'Tocantins' },
];

/** Cache de municípios por UF, para não rebater na API do IBGE a cada tecla digitada. */
const municipiosCache = {};

function normalizarBusca(texto) {
    return removerAcentos(texto).toLowerCase();
}

/**
 * Busca os municípios de uma UF na API pública do IBGE, com cache em memória.
 * Nota: para o DF, a API do IBGE retorna só "Brasília" — Regiões Administrativas
 * são uma divisão do GDF, não do IBGE.
 */
async function fetchMunicipios(uf) {
    if (municipiosCache[uf]) return municipiosCache[uf];

    const response = await fetch(
        `https://servicodados.ibge.gov.br/api/v1/localidades/estados/${uf}/municipios`
    );
    if (!response.ok) {
        throw new Error(`A API do IBGE retornou status ${response.status}.`);
    }

    const data = await response.json();
    const nomes = data.map((m) => m.nome).sort((a, b) => a.localeCompare(b, 'pt-BR'));
    municipiosCache[uf] = nomes;
    return nomes;
}

/**
 * Combobox pesquisável que só aceita seleção a partir de uma lista de opções —
 * nunca um valor livre digitado. Se o campo perder foco sem confirmar uma opção,
 * o valor reverte para a última seleção válida.
 */
function createCombobox({ inputEl, listboxEl, getLabel, onQuery, onSelect }) {
    let options = [];
    let activeIndex = -1;
    let confirmedLabel = '';

    function renderOptions(opts) {
        options = opts;
        activeIndex = -1;
        listboxEl.innerHTML = '';

        if (!opts.length) {
            listboxEl.innerHTML = '<li class="combobox-empty">Nenhum resultado encontrado.</li>';
            return;
        }

        opts.forEach((opt, i) => {
            const li = document.createElement('li');
            li.className   = 'combobox-option';
            li.id          = `${listboxEl.id}-option-${i}`;
            li.setAttribute('role', 'option');
            li.textContent = getLabel(opt);

            // mousedown (não click) dispara antes do blur do input — evita que o
            // fechamento da lista no blur cancele a seleção por clique
            li.addEventListener('mousedown', (e) => {
                e.preventDefault();
                selectOption(opt);
            });

            listboxEl.appendChild(li);
        });
    }

    function openList() {
        listboxEl.classList.remove('hidden');
        inputEl.setAttribute('aria-expanded', 'true');
    }

    function closeList() {
        listboxEl.classList.add('hidden');
        inputEl.setAttribute('aria-expanded', 'false');
        inputEl.removeAttribute('aria-activedescendant');
        activeIndex = -1;
    }

    function selectOption(opt) {
        confirmedLabel = getLabel(opt);
        inputEl.value  = confirmedLabel;
        closeList();
        onSelect(opt);
    }

    function highlight(index) {
        const items = listboxEl.querySelectorAll('.combobox-option');
        items.forEach((el) => el.classList.remove('active'));

        if (index >= 0 && items[index]) {
            items[index].classList.add('active');
            items[index].scrollIntoView({ block: 'nearest' });
            inputEl.setAttribute('aria-activedescendant', items[index].id);
        } else {
            inputEl.removeAttribute('aria-activedescendant');
        }
        activeIndex = index;
    }

    inputEl.addEventListener('input', async () => {
        renderOptions(await onQuery(inputEl.value));
        openList();
    });

    inputEl.addEventListener('focus', async () => {
        if (inputEl.disabled) return;
        renderOptions(await onQuery(inputEl.value));
        openList();
    });

    inputEl.addEventListener('keydown', (e) => {
        if (listboxEl.classList.contains('hidden')) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            highlight(Math.min(activeIndex + 1, options.length - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            highlight(Math.max(activeIndex - 1, 0));
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (activeIndex >= 0 && options[activeIndex]) {
                selectOption(options[activeIndex]);
            }
        } else if (e.key === 'Escape') {
            closeList();
        }
    });

    inputEl.addEventListener('blur', () => {
        closeList();
        if (inputEl.value !== confirmedLabel) {
            inputEl.value = confirmedLabel;
        }
    });

    return {
        reset(label = '') {
            confirmedLabel = label;
            inputEl.value  = label;
        },
    };
}

const municipioCombobox = createCombobox({
    inputEl:   dom.inputMunicipio,
    listboxEl: dom.municipioListbox,
    getLabel:  (nome) => nome,
    onQuery: async (query) => {
        if (!state.estado) return [];
        const municipios = await fetchMunicipios(state.estado);
        const q = normalizarBusca(query);
        return municipios.filter((nome) => normalizarBusca(nome).includes(q));
    },
    onSelect: (nome) => {
        state.municipio = nome;
        syncConfirmButton();
    },
});

const estadoCombobox = createCombobox({
    inputEl:   dom.inputEstado,
    listboxEl: dom.estadoListbox,
    getLabel:  (uf) => `${uf.nome} (${uf.sigla})`,
    onQuery: (query) => {
        const q = normalizarBusca(query);
        return ESTADOS.filter(
            (uf) => normalizarBusca(uf.nome).includes(q) || normalizarBusca(uf.sigla).includes(q)
        );
    },
    onSelect: async (uf) => {
        state.estado    = uf.sigla;
        state.municipio = '';
        municipioCombobox.reset('');
        syncConfirmButton();

        dom.inputMunicipio.disabled    = true;
        dom.inputMunicipio.placeholder = 'Carregando municípios...';

        try {
            await fetchMunicipios(uf.sigla);
            dom.inputMunicipio.disabled    = false;
            dom.inputMunicipio.placeholder = 'Selecione um município';
        } catch (error) {
            dom.inputMunicipio.placeholder = 'Erro ao carregar municípios';
            showModalError(`Falha ao carregar municípios do IBGE: ${error.message}`);
        }
    },
});


/* =============================================================================
   MODAL — UPLOAD DE EDITAL
   ============================================================================= */

function showModalError(mensagem) {
    dom.modalError.textContent = mensagem;
    dom.modalError.classList.remove('hidden');
}

function clearModalError() {
    dom.modalError.classList.add('hidden');
}

function syncConfirmButton() {
    const valido = state.estado.length === 2 && !!state.municipio && !!state.selectedFile;
    dom.btnConfirm.disabled = !valido;
}

function setFile(file) {
    if (!file) return;
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
        showModalError('Apenas arquivos PDF são aceitos.');
        return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
        showModalError(`Arquivo muito grande (${(file.size / (1024 * 1024)).toFixed(1)} MB). O limite é de 20 MB.`);
        return;
    }

    state.selectedFile = file;
    dom.fileNameDisplay.textContent = file.name;
    dom.uploadZone.classList.add('hidden');
    dom.fileInfo.classList.remove('hidden');
    clearModalError();
    syncConfirmButton();
}

function removeFile() {
    state.selectedFile = null;
    dom.fileInput.value = '';
    dom.fileInfo.classList.add('hidden');
    dom.uploadZone.classList.remove('hidden');
    syncConfirmButton();
}

async function confirmarUpload() {
    if (dom.btnConfirm.disabled) return;

    clearModalError();
    dom.btnConfirm.disabled = true;
    dom.modalLoadingText.textContent = 'Indexando o edital… isso pode levar alguns segundos.';
    dom.modalLoading.classList.remove('hidden');

    const formData = new FormData();
    formData.append('file', state.selectedFile);
    formData.append('estado', state.estado.toUpperCase());
    formData.append('municipio', state.municipio);

    try {
        const response = await fetch(`${API_BASE}/upload/`, { method: 'POST', body: formData });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Erro HTTP ${response.status}`);
        }

        const data = await response.json();
        state.cnpjs = data.cnpjs || [];
        state.ready = true;

        dom.modalLoading.classList.add('hidden');
        dom.modalOverlay.classList.add('hidden');
        dom.chatHead.classList.add('hidden');

        dom.chatInput.disabled = false;
        dom.btnSend.disabled   = true; // segue desabilitado até haver texto
        dom.chatInput.focus();

        syncLocationPill();
        showToast(`Edital indexado! ${state.cnpjs.length} CNPJ(s) encontrado(s).`, 'success');

    } catch (error) {
        dom.modalLoading.classList.add('hidden');
        showModalError(`Falha ao indexar: ${error.message}`);
        dom.btnConfirm.disabled = false;
    }
}

function abrirModalNovaSessao() {
    // Aborta qualquer streaming em andamento — sem isso, a resposta da sessão
    // anterior continuaria rodando em segundo plano e escrevendo em elementos
    // já removidos do DOM.
    stopGeneration();
    setLoading(false);

    state.threadId     = generateUUID();
    state.cnpjs        = [];
    state.ready        = false;
    state.selectedFile = null;

    dom.fileInput.value = '';
    dom.fileInfo.classList.add('hidden');
    dom.uploadZone.classList.remove('hidden');
    estadoCombobox.reset('');
    municipioCombobox.reset('');
    state.estado    = '';
    state.municipio = '';
    dom.inputMunicipio.disabled    = true;
    dom.inputMunicipio.placeholder = 'Selecione um estado primeiro';
    clearModalError();
    dom.modalLoading.classList.add('hidden');
    syncConfirmButton();

    dom.chatMessages.innerHTML = '';
    dom.chatEmpty.classList.remove('hidden');
    dom.chatHead.classList.remove('hidden');
    dom.chatInput.disabled = true;
    dom.btnSend.disabled   = true;
    dom.chatInput.value    = '';

    syncLocationPill();
    dom.modalOverlay.classList.remove('hidden');
}


/* =============================================================================
   CHAT — RENDERIZAÇÃO DE MENSAGENS
   ============================================================================= */

function addUserMessage(texto) {
    dom.chatEmpty.classList.add('hidden');

    const el = document.createElement('div');
    el.className = 'chat-msg chat-msg-user';
    el.innerHTML = `
        <div class="msg-col">
            <div class="msg-meta"><span>Você</span><span>${agora()}</span></div>
            <div class="msg-bubble-user">${escapeHtml(texto)}</div>
        </div>
        <div class="msg-avatar">VC</div>
    `;
    dom.chatMessages.appendChild(el);

    // Novo turno sempre pula pro fundo, mesmo que o usuário tivesse rolado pra cima antes.
    userScrolledUp = false;
    syncJumpButton();
    scrollChatToBottom(true);
}

/**
 * Cria a bolha de resposta do agente com accordion de raciocínio (steps de status)
 * e um container para o laudo estruturado. Retorna referências atualizadas via streaming.
 */
function addAiMessage() {
    dom.chatEmpty.classList.add('hidden');

    const el = document.createElement('div');
    el.className = 'chat-msg';
    el.innerHTML = `
        <div class="msg-avatar msg-avatar-ai">IA</div>
        <div class="msg-col">
            <div class="msg-meta">
                <span>Auditor Cidadão</span><span>${agora()}</span>
                <button class="msg-copy-btn material-symbols-outlined" title="Copiar resposta" aria-label="Copiar resposta" disabled>content_copy</button>
            </div>
            <details class="reasoning" open>
                <summary class="reasoning-summary">
                    <span class="reasoning-arrow material-symbols-outlined" aria-hidden="true">chevron_right</span>
                    <span class="reasoning-label">Auditando…</span>
                    <span class="spinner reasoning-spinner"></span>
                </summary>
                <div class="reasoning-body"></div>
            </details>
            <div class="msg-markdown"></div>
            <div class="laudo-card hidden"></div>
        </div>
    `;
    dom.chatMessages.appendChild(el);
    scrollChatToBottom();

    return {
        msgEl:          el,
        reasoningEl:    el.querySelector('.reasoning'),
        reasoningBody:  el.querySelector('.reasoning-body'),
        reasoningLabel: el.querySelector('.reasoning-label'),
        reasoningSpinner: el.querySelector('.reasoning-spinner'),
        markdownEl:     el.querySelector('.msg-markdown'),
        laudoEl:        el.querySelector('.laudo-card'),
        copyBtn:        el.querySelector('.msg-copy-btn'),
    };
}

/** Habilita o botão de copiar da mensagem com o texto final (Markdown cru). */
function enableCopyButton(refs, texto) {
    refs.copyBtn.disabled = false;
    refs.copyBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(texto)
            .then(() => showToast('Resposta copiada!', 'success'))
            .catch(() => showToast('Não foi possível copiar.', 'error'));
    });
}

/** Anexa um botão de nova tentativa após uma falha real (não usado em abort manual):
 * remove a bolha com erro e reenvia a mesma pergunta como um novo turno do agente. */
function addRetryButton(refs, texto) {
    const btn = document.createElement('button');
    btn.className = 'btn btn-outline btn-sm retry-btn';
    btn.innerHTML = '<span class="material-symbols-outlined" aria-hidden="true">refresh</span><span>Tentar novamente</span>';
    btn.addEventListener('click', () => {
        refs.msgEl.remove();
        streamAgentResponse(texto);
    }, { once: true });
    refs.markdownEl.after(btn);
}

function addReasoningStep(reasoningBody, texto) {
    const prevPending = reasoningBody.querySelector('.reasoning-step:last-child:not(.done)');
    if (prevPending) prevPending.classList.add('done');

    const stepEl = document.createElement('div');
    stepEl.className = 'reasoning-step';
    stepEl.innerHTML = `<span class="reasoning-step-icon">›</span><span>${escapeHtml(texto)}</span>`;
    reasoningBody.appendChild(stepEl);
}

function finalizeReasoning(refs) {
    const lastStep = refs.reasoningBody.querySelector('.reasoning-step:last-child:not(.done)');
    if (lastStep) lastStep.classList.add('done');

    const checkEl = document.createElement('span');
    checkEl.className = 'reasoning-check material-symbols-outlined';
    checkEl.setAttribute('aria-hidden', 'true');
    checkEl.textContent = 'check';
    refs.reasoningSpinner.replaceWith(checkEl);
    const stepCount = refs.reasoningBody.querySelectorAll('.reasoning-step').length;
    refs.reasoningLabel.textContent = stepCount > 0
        ? `Raciocínio do agente (${stepCount} etapa${stepCount > 1 ? 's' : ''})`
        : 'Raciocínio do agente';

    refs.reasoningEl.removeAttribute('open');
}

/** Evidências que citam a fonte (ex.: "Fonte: CEIS") viram um chip destacado
 * em vez de um item de lista comum, reforçando a rastreabilidade do laudo. */
function formatEvidencia(ev) {
    const fonteMatch = ev.match(/^fonte:\s*(.+)$/i);
    if (fonteMatch) {
        return `<li class="evidencia-fonte"><span class="fonte-chip"><span class="material-symbols-outlined" aria-hidden="true">link</span> ${escapeHtml(fonteMatch[1])}</span></li>`;
    }
    return `<li>${escapeHtml(ev)}</li>`;
}

function renderLaudoEstruturado(container, laudo) {
    const anomaliasHtml = (laudo.anomalias || []).map((a) => `
        <div class="anomalia-card">
            <div class="anomalia-card-header">
                <span class="anomalia-codigo">${escapeHtml(a.codigo)}</span>
                <span class="risk-badge risk-${riskClass(a.nivel_risco)}">${escapeHtml(a.nivel_risco)}</span>
            </div>
            <div class="anomalia-descricao">${escapeHtml(a.descricao)}</div>
            ${a.evidencias && a.evidencias.length
                ? `<ul class="anomalia-evidencias">${a.evidencias.map(formatEvidencia).join('')}</ul>`
                : ''}
        </div>
    `).join('');

    const recomendacoesHtml = (laudo.recomendacoes || []).length
        ? `<ul class="laudo-recomendacoes">${laudo.recomendacoes.map((r) => `<li>${escapeHtml(r)}</li>`).join('')}</ul>`
        : '';

    container.innerHTML = `
        <div class="laudo-header">
            <span class="laudo-title"><span class="material-symbols-outlined" aria-hidden="true">fact_check</span> Laudo Estruturado</span>
            <span class="risk-badge risk-${riskClass(laudo.nivel_risco_geral)}">${escapeHtml(laudo.nivel_risco_geral)}</span>
        </div>
        <p class="laudo-resumo">${escapeHtml(laudo.resumo_executivo)}</p>
        ${anomaliasHtml}
        ${recomendacoesHtml}
    `;
    container.classList.remove('hidden');
}


/* =============================================================================
   CHAT — ENVIO E STREAMING SSE
   ============================================================================= */

/** Alterna o botão de enviar entre os estados "enviar" (ocioso) e "parar"
 * (streaming em andamento) — o botão nunca fica desabilitado durante o
 * streaming, já que nesse estado ele serve pra abortar a geração. */
function syncSendButton() {
    if (state.isLoading) {
        dom.btnSend.disabled = false;
        dom.btnSend.classList.add('is-stop');
        dom.btnSend.setAttribute('aria-label', 'Parar geração');
        dom.btnSend.innerHTML = STOP_ICON;
    } else {
        dom.btnSend.classList.remove('is-stop');
        dom.btnSend.setAttribute('aria-label', 'Enviar pergunta');
        dom.btnSend.innerHTML = SEND_ICON;
        dom.btnSend.disabled = !state.ready || !dom.chatInput.value.trim();
    }
}

function setLoading(loading) {
    state.isLoading = loading;
    syncSendButton();
}

function stopGeneration() {
    if (currentAbortController) currentAbortController.abort();
}

async function sendMessage() {
    const texto = dom.chatInput.value.trim();
    if (!texto || state.isLoading || !state.ready) return;

    dom.chatInput.value = '';
    dom.chatInput.style.height = 'auto';
    syncSendButton();

    addUserMessage(texto);
    await streamAgentResponse(texto);
}

/** Executa um turno completo do agente para `texto`: cria a bolha de resposta,
 * consome o streaming SSE e trata os três desfechos possíveis — sucesso,
 * interrupção manual (botão de parar) e erro real (com opção de tentar de novo). */
async function streamAgentResponse(texto) {
    setLoading(true);

    const refs = addAiMessage();
    let accumulated = '';
    let leftover    = '';
    let hasSteps    = false;
    let streamError = null;

    const abortController = new AbortController();
    currentAbortController = abortController;

    try {
        const response = await fetch(`${API_BASE}/conversar-com-auditor/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                pergunta:    texto,
                estado:      state.estado.toUpperCase(),
                municipio:   state.municipio,
                lista_cnpjs: state.cnpjs,
                thread_id:   state.threadId,
            }),
            signal: abortController.signal,
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Erro HTTP ${response.status}`);
        }

        const reader  = response.body.getReader();
        const decoder = new TextDecoder('utf-8');

        streamLoop:
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const text = leftover + decoder.decode(value, { stream: true });
            leftover = '';
            const lines = text.split('\n');

            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];

                if (line.startsWith('data: ')) {
                    const payload = line.slice(6);
                    try {
                        const event = JSON.parse(payload);

                        if (event.type === 'token' && event.content) {
                            accumulated += event.content;
                        } else if (event.type === 'status' && event.content) {
                            addReasoningStep(refs.reasoningBody, event.content);
                            hasSteps = true;
                            scrollChatToBottom();
                        } else if (event.type === 'laudo_estruturado' && event.content) {
                            renderLaudoEstruturado(refs.laudoEl, event.content);
                            scrollChatToBottom();
                        } else if (event.type === 'laudo_estruturado_erro') {
                            // Extração estruturada falhou no backend, mas o texto do laudo já
                            // chegou com sucesso — apenas avisa, sem interromper o streaming.
                            showToast(event.content || 'Não foi possível gerar a versão estruturada do laudo.', 'error');
                        } else if (event.type === 'error') {
                            streamError = event.content || 'Erro desconhecido durante o streaming.';
                            break streamLoop;
                        } else if (event.type === 'done') {
                            break streamLoop;
                        }
                    } catch {
                        accumulated += payload;
                    }
                } else if (line === '' && i < lines.length - 1) {
                    continue;
                } else if (line !== '' && i === lines.length - 1) {
                    leftover = line;
                }
            }

            if (accumulated) {
                renderMarkdown(refs.markdownEl, accumulated);
            }
            scrollChatToBottom();
        }

        if (streamError) {
            throw new Error(streamError);
        }

        renderMarkdown(refs.markdownEl, accumulated.trim() ? accumulated : '*(resposta vazia)*');

        if (!hasSteps) {
            refs.reasoningEl.classList.add('hidden');
        } else {
            finalizeReasoning(refs);
        }

        enableCopyButton(refs, accumulated);

    } catch (error) {
        if (error.name === 'AbortError') {
            // Interrupção manual via botão de parar — não é uma falha real, então
            // finaliza normalmente com o que já tinha sido gerado até então.
            const textoFinal = accumulated.trim()
                ? `${accumulated}\n\n*(interrompido pelo usuário)*`
                : '*(interrompido pelo usuário)*';
            renderMarkdown(refs.markdownEl, textoFinal);

            if (!hasSteps) {
                refs.reasoningEl.classList.add('hidden');
            } else {
                finalizeReasoning(refs);
            }
            if (accumulated.trim()) enableCopyButton(refs, accumulated);
            showToast('Geração interrompida.', 'info');
        } else {
            renderMarkdown(refs.markdownEl, `<span class="material-symbols-outlined" aria-hidden="true">error</span> **Erro ao consultar o agente:** ${escapeHtml(error.message)}`);
            showToast(`Erro: ${error.message}`, 'error');
            addRetryButton(refs, texto);
        }
    } finally {
        currentAbortController = null;
        setLoading(false);
    }
}


/* =============================================================================
   EVENT LISTENERS
   ============================================================================= */

// --- Upload: clique/drag-and-drop na zona ---
dom.uploadZone.addEventListener('click', () => dom.fileInput.click());
dom.uploadZone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        dom.fileInput.click();
    }
});
dom.fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) setFile(file);
});
dom.uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dom.uploadZone.classList.add('drag-over');
});
dom.uploadZone.addEventListener('dragleave', (e) => {
    if (!dom.uploadZone.contains(e.relatedTarget)) {
        dom.uploadZone.classList.remove('drag-over');
    }
});
dom.uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dom.uploadZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) setFile(file);
});
dom.btnRemoveFile.addEventListener('click', removeFile);

// --- Modal: confirmar upload ---
dom.btnConfirm.addEventListener('click', confirmarUpload);

// --- Reiniciar sessão ---
dom.btnReset.addEventListener('click', abrirModalNovaSessao);

// --- Enviar mensagem / parar geração (o mesmo botão alterna de função) ---
dom.btnSend.addEventListener('click', () => {
    if (state.isLoading) {
        stopGeneration();
    } else {
        sendMessage();
    }
});
dom.chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});
dom.chatInput.addEventListener('input', () => {
    dom.chatInput.style.height = 'auto';
    dom.chatInput.style.height = Math.min(dom.chatInput.scrollHeight, 180) + 'px';
    syncSendButton();
});

// --- Auto-scroll que respeita o usuário: detecta scroll manual pra cima ---
dom.chatScroll.addEventListener('scroll', () => {
    const distanceFromBottom = dom.chatScroll.scrollHeight - dom.chatScroll.scrollTop - dom.chatScroll.clientHeight;
    userScrolledUp = distanceFromBottom > 80;
    syncJumpButton();
});
dom.btnJumpBottom.addEventListener('click', () => {
    userScrolledUp = false;
    syncJumpButton();
    scrollChatToBottom(true);
});

// --- Prompts de exemplo clicáveis no estado vazio ---
dom.suggestionChips.addEventListener('click', (e) => {
    const chip = e.target.closest('.suggestion-chip');
    if (!chip || !state.ready || state.isLoading) return;
    dom.chatInput.value = chip.dataset.prompt;
    sendMessage();
});

// --- Fechar toast ao clicar ---
dom.toast.addEventListener('click', () => dom.toast.classList.add('hidden'));


/* =============================================================================
   INICIALIZAÇÃO
   ============================================================================= */

function init() {
    marked.setOptions({ breaks: true, gfm: true });
    syncConfirmButton();
    dom.inputEstado.focus();
    console.info('[Auditor Cidadão] Chat iniciado. Thread ID:', state.threadId);
}

init();

})();
