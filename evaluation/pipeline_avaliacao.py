import asyncio
import json
import os
import uuid
from datetime import date

from datasets import Dataset
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from pinecone import Pinecone
from pinecone.exceptions import NotFoundException
from ragas import evaluate
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import context_recall, faithfulness

from app.core.dependencies import (
    AVALIADOR_MODEL,
    AVALIADOR_TEMPERATURE,
    gerenciador,
    retornar_cliente_llm,
)
from app.core.logging_config import logger
from app.core.prompt import PROMPT_DINAMICO, SYSTEM_PROMPT
from app.services.ai_engine import escape_xml
from app.services.build_graph import build_graph
from app.services.tools import TOOLS
from app.utils.func_extrair_texto_pdf import extrair_texto_pdf
from evaluation.metricas import calcular_aderencia_tools

# Carrega as variáveis de ambiente (como PINECONE_API_KEY) do arquivo .env
load_dotenv()

# Direciona a tool buscar_contexto_edital (app/services/tools.py) para o namespace "avaliacao",
# onde este script indexa os editais de teste — sem isso, ela cai no default "production" e
# nunca encontra o que acabou de ser indexado aqui.
os.environ["PINECONE_NAMESPACE"] = "avaliacao"

# Carrega o golden dataset de avaliação, que contém casos de teste.
with open("evaluation/golden_dataset.json", "r", encoding="utf-8") as f:
    golden_dataset = json.load(f)

# Mapa id -> caso, montado uma única vez: acha o caso original de um item de resultados
# por "id" sem precisar de um loop de busca a cada iteração.
golden_dataset_por_id = {caso["id"]: caso for caso in golden_dataset}


def limpar_namespace_avaliacao():
    """Limpa o namespace 'avaliacao' do Pinecone antes de rodar a avaliação, evitando que
    resíduos de execuções anteriores contaminem os resultados do golden dataset."""
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        logger.critical("PINECONE_API_KEY não encontrada no .env")
        return

    logger.info("Conectando ao Pinecone...")
    pc = Pinecone(api_key=api_key)
    index_name = "auditor-cidadao"
    namespace = "avaliacao"

    try:
        index = pc.Index(index_name)

        logger.info("Limpando namespace '%s' do índice '%s'...", namespace, index_name)
        index.delete(delete_all=True, namespace=namespace)

        logger.info("Namespace '%s' limpo com sucesso!", namespace)
    except NotFoundException:
        # Namespace ainda não existe (ex.: primeira execução da avaliação) - nada a limpar
        logger.info("Namespace '%s' ainda não existe, nada para limpar.", namespace)
    except Exception as e:
        logger.error("Erro ao limpar o namespace '%s': %s", namespace, str(e))


# Limpa o banco vetorial antes de rodar a avaliação para garantir que os resultados do golden dataset não sejam contaminados por execuções anteriores.
limpar_namespace_avaliacao()

# Lista para guardar o resultado de cada avaliação do golden dataset.
resultados = []


async def main():
    grafo = build_graph(TOOLS)

    for caso in golden_dataset:
        try:
            caminho_pdf = caso["caminho_pdf"]

            if caminho_pdf is None:
                texto_extraido = caso["contexto_edital_esperado"]
            else:
                with open(caminho_pdf, "rb") as f:
                    conteudo_bytes = f.read()

                texto_extraido, _ = extrair_texto_pdf(
                    conteudo_bytes, os.path.basename(caminho_pdf)
                )
                texto_extraido += caso.get("trecho_injetado", "")

            metadados = {"estado": caso["estado"], "municipio": caso["municipio"]}

            gerenciador.executar(
                texto_edital=texto_extraido, metadados=metadados, namespace="avaliacao"
            )

            thread_id = str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}

            # Réplica do primeiro turno em ai_engine.run_agent: sempre "primeiro turno",
            # já que cada caso do golden dataset roda numa thread nova e isolada
            pergunta_usuario = escape_xml(caso["pergunta"])
            estado_escapado = escape_xml(caso["estado"])
            municipio_escapado = escape_xml(caso["municipio"])
            cnpjs_formatados = escape_xml(
                ", ".join(caso.get("cnpjs", []))
                if caso.get("cnpjs")
                else "Nenhum CNPJ encontrado no documento."
            )

            system_message = SystemMessage(content=SYSTEM_PROMPT)
            data_hoje = date.today().strftime("%Y%m%d")
            human_message = HumanMessage(
                content=PROMPT_DINAMICO.format(
                    pergunta_usuario=pergunta_usuario,
                    cnpjs_formatados=cnpjs_formatados,
                    municipio=municipio_escapado,
                    estado=estado_escapado,
                    data_hoje=data_hoje,
                )
            )
            mensagens_entrada = [system_message, human_message]

            # Acumula os nomes das tools chamadas pelo agente e o laudo final gerado,
            # seguindo o mesmo padrão de streaming usado em ai_engine.run_agent
            tools_chamadas = []
            contexto_recuperado = []
            laudo_completo = ""
            buffer_temporario = ""

            async for evento in grafo.astream_events(
                input={
                    "messages": mensagens_entrada,
                    "estado": caso["estado"],
                    "municipio": caso["municipio"],
                },
                config={**config, "recursion_limit": 50},
                version="v2",
            ):
                tipo_evento = evento["event"]

                if tipo_evento == "on_chat_model_start":
                    # Nova mensagem do LLM começando — reseta o buffer da rodada anterior
                    buffer_temporario = ""

                elif tipo_evento == "on_chat_model_stream":
                    chunk = evento["data"]["chunk"]
                    if chunk.content and not getattr(chunk, "tool_calls", None):
                        buffer_temporario += chunk.content

                elif tipo_evento == "on_chat_model_end":
                    # Mensagem completa — agora sabemos com certeza se ela tinha tool_calls
                    mensagem_final = evento["data"]["output"]
                    if not getattr(mensagem_final, "tool_calls", None):
                        laudo_completo += buffer_temporario

                elif tipo_evento == "on_tool_start":
                    tools_chamadas.append(
                        {"tool": evento["name"], "input": evento["data"].get("input")}
                    )

                elif tipo_evento == "on_tool_end":
                    # Captura o output de buscar_contexto_edital — os trechos do edital
                    # que o RAG efetivamente recuperou, para comparar com
                    # contexto_edital_esperado. O input de todas as tools já foi
                    # capturado em on_tool_start; aqui só nos importa o output do RAG.
                    # data["output"] vem como ToolMessage (o ToolNode embrulha o retorno da
                    # tool nela) — .content extrai a string crua, senão o pyarrow do
                    # datasets não consegue serializar o objeto no Dataset.from_dict.
                    if evento["name"] == "buscar_contexto_edital":
                        saida_tool = evento["data"].get("output")
                        contexto_recuperado.append(
                            getattr(saida_tool, "content", saida_tool)
                        )

            aderencia = calcular_aderencia_tools(caso, tools_chamadas)

            resultados.append(
                {
                    "id": caso.get("id", "desconhecido"),
                    "laudo_completo": laudo_completo,
                    "tools_chamadas": tools_chamadas,
                    "contexto_recuperado": contexto_recuperado,
                    "aderencia_tools": aderencia,
                }
            )
        except Exception as e:
            # Falha isolada num caso (PDF corrompido, erro no Pinecone, erro do agente, etc.)
            # não deve interromper a avaliação dos demais casos do golden dataset
            logger.exception(
                "Falha ao processar caso '%s': %s",
                caso.get("id", "desconhecido"),
                str(e),
            )
            resultados.append(
                {
                    "id": caso.get("id", "desconhecido"),
                    "erro": str(e),
                }
            )
            continue

    limpar_namespace_avaliacao()

    llm_ragas = LangchainLLMWrapper(
        retornar_cliente_llm(
            model_name=AVALIADOR_MODEL,
            config_params={"temperature": AVALIADOR_TEMPERATURE},
        )
    )

    # Monta as 4 listas paralelas que o RAGAS espera em Dataset.from_dict(...).
    # Só entram casos que (1) não falharam e (2) esperavam buscar_contexto_edital —
    # RAGAS mede recuperação de contexto, não se aplica a casos sem essa tool.
    eval_data = {"question": [], "answer": [], "contexts": [], "ground_truth": []}
    for item in resultados:
        if "erro" in item:
            continue  # caso falhou — não tem laudo_completo nem contexto_recuperado

        caso_original = golden_dataset_por_id[item["id"]]

        nomes_tools_esperadas = {
            tool["tool"] for tool in caso_original.get("tools_esperadas", [])
        }
        if "buscar_contexto_edital" not in nomes_tools_esperadas:
            continue  # RAGAS não se aplica a este caso

        eval_data["question"].append(caso_original["pergunta"])
        eval_data["answer"].append(item["laudo_completo"])
        eval_data["contexts"].append(item["contexto_recuperado"])
        eval_data["ground_truth"].append(caso_original["contexto_edital_esperado"])

    ragas_agregado = None

    if not eval_data["question"]:
        # Dataset.from_dict aceita listas vazias, mas evaluate() sobre 0 linhas lança
        # exceção (ou devolve resultado sem sentido) — melhor pular a etapa com um log
        # do que deixar o RAGAS quebrar aqui.
        logger.warning(
            "Nenhum caso elegível para o RAGAS (todos falharam ou nenhum esperava "
            "buscar_contexto_edital) — pulando avaliação de recuperação de contexto."
        )
    else:
        dataset_ragas = Dataset.from_dict(eval_data)
        logger.info("Rodando RAGAS para avaliação de recuperação de contexto...")
        resultado_ragas = evaluate(
            dataset_ragas, metrics=[faithfulness, context_recall], llm=llm_ragas
        )
        logger.info("RAGAS finalizado. Resultados: %s", resultado_ragas)

        # resultado_ragas é um EvaluationResult (dataclass sem __iter__/keys()) — dict(resultado_ragas)
        # lançaria TypeError. __getitem__ é público e devolve os scores por linha de cada métrica;
        # agregamos a média nós mesmos, sem precisar de to_pandas() nem granularidade por linha.
        ragas_agregado = {
            metrica.name: (
                sum(resultado_ragas[metrica.name]) / len(resultado_ragas[metrica.name])
            )
            for metrica in [faithfulness, context_recall]
        }

    relatorio_final = {
        "casos": resultados,
        "ragas_agregado": ragas_agregado,
    }

    with open("evaluation/relatorio.json", "w", encoding="utf-8") as f:
        json.dump(relatorio_final, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
