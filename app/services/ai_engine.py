import uuid

from app.services.build_graph import graph
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.prompt import SYSTEM_PROMPT, PROMPT_DINAMICO


# -----------------------------------------------------------------------------
# MOTOR DE INTELIGÊNCIA ARTIFICIAL (AGENTE)
# -----------------------------------------------------------------------------
def run_agent(
    pergunta_usuario: str,
    lista_cnpj: list,
    contexto: str,
    user_name: str,
    estado: str,
    municipio: str,
    thread_id: str | None = None,
) -> str:
    """
    Resumo Principal: Executa o agente de auditoria, processando a pergunta do usuário,
    gerenciando o histórico conversacional através de threads e retornando a resposta da LLM.

    COMO FUNCIONA:
    1. Resolução da Thread: Garante que exista um thread_id válido (gera UUID se não fornecido).
    2. Resolução do Histórico do Checkpointer: Consulta o grafo SINGLETON para verificar se a
       thread informada já possui histórico de mensagens salvo no InMemorySaver compartilhado.
    3. Construção do Payload de Entrada:
       - Caso seja o primeiro turno: injeta o SystemMessage (instruções e regras de segurança)
         e o HumanMessage enriquecido com o contexto RAG e os CNPJs extraídos.
       - Caso seja um turno subsequente: envia apenas a nova pergunta do usuário. O checkpointer
         restaura automaticamente o histórico pregresso da thread.
    4. Execução do Grafo com Configuração: Invoca o grafo singleton com o payload e o thread_id.
       As chaves `estado` e `municipio` são sempre incluídas no payload para que o LangGraph
       consiga injetá-las automaticamente na ferramenta `buscar_contexto_edital` via `InjectedState`.
    5. Retorno do Resultado: Extrai e retorna o texto da última mensagem gerada pelo agente.

    Args:
        pergunta_usuario (str): Dúvida ou requisição enviada pelo usuário sobre o edital.
        lista_cnpj (list): Lista de CNPJs pré-extraídos do edital pelo endpoint de upload.
        contexto (str): Trechos mais relevantes do edital (RAG) recuperados do Pinecone.
        user_name (str): Nome do usuário logado, usado para personalização do prompt.
        estado (str): Sigla do estado do edital (ex: 'SP'). Propagada ao estado do grafo
                      para ser injetada automaticamente na ferramenta de busca no edital.
        municipio (str): Nome do município do edital (ex: 'São Paulo'). Idem ao estado.
        thread_id (str | None): Identificador único da sessão de chat. Se None, um UUID
                                 é gerado automaticamente para criar uma nova conversa.

    Returns:
        str: A resposta final da LLM consolidada e pronta para ser exibida ao usuário.
    """
    # --- 1. Resolução da Thread ---
    # Garantimos que exista um thread_id válido. O UUID garante unicidade global por sessão.
    if not thread_id:
        thread_id = str(uuid.uuid4())

    config = {"configurable": {"thread_id": thread_id}}

    # --- 2. Resolução do Histórico do Checkpointer ---
    # Consultamos o estado do grafo SINGLETON (compartilhado entre todos os requests HTTP).
    # Ao contrário de recriar o grafo por request, aqui o InMemorySaver é o MESMO objeto
    # em memória, portanto o histórico de mensagens de cada thread persiste entre chamadas.
    state = graph.get_state(config)
    conversa_iniciada = len(state.values.get("messages", [])) > 0

    # --- 3. Construção do Payload de Entrada ---
    if conversa_iniciada:
        # Turnos subsequentes: apenas a nova pergunta é enviada para evitar redundância.
        # O checkpointer restaura o histórico pregresso automaticamente.
        mensagens_entrada = [HumanMessage(content=pergunta_usuario)]
    else:
        # Primeiro turno: injetamos o contexto enriquecido e as regras de segurança.
        # O SYSTEM_PROMPT contém as instruções permanentes do agente (papel, regras, escopo).
        # O PROMPT_DINAMICO injeta o conteúdo específico desta sessão (edital, CNPJs, pergunta).
        cnpjs_formatados = (
            ", ".join(lista_cnpj) if lista_cnpj else "Nenhum CNPJ encontrado no documento."
        )
        system_message = SystemMessage(content=SYSTEM_PROMPT.format(user_name=user_name))
        human_message = HumanMessage(
            content=PROMPT_DINAMICO.format(
                pergunta_usuario=pergunta_usuario,
                contexto=contexto,
                cnpjs_formatados=cnpjs_formatados,
                user_name=user_name
            )
        )
        mensagens_entrada = [system_message, human_message]

    # --- 4. Execução do Grafo com Configuração ---
    # O LangGraph usa o 'thread_id' no config para recuperar e salvar o estado no checkpointer.
    # Após cada invocação, o estado atualizado (com a nova mensagem) é persisitido automaticamente.
    # As chaves `estado` e `municipio` são incluídas em TODOS os turnos (mesmo os subsequentes).
    # O InMemorySaver NÃO persiste chaves arbitrárias do estado entre invocações — apenas `messages`
    # recebe tratamento especial via `add_messages`. Portanto, é necessário repassar `estado` e
    # `municipio` a cada chamada para que o InjectedState da ferramenta consiga lê-los do estado ativo.
    result = graph.invoke(
        {"messages": mensagens_entrada, "estado": estado, "municipio": municipio},
        config=config,
    )

    # --- 5. Retorno do Resultado ---
    # A última mensagem da lista é sempre a resposta final do agente após convergir.
    return str(result["messages"][-1].content)


# -----------------------------------------------------------------------------
# MODO DE EXECUÇÃO INTERATIVA (CLI / TERMINAL DE TESTES)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Este bloco só executa se o arquivo for chamado diretamente: `python app/services/ai_engine.py`.
    # Garante que o servidor FastAPI (uvicorn) nunca entre neste bloco de testes ao importar o módulo.
    #
    # Os imports do 'rich' ficam aqui propositalmente — a biblioteca é uma dependência de CLI/terminal.
    # Importá-la no topo do módulo a carregaria em produção (quando o FastAPI sobe), aumentando
    # desnecessariamente o footprint de memória e tornando 'rich' obrigatória no ambiente de produção.
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.prompt import Prompt

    console = Console()
    console.print("\n[bold yellow]=== MODO INTERATIVO (CLI) - AUDITOR CIDADÃO ===[/bold yellow]")
    console.print("Digite [bold red]'q'[/bold red] ou [bold red]'quit'[/bold red] para encerrar a sessão.\n")

    # --- 1. Dados de Contexto para Testes ---
    # Dados fictícios que simulam o output do pipeline de upload + RAG.
    # Em produção, esses dados vêm do Pinecone via busca semântica.
    teste_user = "Lucas"
    teste_contexto = "Este é um edital de licitação simulado para testes no console local."
    teste_cnpjs = ["46.523.056/0001-21"]
    teste_estado = "SP"
    teste_municipio = "São Paulo"

    # ID de thread fixo para que o histórico persista ao longo de toda a sessão de terminal.
    cli_thread_id = "cli-local-test-session"

    prompt_cli = Prompt()
    Prompt.prompt_suffix = ""

    while True:
        try:
            # --- 2. Escuta de Entrada do Usuário ---
            user_input = prompt_cli.ask("[bold cyan]Você: \n")
            console.print(Markdown("\n\n  ---  \n\n"))

            if user_input.strip().lower() in ["q", "quit", "exit"]:
                console.print("[bold green]Sessão interativa encerrada.[/bold green]")
                break

            # --- 3. Execução do Agente via run_agent ---
            # Reutilizamos a MESMA função usada pela API HTTP, garantindo paridade de comportamento
            # entre o ambiente de teste (CLI) e o ambiente de produção (FastAPI).
            # O thread_id fixo preserva o histórico ao longo de toda a sessão de terminal,
            # pois o grafo singleton (importado no topo do módulo) mantém o InMemorySaver ativo.
            resposta = run_agent(
                pergunta_usuario=user_input,
                lista_cnpj=teste_cnpjs,
                contexto=teste_contexto,
                user_name=teste_user,
                estado=teste_estado,
                municipio=teste_municipio,
                thread_id=cli_thread_id,
            )

            # --- 4. Exibição da Resposta Formatada ---
            console.print("[bold cyan]Auditor Cidadão: \n")
            console.print(Markdown(resposta))
            console.print(Markdown("\n\n  ---  \n\n"))

        except KeyboardInterrupt:
            console.print("\n[bold green]Sessão interrompida pelo teclado.[/bold green]")
            break