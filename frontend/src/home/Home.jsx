import { useEffect } from 'react';
import { runHeroAnimation } from './heroAnimation.js';

/**
 * Landing page — markup idêntico ao antigo index.html estático. O conteúdo
 * do mockup do hero nasce no ESTADO FINAL (laudo pronto): é o que usuários
 * sem JS ou com prefers-reduced-motion veem direto. runHeroAnimation()
 * captura esses textos, zera a janela e reencena a chegada via streaming.
 */
export default function Home() {
    useEffect(() => {
        runHeroAnimation();
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
                    <span className="brand-badge">v1.0.0</span>
                </a>
                <nav className="nav-links">
                    <a href="#como-funciona" className="nav-link">Como funciona</a>
                    <a href="#anomalias" className="nav-link">O que detecta</a>
                    <a href="/chat.html" className="btn btn-primary btn-sm"><span>Abrir o chat</span><span className="material-symbols-outlined" aria-hidden="true">arrow_forward</span></a>
                </nav>
            </header>

            {/* ===========================
                 HERO
                 =========================== */}
            <section className="hero">
                <div className="hero-copy">
                    <div className="eyebrow">Agente de auditoria com IA</div>
                    <h1 className="hero-title">Fiscalize gastos públicos como um verdadeiro auditor.</h1>
                    <p className="hero-subtitle">
                        O Auditor Cidadão recebe editais de licitação em PDF, indexa o conteúdo e coloca um
                        agente de IA para detectar irregularidades — de sobrepreço a empresas sancionadas —
                        com raciocínio auditável em tempo real.
                    </p>
                    <div className="hero-actions">
                        <a href="/chat.html" className="btn btn-primary"><span>Começar auditoria</span><span className="material-symbols-outlined" aria-hidden="true">arrow_forward</span></a>
                        <a href="#como-funciona" className="btn btn-outline">Como funciona</a>
                    </div>
                </div>

                {/* O conteúdo abaixo está escrito no ESTADO FINAL (laudo pronto) — ver
                     comentário no topo do arquivo e em heroAnimation.js. */}
                <div className="hero-mockup">
                    <div className="code-window">
                        <div className="code-window-bar">
                            <span className="code-window-dot"></span>
                            <span className="code-window-dot"></span>
                            <span className="code-window-dot"></span>
                            <span className="code-window-name">laudo_auditoria.md</span>
                        </div>
                        <div className="code-window-body">
                            <div className="code-window-muted" id="hero-heading"># Resumo Executivo</div>
                            <div className="code-window-score" id="hero-score-line">Score de risco: <strong id="hero-score">0.87</strong><span id="hero-class-wrap"> — <strong>CRÍTICO</strong></span></div>
                            <div className="code-window-row" id="hero-row">
                                <span className="risk-pill">CRÍTICA</span>
                                <span>Sanção Vigente</span>
                            </div>
                            <div className="code-window-evidence" id="hero-evidence-line">
                                <span className="material-symbols-outlined" aria-hidden="true">subdirectory_arrow_right</span> <span className="evidence-text" id="hero-evidence">{'Empresa XYZ LTDA consta no CEIS\n   (Lei 14.133/2021, art. 14)'}</span>
                            </div>
                            <div className="code-window-status is-done" id="hero-status">
                                <span className="status-dot" id="hero-status-dot"></span>
                                <span id="hero-status-text">Laudo pronto</span>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <div className="green-divider"></div>

            {/* ===========================
                 COMO FUNCIONA
                 =========================== */}
            <section id="como-funciona" className="section">
                <div className="eyebrow">Como funciona</div>
                <h2 className="section-title">Três passos entre o edital e o laudo.</h2>

                <div className="feature-grid">
                    <div className="feature-card">
                        <div className="feature-step">01</div>
                        <h3 className="feature-title">Informe o contexto</h3>
                        <p className="feature-desc">Selecione o estado, o município e envie o edital de licitação em PDF. Em segundos o documento é indexado.</p>
                    </div>
                    <div className="feature-card">
                        <div className="feature-step">02</div>
                        <h3 className="feature-title">O agente investiga</h3>
                        <p className="feature-desc">A IA cruza dados de fontes oficiais — Receita Federal e PNCP — em busca de 9 categorias de anomalias.</p>
                    </div>
                    <div className="feature-card">
                        <div className="feature-step">03</div>
                        <h3 className="feature-title">Receba o laudo</h3>
                        <p className="feature-desc">Converse com o agente e receba um laudo estruturado, com evidências, fontes e um score de risco consolidado.</p>
                    </div>
                </div>

                <div className="section-cta">
                    <a href="/chat.html" className="btn btn-primary"><span>Abrir o chat com o auditor</span><span className="material-symbols-outlined" aria-hidden="true">arrow_forward</span></a>
                </div>
            </section>

            {/* ===========================
                 CATÁLOGO DE ANOMALIAS
                 =========================== */}
            <section id="anomalias" className="section section-anomalias">
                <div className="eyebrow">Catálogo de anomalias</div>
                <h2 className="section-title">Nove categorias de irregularidade, verificadas uma a uma.</h2>
                <p className="section-lead">
                    A cada auditoria, o agente varre este catálogo de ponta a ponta — cruzando o que o
                    edital declara com o que as fontes oficiais registram.
                </p>

                <div className="anomalia-stack">
                    {ANOMALIA_PARES.map((par, i) => (
                        <div key={i} className={`anomalia-par${par.solo ? ' anomalia-par-solo' : ''}`} style={{ '--stack-i': i }}>
                            {par.itens.map((item) => (
                                <article key={item.letra} className="anomalia-cat">
                                    <div className="anomalia-cat-head">
                                        <span className="anomalia-letra">{item.letra}</span>
                                        <h3 className="anomalia-titulo">{item.titulo}</h3>
                                        <span className="anomalia-indice">{item.indice}</span>
                                    </div>
                                    <p className="anomalia-criterio">{item.criterio}</p>
                                    <div className="anomalia-meta">
                                        {item.risco && <span className="risk-badge risk-critico">{item.risco}</span>}
                                        {item.chips.map((chip) => (
                                            <span key={chip} className="anomalia-chip">{chip}</span>
                                        ))}
                                    </div>
                                </article>
                            ))}
                        </div>
                    ))}
                </div>
            </section>

            {/* ===========================
                 RODAPÉ
                 =========================== */}
            <footer className="footer">
                <div className="footer-inner">
                    <div className="footer-brand">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#00d992" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                            <circle cx="10.5" cy="10.5" r="6.5"></circle>
                            <line x1="15.5" y1="15.5" x2="21" y2="21"></line>
                        </svg>
                        <span>Auditor Cidadão</span>
                    </div>
                    <a className="footer-link" href="https://moreira-89.github.io/auditor-cidadao/" target="_blank" rel="noopener">Acesse a documentação do projeto</a>
                    <span className="footer-note">IA para fiscalização de gastos públicos · Apache 2.0</span>
                </div>
            </footer>
        </>
    );
}

/** Catálogo de anomalias, agrupado em pares para o empilhamento sticky (ver
 * .anomalia-stack em styles.css — cada dupla fixa por cima da anterior
 * conforme o scroll avança, via --stack-i). A letra I fica sozinha. */
const ANOMALIA_PARES = [
    {
        itens: [
            {
                letra: 'A', titulo: 'Sobrepreço', indice: '01 / 09',
                criterio: 'O item está sendo comprado por um preço bem acima do praticado no mercado. O agente compara o valor unitário com a mediana paga pelo mesmo item nos últimos 12 meses — mais de 30% acima acende o alerta.',
                chips: ['> +30% sobre a mediana', 'Catálogo de preços de referência'],
            },
            {
                letra: 'B', titulo: 'Direcionamento', indice: '02 / 09',
                criterio: 'O edital parece escrito sob medida para uma empresa específica: marca única, modelo exato, dimensões fora de padrão. Exigências assim eliminam a concorrência antes mesmo de a disputa começar.',
                chips: ['"marca X ou similar superior"', 'Texto do edital'],
            },
        ],
    },
    {
        itens: [
            {
                letra: 'C', titulo: 'Fracionamento irregular', indice: '03 / 09',
                criterio: 'Uma compra grande é fatiada em várias contratações pequenas para escapar das regras mais rígidas de licitação. O agente procura no histórico do órgão compras parecidas feitas em datas próximas.',
                chips: ['Lei 14.133, art. 75', 'Histórico no PNCP'],
            },
            {
                letra: 'D', titulo: 'Cartel e conluio', indice: '04 / 09',
                criterio: 'Empresas que parecem concorrentes, mas jogam no mesmo time — sócios em comum, mesmo endereço, vitórias que se revezam. O agente cruza o quadro societário e os endereços das participantes.',
                chips: ['Quadro societário', 'Receita Federal'],
            },
        ],
    },
    {
        itens: [
            {
                letra: 'E', titulo: 'Empresa recém-criada', indice: '05 / 09',
                criterio: 'Uma empresa aberta há poucos meses vencendo contrato de alto valor. Fica ainda mais suspeito quando o objeto exige experiência técnica que ela não teve tempo de construir.',
                chips: ['< 12 meses de CNPJ', 'Receita Federal'],
            },
            {
                letra: 'F', titulo: 'Prazo insuficiente', indice: '06 / 09',
                criterio: 'O edital dá menos tempo que o mínimo legal entre a publicação e a abertura das propostas. Na prática, só participa quem já sabia da licitação antes de ela ser publicada.',
                chips: ['Lei 14.133, art. 55', 'Datas do próprio edital'],
            },
        ],
    },
    {
        itens: [
            {
                letra: 'G', titulo: 'Reincidência suspeita', indice: '07 / 09',
                criterio: 'A mesma empresa vence quase tudo em um único órgão: mais da metade das licitações em 12 meses. Pode ser eficiência — ou proximidade demais com quem contrata.',
                chips: ['> 50% das vitórias', 'PNCP'],
            },
            {
                letra: 'H', titulo: 'Sanção vigente', indice: '08 / 09',
                criterio: 'A empresa vencedora está proibida por lei de contratar com o poder público — consta no CEIS, no CNEP ou na lista de inidôneos do TCU. É o achado mais grave do catálogo: risco crítico imediato.',
                risco: 'Risco crítico',
                chips: ['Lei 14.133, art. 14', 'CEIS · CNEP'],
            },
        ],
    },
    {
        solo: true,
        itens: [
            {
                letra: 'I', titulo: 'Incompatibilidade de atividade', indice: '09 / 09',
                criterio: 'A atividade registrada da empresa não tem relação com o que ela venceu para entregar — como um restaurante ganhando uma licitação de obra civil.',
                chips: ['CNAE × objeto', 'Receita Federal'],
            },
        ],
    },
];
