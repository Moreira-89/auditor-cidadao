from fastapi import APIRouter

from app.core.dependencies import gerenciador
from app.models.pergunta_request import PerguntaRequest
from app.services.ai_engine import run_agent

# -----------------------------------------------------------------------------
# INICIALIZAÇÃO
# -----------------------------------------------------------------------------
# Criação do roteador FastAPI para o endpoint de chat.
# O prefixo define a URL base e a tag organiza a exibição no Swagger UI.
router = APIRouter(prefix="/conversar-com-auditor", tags=["Conversar sobre o edital"])


# -----------------------------------------------------------------------------
# ENDPOINTS
# -----------------------------------------------------------------------------
@router.post("/")
def executar_pergunta(request: PerguntaRequest):
    """
    Objetivo: Endpoint principal de chat (Perguntas e Respostas).
    Implementa a etapa de "Recuperação e Geração" (RAG - Retrieval-Augmented Generation).

    COMO FUNCIONA:
    1. Busca de Contexto (Retrieval): Pega a pergunta do usuário e busca no Pinecone
       os trechos do edital (chunks) que são mais parecidos semanticamente com a pergunta.
       Usa os filtros de estado e município para não misturar editais de locais diferentes.
    2. Execução do Agente (Generation): Envia a pergunta, o contexto recuperado e a
       lista de CNPJs para o agente de IA (`run_agent`).
       O agente analisa os dados, podendo consultar APIs externas (como a Receita Federal)
       se necessário, e formula a resposta final.

    Args:
        request (PerguntaRequest): Corpo da requisição contendo a pergunta, estado,
                                   município, nome do usuário e lista de CNPJs previamente extraídos.

    Returns:
        dict: Resposta gerada pela Inteligência Artificial.
    """

    # --- 1. Busca de Contexto (Retrieval) ---
    # Em vez de enviar o edital inteiro para o LLM (o que seria caro e poderia
    # estourar o limite de tokens), buscamos apenas os parágrafos mais relevantes.
    # O 'buscar_contexto' transforma a pergunta em vetor e acha os vetores mais
    # próximos no banco de dados.
    contexto = gerenciador.buscar_contexto(
        pergunta=request.pergunta,
        estado=request.estado,
        municipio=request.municipio
    )

    # --- 2. Execução do Agente (Generation) ---
    # Passamos o contexto enxuto (apenas as partes relevantes do edital) para o LLM.
    # A 'lista_cnpj' é enviada para que a IA saiba de antemão quais empresas
    # pesquisar, garantindo que o agente possa usar suas 'tools' (ferramentas)
    # para consultar os dados dessas empresas na Receita Federal.
    resposta = run_agent(
        pergunta_usuário=request.pergunta,
        lista_cnpj=request.lista_cnpjs,
        contexto=contexto,
        user_name=request.user_name
    )

    # Retorna a resposta final empacotada em um JSON
    return {"resultado_pergunta": resposta}
