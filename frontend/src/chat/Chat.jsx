import { useEffect } from 'react';
import { initChat } from './chatLogic.js';

/**
 * Shell estático com os mesmos ids do antigo chat.html — initChat() (imperativo,
 * ver chatLogic.js) assume o resto depois do mount. Este componente não guarda
 * estado próprio nem re-renderiza: se re-renderizasse, o React tentaria
 * reconciliar essa árvore contra as mutações diretas que initChat() faz no DOM
 * (innerHTML, appendChild, etc.), o que quebraria a lógica de streaming/upload.
 */
export default function Chat() {
    useEffect(() => {
        initChat();
    }, []);

    return (
        <>
            {/* ===========================
                 NAVEGAÇÃO
                 =========================== */}
            <header className="nav">
                <a href="/" className="brand">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#00d992" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                        <circle cx="10.5" cy="10.5" r="6.5"></circle>
                        <line x1="15.5" y1="15.5" x2="21" y2="21"></line>
                    </svg>
                    <span className="brand-name">Auditor Cidadão</span>
                </a>
                <div className="nav-chat-right">
                    <span className="location-pill hidden" id="location-pill">
                        <span className="location-dot"></span>
                        <span id="location-label"></span>
                    </span>
                    <button className="btn btn-outline btn-sm" id="btn-reset"><span className="material-symbols-outlined" aria-hidden="true">refresh</span><span>Reiniciar sessão</span></button>
                    <a href="/" className="nav-link">Início</a>
                </div>
            </header>

            {/* ===========================
                 CHAT
                 =========================== */}
            <main className="chat-shell">

                <h1 className="sr-only">Conversa com o auditor</h1>

                <div className="chat-scroll" id="chat-scroll" role="log" aria-live="polite" aria-label="Histórico da conversa">

                    <div className="chat-empty" id="chat-empty">
                        <div className="chat-empty-icon">
                            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#00d992" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                                <circle cx="10.5" cy="10.5" r="6.5"></circle>
                                <line x1="15.5" y1="15.5" x2="21" y2="21"></line>
                            </svg>
                        </div>
                        <p className="chat-empty-title">Edital indexado. Pode começar.</p>
                        <p className="chat-empty-sub">Escolha uma sugestão ou digite sua própria pergunta.</p>
                        <div className="suggestion-chips" id="suggestion-chips">
                            <button className="suggestion-chip" data-prompt="Existe alguma irregularidade nas empresas participantes desta licitação?">Existe irregularidade nas empresas participantes?</button>
                            <button className="suggestion-chip" data-prompt="Alguma empresa participante possui sanção vigente no CEIS ou CNEP?">Alguma empresa tem sanção vigente?</button>
                            <button className="suggestion-chip" data-prompt="Faça um resumo dos principais riscos deste edital.">Resuma os principais riscos deste edital</button>
                        </div>
                    </div>

                    <div id="chat-messages"></div>

                </div>

                <button className="jump-bottom hidden" id="btn-jump-bottom" aria-label="Ir para o final da conversa">
                    <span className="material-symbols-outlined" aria-hidden="true">arrow_downward</span><span>Novo conteúdo</span>
                </button>

                <div className="chat-input-wrap">
                    <div className="chat-input-box">
                        <textarea
                            className="chat-input"
                            id="chat-input"
                            rows="1"
                            placeholder="Faça uma pergunta sobre o edital…"
                            disabled
                            aria-label="Campo de pergunta ao agente"
                        ></textarea>
                        <button className="send-btn" id="btn-send" disabled aria-label="Enviar pergunta">
                            <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18" aria-hidden="true">
                                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path>
                            </svg>
                        </button>
                    </div>
                    <p className="input-hint">
                        Pressione <kbd>Enter</kbd> para enviar &middot; <kbd>Shift+Enter</kbd> para nova linha
                    </p>
                </div>

            </main>

            {/* ===========================
                 MODAL — NOVA SESSÃO / UPLOAD
                 =========================== */}
            <div className="modal-overlay" id="modal-overlay">
                <div className="modal-card">

                    <div className="modal-eyebrow">
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00d992" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                            <circle cx="10.5" cy="10.5" r="6.5"></circle>
                            <line x1="15.5" y1="15.5" x2="21" y2="21"></line>
                        </svg>
                        Nova sessão
                    </div>
                    <h2 className="modal-title">Informe o edital</h2>
                    <p className="modal-desc">Selecione o local e envie o edital de licitação em PDF para iniciar a auditoria.</p>

                    <div className="modal-row">
                        <div className="field" id="combobox-estado">
                            <label className="field-label" htmlFor="input-estado">Estado</label>
                            <input className="input" type="text" id="input-estado"
                                   placeholder="Digite ou selecione" autoComplete="off"
                                   role="combobox" aria-autocomplete="list" aria-expanded="false"
                                   aria-controls="estado-listbox" aria-haspopup="listbox" />
                            <ul className="combobox-list hidden" id="estado-listbox"
                                role="listbox" aria-label="Lista de estados"></ul>
                        </div>
                        <div className="field field-grow" id="combobox-municipio">
                            <label className="field-label" htmlFor="input-municipio">Município</label>
                            <input className="input" type="text" id="input-municipio"
                                   placeholder="Selecione um estado primeiro" autoComplete="off" disabled
                                   role="combobox" aria-autocomplete="list" aria-expanded="false"
                                   aria-controls="municipio-listbox" aria-haspopup="listbox" />
                            <ul className="combobox-list hidden" id="municipio-listbox"
                                role="listbox" aria-label="Lista de municípios"></ul>
                        </div>
                    </div>

                    <div className="upload-field">
                        <label className="field-label">Edital (PDF)</label>
                        <input type="file" id="file-input" accept=".pdf" hidden aria-hidden="true" />

                        <div className="upload-zone" id="upload-zone" role="button" tabIndex="0"
                             aria-label="Área de upload — arraste um PDF ou clique para selecionar">
                            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#8b949e" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                                <path d="M17 8l-5-5-5 5"></path>
                                <path d="M12 3v12"></path>
                            </svg>
                            <span className="upload-zone-title">Clique para selecionar o PDF</span>
                            <span className="upload-zone-sub">ou arraste o arquivo aqui</span>
                        </div>

                        <div className="file-info hidden" id="file-info">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00d992" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                                <path d="M14 2v6h6"></path>
                            </svg>
                            <span className="file-info-name" id="file-name-display"></span>
                            <button className="file-info-remove material-symbols-outlined" id="btn-remove-file" aria-label="Remover arquivo selecionado">close</button>
                        </div>
                    </div>

                    <div className="modal-msg error hidden" id="modal-error" role="alert"></div>
                    <div className="modal-msg loading hidden" id="modal-loading" role="status">
                        <span className="spinner"></span>
                        <span id="modal-loading-text">Indexando o edital…</span>
                    </div>

                    <button className="btn btn-primary btn-block" id="btn-confirm" disabled><span>Confirmar e iniciar</span><span className="material-symbols-outlined" aria-hidden="true">arrow_forward</span></button>

                </div>
            </div>

            {/* Toast de notificação */}
            <div className="toast hidden" id="toast" role="alert" aria-live="assertive" aria-atomic="true"></div>
        </>
    );
}
