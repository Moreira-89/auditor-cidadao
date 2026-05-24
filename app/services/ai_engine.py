import uuid
from app.services.build_graph import build_graph
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.prompt import SYSTEM_PROMPT, PROMPT_DINAMICO
from rich.markdown import Markdown
from rich.prompt import Prompt

# -----------------------------------------------------------------------------
# MOTOR DE INTELIGÊNCIA ARTIFICIAL (AGENTE)
# -----------------------------------------------------------------------------
def run_agent(pergunta_usuário: str, lista_cnpj: list, contexto: str, user_name: str, thread_id: str | None = None) -> str:
    """
    Resumo Principal: Executa o agente de auditoria de forma isolada, processando a pergunta 
    do usuário, gerenciando o histórico conversacional através de threads e retornando a resposta da LLM.

    COMO FUNCIONA:
    1. Inicialização do Grafo e Thread: Carrega o StateGraph compilado e resolve o thread_id (se nulo, gera um UUID).
    2. Resolução do Histórico do Checkpointer: Verifica se a thread informada já possui histórico de mensagens na memória.
    3. Construção do Payload de Entrada:
       - Caso seja o primeiro turno: injeta o SystemMessage (instruções e regras) e o HumanMessage enriquecido (contexto RAG + CNPJs).
       - Caso seja um turno subsequente: envia apenas a nova pergunta simples do usuário, deixando o checkpointer resgatar o contexto pregresso.
    4. Execução do Grafo com Configuração: Invoca o grafo repassando a thread correspondente nas opções configuráveis.
    5. Retorno do Resultado: Retorna o texto da última mensagem gerada pelo agente após convergir.

    Args:
        pergunta_usuário (str): Dúvida ou requisição enviada pelo usuário sobre o edital.
        lista_cnpj (list): Lista de CNPJs pré-extraídos do edital.
        contexto (str): Trechos mais relevantes do edital (RAG) recuperados do Pinecone.
        user_name (str): Nome do usuário logado para personalização.
        thread_id (str | None): Identificador único da sessão do chat na web.

    Returns:
        str: A resposta final da LLM consolidada e analisada.
    """
    # --- 1. Inicialização do Grafo e Thread ---
    # Instanciamos o grafo compilado e garantimos que tenhamos um thread_id válido para persistência.
    graph = build_graph()
    if not thread_id:
        thread_id = str(uuid.uuid4())

    config = {"configurable": {"thread_id": thread_id}}

    # --- 2. Resolução do Histórico do Checkpointer ---
    # Buscamos o estado atual gravado para essa thread. Se já existirem mensagens arquivadas,
    # significa que o edital e as regras do sistema já foram configurados no primeiro turno.
    state = graph.get_state(config)
    conversa_iniciada = len(state.values.get("messages", [])) > 0

    # --- 3. Construção do Payload de Entrada ---
    if conversa_iniciada:
        # Turnos subsequentes: passamos apenas a nova pergunta para evitar redundância de contexto
        mensagens_entrada = [HumanMessage(content=pergunta_usuário)]
    else:
        # Primeiro turno: precisamos inicializar o contexto enriquecido e as regras de segurança
        cnpjs_formatados = (
            ", ".join(lista_cnpj) if lista_cnpj else "Nenhum CNPJ encontrado no documento."
        )
        system_message = SystemMessage(content=SYSTEM_PROMPT.format(user_name=user_name))
        human_message = HumanMessage(
            content=PROMPT_DINAMICO.format(
                pergunta_usuário=pergunta_usuário,
                contexto=contexto,
                cnpjs_formatados=cnpjs_formatados,
                user_name=user_name
            )
        )
        mensagens_entrada = [system_message, human_message]

    # --- 4. Execução do Grafo com Configuração ---
    # Executamos o processamento passando o payload de entrada e o dicionário de configurações da thread.
    result = graph.invoke({"messages": mensagens_entrada}, config=config)

    # --- 5. Retorno do Resultado ---
    # Retornamos o texto gerado na última interação. O LangGraph mantém as mensagens salvas no InMemorySaver.
    return str(result["messages"][-1].content)


# -----------------------------------------------------------------------------
# MODO DE EXECUÇÃO INTERATIVA (CLI / TERMINAL DE TESTES)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # --- 1. Inicialização do Terminal de Testes ---
    # Este bloco só executa se o arquivo for chamado diretamente no terminal via `python app/services/ai_engine.py`.
    # Evita travar a API HTTP do FastAPI na escuta de comandos no stdin do console.
    from rich.console import Console
    
    console = Console()
    console.print("\n[bold yellow]=== MODO INTERATIVO (CLI) - AUDITOR CIDADÃO ===[/bold yellow]")
    console.print("Digite [bold red]'q'[/bold red] ou [bold red]'quit'[/bold red] para encerrar a sessão.\n")
    
    # Compilamos o grafo e definimos dados fictícios de teste para o console
    graph = build_graph()
    all_messages = []
    
    teste_user = "Lucas"
    teste_contexto = "Este é um edital de licitação simulado para testes no console local."
    teste_cnpjs = ["46.523.056/0001-21"]
    
    prompt = Prompt()
    Prompt.prompt_suffix = ""
    
    system_msg = SystemMessage(content=SYSTEM_PROMPT.format(user_name=teste_user))
    
    # Definimos um ID de thread fixo para o ambiente de testes em terminal para que
    # o checkpointer do LangGraph consiga salvar as sessões locais corretamente.
    cli_config = {"configurable": {"thread_id": "cli-local-test-session"}}
    
    while True:
        try:
            # --- 2. Escuta de Entrada do Usuário ---
            user_input = prompt.ask("[bold cyan]Você: \n")
            console.print(Markdown("\n\n  ---  \n\n"))
            
            if user_input.strip().lower() in ["q", "quit", "exit"]:
                console.print("[bold green]Sessão interativa encerrada.[/bold green]")
                break
            
            # --- 3. Formatação do Prompt Dinâmico de Turno ---
            cnpjs_formatados = ", ".join(teste_cnpjs)
            human_msg = HumanMessage(
                content=PROMPT_DINAMICO.format(
                    pergunta_usuário=user_input,
                    contexto=teste_contexto,
                    cnpjs_formatados=cnpjs_formatados,
                    user_name=teste_user
                )
            )
            
            # Montamos o histórico do diálogo. Se for o primeiro turno, adicionamos a instrução do sistema.
            if not all_messages:
                current_messages = [system_msg, human_msg]
            else:
                current_messages = all_messages + [human_msg]
            
            # --- 4. Execução do Agente ---
            # Passamos cli_config contendo a thread da sessão para evitar ValueError do checkpointer
            result = graph.invoke({"messages": current_messages}, config=cli_config)
            
            # --- 5. Exibição da Resposta Formatada ---
            console.print("[bold cyan]Auditor Cidadão: \n")
            console.print(Markdown(str(result["messages"][-1].content)))
            console.print(Markdown("\n\n  ---  \n\n"))
            
            # Salvamos o histórico completo retornado para o próximo turno da conversa
            all_messages = result["messages"]
            
        except KeyboardInterrupt:
            console.print("\n[bold green]Sessão interrompida pelo teclado.[/bold green]")
            break