/**
 * =============================================================================
 * AUDITOR CIDADÃO — PAINEL DE TESTES
 * app.js — Toda a lógica de interação com a API e atualização da UI
 * =============================================================================
 */

/* =============================================================================
   1. CONFIGURAÇÃO
   ============================================================================= */

/** URL base da API. Por padrão usa a mesma origem (FastAPI serve o frontend). */
const API_BASE = '';


/* =============================================================================
   2. ESTADO DA APLICAÇÃO
   ============================================================================= */

const state = {
    userName:   '',
    estado:     '',
    municipio:  '',
    threadId:   generateUUID(),
    cnpjs:      [],
    isUploaded: false,
    isLoading:  false,
    turns:      0,
    selectedFile: null,
};


/* =============================================================================
   3. REFERÊNCIAS AO DOM
   ============================================================================= */

const $ = (id) => document.getElementById(id);

const dom = {
    // Header
    sessionIdDisplay: $('session-id-display'),
    btnNovaSessao:    $('btn-nova-sessao'),

    // Config
    inputUsername:    $('input-username'),
    inputEstado:      $('input-estado'),
    inputMunicipio:   $('input-municipio'),

    // Upload
    uploadZone:       $('upload-zone'),
    fileInput:        $('file-input'),
    fileInfo:         $('file-info'),
    fileNameDisplay:  $('file-name-display'),
    btnRemoveFile:    $('btn-remove-file'),
    btnUpload:        $('btn-upload'),
    uploadStatus:     $('upload-status'),

    // CNPJs
    cardCnpjs:        $('card-cnpjs'),
    cnpjList:         $('cnpj-list'),

    // Debug
    debugBase:        $('debug-base'),
    debugThread:      $('debug-thread'),
    debugIndexed:     $('debug-indexed'),
    debugCnpjs:       $('debug-cnpjs'),
    debugTurns:       $('debug-turns'),

    // Chat
    chatMessages:     $('chat-messages'),
    chatEmpty:        $('chat-empty'),
    typingIndicator:  $('typing-indicator'),
    chatInput:        $('chat-input'),
    btnSend:          $('btn-send'),

    // Toast
    toast:            $('toast'),
};


/* =============================================================================
   4. FUNÇÕES UTILITÁRIAS
   ============================================================================= */

/**
 * Gera um UUID v4 para identificar a sessão de conversa.
 * @returns {string} UUID no formato xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
 */
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = (Math.random() * 16) | 0;
        return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
    });
}

/**
 * Formata um CNPJ numérico (14 dígitos) para exibição com máscara.
 * @param {string} cnpj - CNPJ com ou sem máscara
 * @returns {string} CNPJ no formato XX.XXX.XXX/XXXX-XX
 */
function formatarCNPJ(cnpj) {
    const limpo = cnpj.replace(/\D/g, '');
    if (limpo.length !== 14) return cnpj;
    return limpo.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, '$1.$2.$3/$4-$5');
}

/**
 * Formata a hora atual para o timestamp das mensagens.
 * @returns {string} Hora no formato HH:MM
 */
function agora() {
    return new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

/**
 * Exibe um toast de notificação temporário.
 * @param {string} mensagem - Texto da notificação
 * @param {'success'|'error'|'info'} tipo - Tipo visual do toast
 */
function showToast(mensagem, tipo = 'info') {
    dom.toast.textContent = mensagem;
    dom.toast.className = `toast ${tipo}`;
    dom.toast.classList.remove('hidden');

    clearTimeout(dom.toast._timer);
    dom.toast._timer = setTimeout(() => {
        dom.toast.classList.add('hidden');
    }, 4000);
}

/**
 * Atualiza o painel de debug com os valores do estado atual.
 */
function syncDebug() {
    dom.debugThread.textContent   = state.threadId;
    dom.debugThread.title         = state.threadId;
    dom.debugIndexed.textContent  = state.isUploaded ? 'Sim ✓' : 'Não';
    dom.debugCnpjs.textContent    = state.cnpjs.length;
    dom.debugTurns.textContent    = state.turns;
}

/**
 * Atualiza o display do Thread ID no header e no debug.
 */
function syncSessionDisplay() {
    const short = state.threadId.substring(0, 18) + '…';
    dom.sessionIdDisplay.textContent = short;
    dom.sessionIdDisplay.title       = state.threadId;
    syncDebug();
}

/**
 * Controla o estado de loading da interface (desabilita inputs e mostra indicador).
 * @param {boolean} loading
 */
function setLoading(loading) {
    state.isLoading = loading;
    dom.btnSend.disabled    = loading || !state.isUploaded;
    dom.chatInput.disabled  = loading || !state.isUploaded;
    dom.typingIndicator.classList.toggle('hidden', !loading);

    if (loading) {
        dom.chatMessages.scrollTo({ top: dom.chatMessages.scrollHeight, behavior: 'smooth' });
    }
}


/* =============================================================================
   5. LÓGICA DE UPLOAD
   ============================================================================= */

/**
 * Define o arquivo selecionado e atualiza a UI de upload.
 * @param {File} file - Arquivo PDF selecionado
 */
function setFile(file) {
    if (!file) return;

    state.selectedFile = file;
    dom.fileNameDisplay.textContent = file.name;
    dom.uploadZone.classList.add('hidden');
    dom.fileInfo.classList.remove('hidden');
    dom.btnUpload.disabled = false;
    dom.uploadStatus.className = 'status-msg hidden';
}

/**
 * Remove o arquivo selecionado e reseta a área de upload.
 */
function removeFile() {
    state.selectedFile = null;
    dom.fileInput.value = '';
    dom.fileInfo.classList.add('hidden');
    dom.uploadZone.classList.remove('hidden');
    dom.btnUpload.disabled = true;
    dom.uploadStatus.className = 'status-msg hidden';
}

/**
 * Valida se os campos obrigatórios estão preenchidos antes do upload.
 * @returns {boolean}
 */
function validarCampos() {
    if (!state.userName) {
        showToast('Preencha seu nome antes de indexar.', 'error');
        dom.inputUsername.focus();
        return false;
    }
    if (!state.estado || state.estado.length !== 2) {
        showToast('Informe a sigla do estado (2 letras).', 'error');
        dom.inputEstado.focus();
        return false;
    }
    if (!state.municipio) {
        showToast('Informe o município.', 'error');
        dom.inputMunicipio.focus();
        return false;
    }
    return true;
}

/**
 * Faz o upload e indexação do PDF via POST /upload/.
 */
async function uploadEdital() {
    if (!validarCampos() || !state.selectedFile) return;

    dom.btnUpload.disabled = true;
    dom.uploadStatus.textContent = '⏳ Indexando... isso pode levar alguns segundos.';
    dom.uploadStatus.className = 'status-msg loading';
    dom.uploadStatus.classList.remove('hidden');

    const formData = new FormData();
    formData.append('file', state.selectedFile);
    formData.append('estado', state.estado.toUpperCase());
    formData.append('municipio', state.municipio);
    formData.append('user_name', state.userName);

    try {
        const response = await fetch(`${API_BASE}/upload/`, {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Erro HTTP ${response.status}`);
        }

        const data = await response.json();
        state.cnpjs     = data.cnpjs || [];
        state.isUploaded = true;

        // Feedback de sucesso
        dom.uploadStatus.textContent = `✅ Edital indexado! ${state.cnpjs.length} CNPJ(s) encontrado(s).`;
        dom.uploadStatus.className   = 'status-msg success';

        // Habilita o chat
        dom.chatInput.disabled = false;
        dom.btnSend.disabled   = false;
        dom.chatInput.placeholder = 'Faça uma pergunta sobre o edital...';

        // Exibe CNPJs
        renderCNPJs(state.cnpjs);
        syncDebug();
        showToast('Edital indexado com sucesso!', 'success');

    } catch (error) {
        dom.uploadStatus.textContent = `❌ Erro: ${error.message}`;
        dom.uploadStatus.className   = 'status-msg error';
        dom.btnUpload.disabled       = false;
        showToast(`Falha no upload: ${error.message}`, 'error');
    }
}

/**
 * Renderiza os badges de CNPJ no painel lateral.
 * @param {string[]} cnpjs - Lista de CNPJs numéricos
 */
function renderCNPJs(cnpjs) {
    dom.cnpjList.innerHTML = '';

    if (!cnpjs.length) {
        dom.cnpjList.innerHTML = '<span style="font-size:12px;color:var(--text-muted)">Nenhum CNPJ encontrado.</span>';
    } else {
        cnpjs.forEach((cnpj) => {
            const badge = document.createElement('span');
            badge.className  = 'cnpj-badge';
            badge.textContent = formatarCNPJ(cnpj);
            badge.title      = cnpj;
            badge.setAttribute('role', 'listitem');
            dom.cnpjList.appendChild(badge);
        });
    }

    dom.cardCnpjs.classList.remove('hidden');
}


/* =============================================================================
   6. LÓGICA DE CHAT
   ============================================================================= */

/**
 * Adiciona uma bolha de mensagem à área de chat.
 * @param {'user'|'ai'} role - Remetente da mensagem
 * @param {string} content   - Conteúdo da mensagem (texto para user, markdown para ai)
 */
function addMessage(role, content) {
    // Remove estado vazio se ainda estiver visível
    if (!dom.chatEmpty.classList.contains('hidden')) {
        dom.chatEmpty.classList.add('hidden');
    }

    const avatarEmoji = role === 'user' ? '👤' : '🤖';
    const labelText   = role === 'user' ? (state.userName || 'Você') : 'Auditor Cidadão';
    const timestamp   = agora();

    // Renderiza markdown para mensagens do agente; escapa HTML para o usuário
    const bubbleContent = role === 'ai'
        ? marked.parse(content)
        : escapeHtml(content).replace(/\n/g, '<br>');

    const messageEl = document.createElement('div');
    messageEl.className = `message ${role}`;
    messageEl.innerHTML = `
        <div class="message-avatar noto-emoji" aria-hidden="true">${avatarEmoji}</div>
        <div class="message-body">
            <div class="message-meta">
                <span>${labelText}</span>
                <span>${timestamp}</span>
            </div>
            <div class="message-bubble">${bubbleContent}</div>
        </div>
    `;

    dom.chatMessages.appendChild(messageEl);
    dom.chatMessages.scrollTo({ top: dom.chatMessages.scrollHeight, behavior: 'smooth' });
}

/**
 * Escapa caracteres HTML perigosos para prevenir XSS em mensagens do usuário.
 * @param {string} text
 * @returns {string}
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(text));
    return div.innerHTML;
}

/**
 * Cria uma bolha de mensagem AI com o accordion de Chain of Thought.
 * Retorna um objeto com referências aos elementos que serão atualizados via streaming:
 *   - bubbleEl: a div .message-bubble onde a resposta final é renderizada
 *   - cotAccordion: o <details> do accordion de pensamento
 *   - cotBody: o container onde os steps de status são adicionados
 *   - cotSpinner: o spinner do summary (removido quando o stream acaba)
 * @returns {{ bubbleEl: HTMLElement, cotAccordion: HTMLElement, cotBody: HTMLElement, cotSpinner: HTMLElement }}
 */
function createStreamingAIMessage() {
    if (!dom.chatEmpty.classList.contains('hidden')) {
        dom.chatEmpty.classList.add('hidden');
    }

    const messageEl = document.createElement('div');
    messageEl.className = 'message ai';
    messageEl.innerHTML = `
        <div class="message-avatar noto-emoji" aria-hidden="true">🤖</div>
        <div class="message-body">
            <div class="message-meta">
                <span>Auditor Cidadão</span>
                <span>${agora()}</span>
            </div>
            <div class="message-bubble">
                <details class="cot-accordion" open>
                    <summary>
                        <span class="cot-arrow">▶</span>
                        <span class="cot-icon noto-emoji">🧠</span>
                        <span>Pensando...</span>
                        <span class="cot-spinner"></span>
                    </summary>
                    <div class="cot-body"></div>
                </details>
                <div class="cot-response"></div>
            </div>
        </div>
    `;

    dom.chatMessages.appendChild(messageEl);
    dom.chatMessages.scrollTo({ top: dom.chatMessages.scrollHeight, behavior: 'smooth' });

    return {
        bubbleEl:     messageEl.querySelector('.cot-response'),
        cotAccordion: messageEl.querySelector('.cot-accordion'),
        cotBody:      messageEl.querySelector('.cot-body'),
        cotSpinner:   messageEl.querySelector('.cot-spinner'),
    };
}

/**
 * Adiciona um step de status ao accordion de Chain of Thought.
 * @param {HTMLElement} cotBody - Container dos steps
 * @param {string} statusText - Texto descritivo do status
 */
function addCotStep(cotBody, statusText) {
    // Marca o step anterior como concluído
    const prevStep = cotBody.querySelector('.cot-step:last-child:not(.done)');
    if (prevStep) prevStep.classList.add('done');

    const stepEl = document.createElement('div');
    stepEl.className = 'cot-step';
    stepEl.innerHTML = `
        <span class="cot-step-icon noto-emoji">⚙️</span>
        <span class="cot-step-text">${escapeHtml(statusText)}</span>
        <span class="cot-step-spinner"></span>
    `;
    cotBody.appendChild(stepEl);
}

/**
 * Finaliza o accordion de CoT: marca todos os steps como done,
 * troca o spinner do summary por um checkmark e recolhe o bloco.
 */
function finalizeCot(cotAccordion, cotBody, cotSpinner) {
    // Marca o último step como concluído
    const lastStep = cotBody.querySelector('.cot-step:last-child:not(.done)');
    if (lastStep) lastStep.classList.add('done');

    // Troca spinner por checkmark no summary
    if (cotSpinner) {
        const doneEl = document.createElement('span');
        doneEl.className = 'cot-done';
        doneEl.textContent = '✓ Concluído';
        cotSpinner.replaceWith(doneEl);
    }

    // Atualiza o texto do summary
    const summaryTextEl = cotAccordion.querySelector('summary > span:nth-child(3)');
    if (summaryTextEl) {
        const stepCount = cotBody.querySelectorAll('.cot-step').length;
        summaryTextEl.textContent = stepCount > 0
            ? `Raciocínio do agente (${stepCount} etapa${stepCount > 1 ? 's' : ''})`
            : 'Raciocínio do agente';
    }

    // Recolhe e diminui opacidade
    cotAccordion.removeAttribute('open');
    cotAccordion.classList.add('collapsed');
}

/**
 * Lê o conteúdo do textarea, envia ao agente e exibe a resposta via streaming SSE
 * com o accordion de Chain of Thought mostrando as etapas do agente em tempo real.
 */
async function sendMessage() {
    const texto = dom.chatInput.value.trim();
    if (!texto || state.isLoading || !state.isUploaded) return;

    // Limpa o input e ajusta altura
    dom.chatInput.value  = '';
    dom.chatInput.style.height = 'auto';

    // Exibe mensagem do usuário imediatamente
    addMessage('user', texto);
    state.turns++;

    setLoading(true);

    try {
        const response = await fetch(`${API_BASE}/conversar-com-auditor/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                pergunta:    texto,
                estado:      state.estado.toUpperCase(),
                municipio:   state.municipio,
                user_name:   state.userName || 'Usuário',
                lista_cnpjs: state.cnpjs,
                thread_id:   state.threadId,
            }),
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Erro HTTP ${response.status}`);
        }

        // --- Leitura do stream SSE com Chain of Thought ---
        const { bubbleEl, cotAccordion, cotBody, cotSpinner } = createStreamingAIMessage();
        const reader   = response.body.getReader();
        const decoder  = new TextDecoder('utf-8');
        let accumulated = '';
        let leftover    = '';
        let hasSteps    = false;

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
                            addCotStep(cotBody, event.content);
                            hasSteps = true;
                            dom.chatMessages.scrollTo({ top: dom.chatMessages.scrollHeight, behavior: 'smooth' });
                        }
                    } catch {
                        accumulated += payload;
                    }
                } else if (line === '' && i < lines.length - 1) {
                    continue;
                } else if (line !== '') {
                    if (i === lines.length - 1) {
                        leftover = line;
                    }
                }
            }

            // Renderiza o markdown acumulado na área de resposta
            if (accumulated) {
                bubbleEl.innerHTML = marked.parse(accumulated);
            }
            dom.chatMessages.scrollTo({ top: dom.chatMessages.scrollHeight, behavior: 'smooth' });
        }

        // --- Finalização ---
        if (!accumulated.trim()) {
            bubbleEl.innerHTML = marked.parse('*(resposta vazia)*');
        } else {
            bubbleEl.innerHTML = marked.parse(accumulated);
        }

        // Se não houve nenhum step de status, oculta o accordion inteiro
        if (!hasSteps) {
            cotAccordion.classList.add('hidden');
        } else {
            finalizeCot(cotAccordion, cotBody, cotSpinner);
        }

        syncDebug();

    } catch (error) {
        addMessage('ai', `❌ **Erro ao consultar o agente:** ${error.message}`);
        showToast(`Erro: ${error.message}`, 'error');
    } finally {
        setLoading(false);
    }
}


/* =============================================================================
   7. NOVA SESSÃO
   ============================================================================= */

/**
 * Gera um novo Thread ID, limpa o chat e reseta o contador de turnos.
 * Mantém o edital já indexado e os CNPJs — apenas o histórico de conversa é reiniciado.
 */
function novaSessao() {
    state.threadId = generateUUID();
    state.turns    = 0;

    // Limpa mensagens do chat
    dom.chatMessages.innerHTML = '';
    dom.chatMessages.appendChild(dom.chatEmpty);
    dom.chatEmpty.classList.remove('hidden');

    syncSessionDisplay();
    showToast('Nova sessão iniciada. Histórico da conversa reiniciado.', 'info');
}


/* =============================================================================
   8. EVENT LISTENERS
   ============================================================================= */

// --- Inputs de configuração ---
dom.inputUsername.addEventListener('input', (e) => {
    state.userName = e.target.value.trim();
});

dom.inputEstado.addEventListener('input', (e) => {
    e.target.value = e.target.value.toUpperCase();
    state.estado   = e.target.value.trim();
});

dom.inputMunicipio.addEventListener('input', (e) => {
    state.municipio = e.target.value.trim();
});

// --- Upload: clique na zona ---
dom.uploadZone.addEventListener('click', () => dom.fileInput.click());
dom.uploadZone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        dom.fileInput.click();
    }
});

// --- Upload: seleção via input file ---
dom.fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) setFile(file);
});

// --- Upload: drag and drop ---
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
    if (file && file.type === 'application/pdf') {
        setFile(file);
    } else {
        showToast('Apenas arquivos PDF são aceitos.', 'error');
    }
});

// --- Remover arquivo ---
dom.btnRemoveFile.addEventListener('click', removeFile);

// --- Indexar edital ---
dom.btnUpload.addEventListener('click', uploadEdital);

// --- Enviar mensagem: botão ---
dom.btnSend.addEventListener('click', sendMessage);

// --- Enviar mensagem: Enter (sem Shift) ---
dom.chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// --- Auto-resize do textarea ---
dom.chatInput.addEventListener('input', () => {
    dom.chatInput.style.height = 'auto';
    dom.chatInput.style.height = Math.min(dom.chatInput.scrollHeight, 200) + 'px';
});

// --- Nova sessão ---
dom.btnNovaSessao.addEventListener('click', novaSessao);

// --- Fechar toast ao clicar ---
dom.toast.addEventListener('click', () => dom.toast.classList.add('hidden'));


/* =============================================================================
   9. INICIALIZAÇÃO
   ============================================================================= */

/**
 * Configuração inicial da aplicação ao carregar a página.
 */
function init() {
    // Configura o marked.js
    marked.setOptions({ breaks: true, gfm: true });

    // Exibe o Thread ID inicial
    syncSessionDisplay();

    // Foca no primeiro campo de configuração
    dom.inputUsername.focus();

    console.info('[Auditor Cidadão] Frontend iniciado. Thread ID:', state.threadId);
}

init();
