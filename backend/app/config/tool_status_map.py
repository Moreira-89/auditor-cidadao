# Mapeia o nome técnico de cada tool para uma mensagem legível exibida ao usuário durante a execução
TOOL_STATUS_MAP = {
    # Ferramentas Nativas
    "consultar_receita_federal": "🏛️ Consultando dados cadastrais na Receita Federal...",
    "buscar_contexto_edital": "🖹 Analisando trechos do edital indexado...",
    "buscar_informacao_web": "🌐 Pesquisando informações complementares na web...",
    "consultar_sancoes_empresa": "⚖️ Verificando sanções da empresa nos cadastros CEIS e CNEP...",
    # Licitações (Prefixo: Buscando/Obtendo/Listando)
    "search_licitacoes": "⌕ Buscando licitações no Portal Nacional de Contratações Públicas...",
    "get_licitacao": "📋 Obtendo detalhes da licitação no PNCP...",
    "list_licitacao_itens": "🔲 Listando itens e lotes da licitação...",
    "list_licitacao_resultados": "🗲 Verificando vencedores e preços praticados...",
    "list_licitacao_arquivos": "🗎 Listando arquivos anexos da licitação...",
    # Contratos (Prefixo: Buscando/Obtendo/Listando)
    "search_contratos": "⌕ Buscando contratos no Portal Nacional de Contratações Públicas...",
    "get_contrato": "📄 Obtendo detalhes do contrato selecionado...",
    "list_contrato_termos": "🗏 Listando termos aditivos e apostilamentos do contrato...",
    # Atas e Análises Temporais
    "search_atas_rp": "📑 Buscando Atas de Registro de Preço vigentes...",
    "compare_periodos": "⛬ Comparando períodos para identificar padrões temporais...",
    "aggregate_licitacoes_por_periodo": "📊 Agrupando volume de licitações por período...",
}