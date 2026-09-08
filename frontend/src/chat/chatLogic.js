/**
 * =============================================================================
 * AUDITOR CIDADÃO — CHAT
 * chatLogic.js — Modal de upload, seleção de estado/município e streaming SSE
 *
 * Continua imperativo (manipula o DOM diretamente via getElementById), em vez
 * de reescrito com estado/JSX do React: <Chat/> monta um shell estático com os
 * mesmos ids do chat.html original e chama initChat() uma única vez, depois do
 * mount, num useEffect sem dependências — o React nunca mais re-renderiza essa
 * árvore, então não há conflito de reconciliação com as mutações diretas feitas
 * aqui. Preserva o comportamento (streaming SSE, combobox, drag&drop) 1:1 com
 * o que já estava validado em produção, em vez de arriscar reintroduzir bugs
 * sutis reescrevendo tudo para hooks/estado de uma vez.
 * =============================================================================
 */
import DOMPurify from 'dompurify';
import { marked } from 'marked';

export function initChat() {

// Frontend e backend são serviços/domínios separados — mesmo em dev local, já
// que agora cada um roda com sua própria stack (Vite aqui, uvicorn lá), então
// não existe mais o caso "mesma origem" que o backend servia antes. A URL do
// backend vem de uma env var de build (ver frontend/.env.example): em dev,
// aponta pro uvicorn local; em produção, o Railway injeta a URL pública do
// serviço de backend na hora do `vite build` (ver Dockerfile).
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

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
    progressFill:  $('modal-progress-fill'),
    btnConfirm:    $('btn-confirm'),

    // Chat
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

/**
 * Extrai uma mensagem legível do corpo de erro de uma resposta HTTP não-ok. `detail` normalmente
 * é uma string (nossos HTTPException), mas num 422 de validação automática do FastAPI/Pydantic ele
 * vem como uma LISTA de objetos (`[{loc, msg, type}, ...]`) — sem tratar esse caso, `new Error(lista)`
 * vira o texto "[object Object]", que não ajuda ninguém a entender o que houve.
 */
function extrairMensagemErro(err, statusFallback) {
    if (typeof err.detail === 'string' && err.detail) return err.detail;
    if (Array.isArray(err.detail) && err.detail.length) {
        return err.detail.map((item) => item.msg || JSON.stringify(item)).join('; ');
    }
    return `Erro HTTP ${statusFallback}`;
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

/**
 * Barra de progresso do upload. O /upload/ é um stream SSE: os eventos `progress`
 * do backend definem o alvo (`setUploadTarget`) e a etapa, os `heartbeat` empurram
 * a barra devagar enquanto o Docling roda. A barra só chega a 100% no `done`.
 * `startUploadProgress` roda um easing suave entre os eventos.
 */
let progressTimer = null;
let progressoAtual = 0;
let progressoAlvo = 0;

/**
 * Submensagens que giram durante uma etapa longa (o Docling fica ~2 min sem emitir
 * nenhum `progress`). Trocar o texto de tempos em tempos comunica "ainda estou
 * vivo" melhor do que a barra sozinha. Um `progress` real reinicia o ciclo com o
 * texto da etapa nova na frente.
 */
const UPLOAD_SUBMENSAGENS = {
    extracao: [
        'Lendo o documento…',
        'Identificando títulos e seções…',
        'Reconstruindo tabelas…',
        'Organizando a hierarquia do edital…',
    ],
    indexacao: [
        'Gerando os vetores dos trechos…',
        'Gravando as seções…',
        'Quase lá…',
    ],
};

let mensagemTimer = null;

function pararCicloDeMensagens() {
    if (mensagemTimer) clearInterval(mensagemTimer);
    mensagemTimer = null;
}

/** Mostra `mensagens[0]` e passa para a próxima a cada ~9 s, em loop. */
function ciclarMensagens(mensagens) {
    pararCicloDeMensagens();
    dom.modalLoadingText.textContent = mensagens[0];
    if (mensagens.length < 2) return;
    let i = 0;
    mensagemTimer = setInterval(() => {
        i = (i + 1) % mensagens.length;
        dom.modalLoadingText.textContent = mensagens[i];
    }, 9000);
}

function setProgress(pct) {
    if (dom.progressFill) dom.progressFill.style.width = `${pct}%`;
}

/** Alvo monotônico (só sobe), com teto em 96% até o evento `done`. */
function setUploadTarget(pct) {
    progressoAlvo = Math.min(96, Math.max(progressoAlvo, pct));
}

function stopUploadProgress() {
    if (progressTimer) clearInterval(progressTimer);
    progressTimer = null;
    pararCicloDeMensagens();
}

function startUploadProgress() {
    stopUploadProgress();
    progressoAtual = 0;
    progressoAlvo = 8;
    setProgress(0);
    progressTimer = setInterval(() => {
        progressoAtual += Math.max(0.25, (progressoAlvo - progressoAtual) * 0.07);
        progressoAtual = Math.min(progressoAtual, progressoAlvo);
        setProgress(progressoAtual);
    }, 250);
}

function finishUploadProgress() {
    stopUploadProgress();
    setProgress(100);
}

/** Lê o SSE do /upload/: os eventos `progress`/`heartbeat` movem a barra; resolve
 * com a lista de CNPJs no `done`, ou lança no `error` / se a conexão cair antes. */
async function consumirStreamUpload(response) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    while (true) {
        const { value, done } = await reader.read();
        if (done) throw new Error('a conexão caiu antes da confirmação');

        buffer += decoder.decode(value, { stream: true });
        const linhas = buffer.split('\n');
        buffer = linhas.pop(); // a última pode ter chegado cortada

        for (const linha of linhas) {
            if (!linha.startsWith('data: ')) continue;
            let ev;
            try { ev = JSON.parse(linha.slice(6)); } catch { continue; }

            if (ev.type === 'progress') {
                // etapa nova: o texto do backend na frente, depois giram as submensagens
                const subs = ev.pct >= 80 ? UPLOAD_SUBMENSAGENS.indexacao
                    : ev.pct >= 30 ? UPLOAD_SUBMENSAGENS.extracao
                    : [];
                ciclarMensagens([ev.content, ...subs]);
                if (typeof ev.pct === 'number') setUploadTarget(ev.pct);
            } else if (ev.type === 'heartbeat') {
                setUploadTarget(progressoAlvo + 1);
            } else if (ev.type === 'done') {
                return ev.cnpjs || [];
            } else if (ev.type === 'error') {
                throw new Error(ev.content || 'erro na indexação');
            }
        }
    }
}

async function confirmarUpload() {
    if (dom.btnConfirm.disabled) return;

    clearModalError();
    dom.btnConfirm.disabled = true;
    dom.modalLoadingText.textContent = 'Enviando o edital…';
    startUploadProgress();
    dom.modalLoading.classList.remove('hidden');

    const formData = new FormData();
    formData.append('file', state.selectedFile);
    formData.append('estado', state.estado.toUpperCase());
    formData.append('municipio', state.municipio);
    formData.append('thread_id', state.threadId);

    try {
        const response = await fetch(`${API_BASE}/upload/`, {
            method: 'POST',
            body: formData,
            credentials: 'include',
        });

        // 415/413/429 ainda vêm como HTTP normal, antes do stream começar.
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(extrairMensagemErro(err, response.status));
        }

        const cnpjs = await consumirStreamUpload(response);
        state.cnpjs = cnpjs;
        state.ready = true;

        // Preenche até 100% e deixa a barra cheia visível por um instante antes de fechar.
        finishUploadProgress();
        dom.modalLoadingText.textContent = 'Pronto!';
        await new Promise((resolve) => setTimeout(resolve, 350));

        dom.modalLoading.classList.add('hidden');
        dom.modalOverlay.classList.add('hidden');

        dom.chatInput.disabled = false;
        dom.btnSend.disabled   = true; // segue desabilitado até haver texto

        syncLocationPill();
        showToast(`Edital indexado! ${cnpjs.length} CNPJ(s) encontrado(s).`, 'success');

        // O agente "fala primeiro": o relatório inicial entra como o primeiro turno
        // da thread, via streaming SSE, em vez de bloquear o /upload/ por minutos.
        streamAgentResponse('', { inicial: true });

    } catch (error) {
        stopUploadProgress();
        setProgress(0);
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
 * Retorna referências atualizadas via streaming.
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
 * remove a bolha com erro e reenvia o mesmo turno do agente. */
function addRetryButton(refs, texto, { inicial = false } = {}) {
    const btn = document.createElement('button');
    btn.className = 'btn btn-outline btn-sm retry-btn';
    btn.innerHTML = '<span class="material-symbols-outlined" aria-hidden="true">refresh</span><span>Tentar novamente</span>';
    btn.addEventListener('click', () => {
        refs.msgEl.remove();
        streamAgentResponse(texto, { inicial });
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
 * interrupção manual (botão de parar) e erro real (com opção de tentar de novo).
 * `inicial: true` é o primeiro turno pós-upload (relatório automático): o backend
 * ignora `texto` e usa o prompt do relatório inicial. */
async function streamAgentResponse(texto, { inicial = false } = {}) {
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
                inicial,
                estado:      state.estado.toUpperCase(),
                municipio:   state.municipio,
                lista_cnpjs: state.cnpjs,
                thread_id:   state.threadId,
            }),
            signal: abortController.signal,
            credentials: 'include',
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(extrairMensagemErro(err, response.status));
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

            // Cada chunk de rede pode conter várias linhas SSE — e a última pode ter chegado
            // cortada no meio. Processamos linha a linha; a linha incompleta do fim é guardada
            // em `leftover` para ser completada quando o próximo chunk chegar.
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i];

                // A última linha só está COMPLETA se o texto terminou em '\n'. Se não terminou,
                // ela foi cortada pela fronteira do chunk de rede (ex.: veio só 'data: {"type":"to').
                // Guardamos em `leftover` e completamos no próximo read — isso vale INCLUSIVE para
                // linhas que começam com 'data:'. Sem esse tratamento, uma linha partida cairia no
                // JSON.parse abaixo, falharia, e o pedaço quebrado vazaria como texto na resposta.
                if (i === lines.length - 1 && line !== '' && !text.endsWith('\n')) {
                    leftover = line;
                    break;
                }

                // Linha em branco é apenas o separador entre eventos SSE — nada a processar.
                if (line === '') continue;

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
                        } else if (event.type === 'error') {
                            streamError = event.content || 'Erro desconhecido durante o streaming.';
                            break streamLoop;
                        } else if (event.type === 'done') {
                            break streamLoop;
                        }
                    } catch {
                        // Só deve cair aqui se o backend mandar um payload realmente malformado —
                        // linha cortada no meio já foi tratada pelo `leftover` acima.
                        accumulated += payload;
                    }
                }
            }

            if (accumulated) {
                renderMarkdown(refs.markdownEl, accumulated);
                // Cursor ▍ no fim do texto enquanto a resposta ainda chega —
                // o CSS (.is-streaming) desenha e anima; removido no finally.
                refs.markdownEl.classList.add('is-streaming');
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
            addRetryButton(refs, texto, { inicial });
        }
    } finally {
        refs.markdownEl.classList.remove('is-streaming');
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

}
