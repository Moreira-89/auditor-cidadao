import uuid

from app.services.build_graph import graph
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.prompt import SYSTEM_PROMPT, PROMPT_DINAMICO


# -----------------------------------------------------------------------------
# MOTOR DE INTELIGÊNCIA ARTIFICIAL (AGENTE)
# -----------------------------------------------------------------------------
async def run_agent(
    pergunta_usuario: str,
    lista_cnpj: list,
    user_name: str,
    estado: str,
    municipio: str,
    thread_id: str | None = None,
) -> str:
    """
    Resumo Principal: Executa o agente de auditoria de forma assíncrona, processando a pergunta
    do usuário, gerenciando o histórico conversacional e retornando a resposta da LLM.

    COMO FUNCIONA:
    1. Resolução da Thread: Garante que exista um thread_id válido (gera UUID se não fornecido).
    2. Resolução do Histórico do Checkpointer: Consulta o grafo SINGLETON para verificar se a
       thread informada já possui histórico de mensagens salvo no InMemorySaver compartilhado.
    3. Construção do Payload de Entrada:
       - Caso seja o primeiro turno: injeta o SystemMessage (instruções e regras de segurança)
         e o HumanMessage com os CNPJs extraídos e metadados geográficos. O contexto do edital
         NÃO é pré-injetado — o agente o busca autonomamente via a tool buscar_contexto_edital.
       - Caso seja um turno subsequente: envia apenas a nova pergunta do usuário. O checkpointer
         restaura automaticamente o histórico pregresso da thread.
    4. Execução Assíncrona do Grafo: Invoca o grafo via ainvoke para não bloquear o event loop.
       As chaves `estado` e `municipio` são sempre incluídas para que o ToolNode as injete
       automaticamente nos parâmetros InjectedState da ferramenta buscar_contexto_edital.
    5. Retorno do Resultado: Extrai e retorna o texto da última mensagem gerada pelo agente.

    Args:
        pergunta_usuario (str): Dúvida ou requisição enviada pelo usuário sobre o edital.
        lista_cnpj (list): Lista de CNPJs pré-extraídos do edital pelo endpoint de upload.
        user_name (str): Nome do usuário logado, usado para personalização do system prompt.
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
        texto_protegido = f"<PERGUNTA>{pergunta_usuario}</PERGUNTA>"
        # Turnos subsequentes: apenas a nova pergunta é enviada para evitar redundância.
        # O checkpointer restaura o histórico pregresso automaticamente.
        mensagens_entrada = [HumanMessage(content=texto_protegido)]
    else:
        # Primeiro turno: injetamos as regras de segurança e os dados da sessão.
        # O SYSTEM_PROMPT contém as instruções permanentes do agente (papel, regras, escopo).
        # O PROMPT_DINAMICO injeta os CNPJs extraídos, metadados geográficos e a pergunta.
        # Nota: o contexto do edital NÃO é pré-injetado aqui. O agente usa a ferramenta
        # buscar_contexto_edital para recuperar trechos relevantes conforme a necessidade.
        cnpjs_formatados = (
            ", ".join(lista_cnpj) if lista_cnpj else "Nenhum CNPJ encontrado no documento."
        )
        system_message = SystemMessage(content=SYSTEM_PROMPT.format(user_name=user_name))
        human_message = HumanMessage(
            content=PROMPT_DINAMICO.format(
                pergunta_usuario=pergunta_usuario,
                cnpjs_formatados=cnpjs_formatados,
                municipio=municipio,
                estado=estado,
            )
        )
        mensagens_entrada = [system_message, human_message]

    # --- 4. Execução Assíncrona do Grafo ---
    # ainvoke é o equivalente assíncrono de invoke. Não bloqueia o event loop do FastAPI,
    # permitindo que o servidor atenda outras requisições enquanto o agente processa.
    # As chaves `estado` e `municipio` são incluídas em TODOS os turnos (mesmo os subsequentes).
    # O InMemorySaver NÃO persiste chaves arbitrárias do estado entre invocações — apenas `messages`
    # recebe tratamento especial via `add_messages`. Portanto, é necessário repassar `estado` e
    # `municipio` a cada chamada para que o InjectedState da ferramenta consiga lê-los do estado ativo.
    result = await graph.ainvoke(
        {"messages": mensagens_entrada, "estado": estado, "municipio": municipio},
        config=config,
    )

    # --- 5. Retorno do Resultado ---
    # A última mensagem da lista é sempre a resposta final do agente após convergir.
    return str(result["messages"][-1].content)
