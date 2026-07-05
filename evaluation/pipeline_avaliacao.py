"""
Pipeline de avaliação automatizada do agente de auditoria contra o golden dataset
(evaluation/golden_dataset.json). Para cada caso: indexa o edital de teste no Pinecone,
roda o agente de ponta a ponta (mesmo grafo/tools/prompt usados em produção) e mede o
resultado em duas camadas independentes, escrevendo tudo em evaluation/relatorio.json.
"""

import asyncio
import json
import logging
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

# =============================================================================
# CONTEXTO GERAL DO MÓDULO
#
# Este script roda o mesmo agente de produção (build_graph + TOOLS + SYSTEM_PROMPT)
# contra casos de teste fixos, em vez de reimplementar uma versão simplificada dele —
# isso garante que o resultado da avaliação reflita o comportamento real, não uma
# aproximação. Duas decisões de isolamento tornam isso seguro de rodar repetidamente:
#
#   1. Namespace dedicado no Pinecone ("avaliacao", separado de "production"): a env var
#      PINECONE_NAMESPACE é lida em tempo de chamada por buscar_contexto_edital
#      (app/services/tools.py), então o agente busca no mesmo lugar onde este script
#      acabou de indexar, sem tocar nos dados reais de produção.
#   2. Falha isolada por caso: cada iteração do golden dataset roda dentro do próprio
#      try/except — um PDF corrompido ou uma falha pontual do agente não derruba a
#      avaliação inteira, só marca aquele caso como erro e segue para o próximo.
#
# A avaliação em si tem DUAS métricas independentes, cada uma com seu próprio critério
# de "se aplica ou não":
#   - aderencia_tools (calcular_aderencia_tools, em evaluation/metricas.py): compara as
#     tools chamadas pelo agente com as esperadas no golden dataset. Calculada para
#     TODO caso que não falhou, não depende de LLM nenhum.
#   - RAGAS (faithfulness/context_recall): mede se o laudo do agente é fiel ao contexto
#     recuperado e se esse contexto recuperado cobre o que era esperado. Só se aplica
#     aos casos cujas tools_esperadas incluem buscar_contexto_edital — para os demais
#     (ex.: casos que só consultam sanções), a métrica não faz sentido e o caso é
#     simplesmente pulado dessa camada. Usa um LLM avaliador PRÓPRIO (AVALIADOR_MODEL),
#     desacoplado do LLM do agente principal, para não ter o mesmo modelo jugando a si
#     mesmo com os parâmetros de geração.
#
# Por cima dessas duas métricas, há uma camada de APROVAÇÃO (CRITERIOS_APROVACAO):
# cada métrica agregada é comparada a um limiar mínimo, e "geral" só é True se nenhuma
# métrica aplicável ficou abaixo do seu limiar. Uma métrica que não pôde ser calculada
# (None — ex.: nenhum caso elegível pro RAGAS) não reprova a avaliação por falta de
# dado; só reprova quem realmente rodou e ficou abaixo do esperado.
# =============================================================================

# Este script é um ponto de entrada (rodado via `python -m evaluation.pipeline_avaliacao`),
# então é responsabilidade dele configurar o handler do logger "auditor_cidadao" — que por
# padrão só tem um NullHandler (ver app/core/logging_config.py) e absorve tudo silenciosamente.
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logger.addHandler(_handler)
logger.setLevel(logging.INFO)

# Carrega as variáveis de ambiente (como PINECONE_API_KEY) do arquivo .env
load_dotenv()


def limpar_namespace_avaliacao(namespace: str = "avaliacao"):
    """
    Apaga todos os vetores de um namespace do Pinecone (default: "avaliacao").

    Chamada duas vezes em main(): antes do loop (evita que resíduos de uma execução
    anterior contaminem os resultados desta) e depois dele (não deixa lixo de teste
    acumulado no Pinecone entre execuções). NotFoundException é tratada como caso
    normal, não erro — é exatamente o que acontece na primeiríssima execução, quando
    o namespace "avaliacao" ainda não existe.
    """
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        logger.critical("PINECONE_API_KEY não encontrada no .env")
        return

    logger.info("Conectando ao Pinecone...")
    pc = Pinecone(api_key=api_key)
    index_name = "auditor-cidadao"

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


async def main(salvar_json: bool = True):
    """
    Roda o golden dataset inteiro contra o agente e escreve evaluation/relatorio.json.

    Ordem de execução, por quê cada etapa existe:
    1. Limpa o namespace "avaliacao" do Pinecone (estado limpo antes de indexar).
    2. Para cada caso do golden dataset: indexa o edital de teste, invoca o agente
       numa thread nova (thread_id isolado por caso) e captura tudo que sai do
       streaming de eventos — laudo final, tools chamadas e contexto recuperado.
    3. Calcula aderencia_tools por caso e agrega a média entre os que não falharam.
    4. Limpa o namespace "avaliacao" de novo (não deixa lixo de teste para trás).
    5. Roda o RAGAS só nos casos elegíveis (ver CONTEXTO GERAL DO MÓDULO acima) e
       agrega faithfulness/context_recall.
    6. Compara as métricas agregadas com CRITERIOS_APROVACAO e monta o veredito
       final (aprovacao["geral"]).
    7. Junta tudo (casos individuais + as duas agregações + o veredito de aprovação)
       em evaluation/relatorio.json — só grava o arquivo se salvar_json for True.

    Args:
        salvar_json: quando False, roda a avaliação inteira (inclusive logando o
            veredito) mas não escreve evaluation/relatorio.json — útil para rodar a
            partir de um teste automatizado sem sujar o disco.
    """
    # Direciona buscar_contexto_edital (app/services/tools.py) para o namespace de teste —
    # lido em tempo de chamada pela tool, então precisa estar setado antes do primeiro
    # turno do agente, não só antes da indexação.
    os.environ["PINECONE_NAMESPACE"] = "avaliacao"

    limpar_namespace_avaliacao()

    # Lista para guardar o resultado de cada avaliação do golden dataset.
    resultados = []

    # Carrega o golden dataset de avaliação, que contém casos de teste.
    with open("evaluation/golden_dataset.json", "r", encoding="utf-8") as f:
        golden_dataset = json.load(f)

    # Mapa id -> caso, montado uma única vez: acha o caso original de um item de resultados
    # por "id" sem precisar de um loop de busca a cada iteração.
    golden_dataset_por_id = {caso["id"]: caso for caso in golden_dataset}

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

    # RAGAS já devolve ragas_agregado pronto (calculado mais abaixo); aderencia_tools, por
    # outro lado, fica espalhado — um valor por item dentro de resultados — então a média
    # precisa ser calculada aqui. Casos com "erro" não têm "aderencia_tools" (nunca chegaram
    # a rodar o agente), por isso são excluídos do cálculo em vez de contar como 0.0.
    valores_aderencia = [r["aderencia_tools"] for r in resultados if "erro" not in r]
    # `if valores_aderencia else None` evita ZeroDivisionError se todos os casos
    # falharem (raro, mas possível — ex.: Pinecone fora do ar durante toda a execução).
    media_aderencia_tools = (
        sum(valores_aderencia) / len(valores_aderencia) if valores_aderencia else None
    )

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

    # Limiares mínimos para cada métrica ser considerada aprovada — ajuste aqui conforme
    # o padrão de qualidade esperado for calibrado com mais execuções do golden dataset.
    CRITERIOS_APROVACAO = {"aderencia_tools": 0.70, "faithfulness": 0.85, "context_recall": 0.75}

    def _avaliar_metrica(nome, valor):
        # valor None significa "não computado" (ex.: nenhum caso elegível pro RAGAS),
        # não "computado e ruim" — por isso aprovado também fica None aqui, e não False.
        # É essa distinção que o `is not False` em aprovacao["geral"] mais abaixo respeita.
        if valor is None:
            return {"valor": None, "aprovado": None}
        return {"valor": valor, "aprovado": valor >= CRITERIOS_APROVACAO[nome]}

    aprovacao = {
        "aderencia_tools": _avaliar_metrica("aderencia_tools", media_aderencia_tools),
        "faithfulness": _avaliar_metrica("faithfulness", ragas_agregado["faithfulness"] if ragas_agregado else None),
        "context_recall": _avaliar_metrica("context_recall", ragas_agregado["context_recall"] if ragas_agregado else None),
    }

    # `is not False` (em vez de checar o valor truthy de "aprovado") é o que garante que uma
    # métrica None (não computada) não reprove a avaliação geral — só uma métrica que
    # rodou e ficou abaixo do limiar (aprovado == False) derruba aprovacao["geral"].
    aprovacao["geral"] = all(m["aprovado"] is not False for m in aprovacao.values())

    relatorio_final = {
        "casos": resultados,
        "ragas_agregado": ragas_agregado,
        "media_aderencia_tools": media_aderencia_tools,
        "aprovacao": aprovacao,
    }

    logger.info("\nResultado da avaliação: %s", aprovacao)

    if salvar_json:
        with open("evaluation/relatorio.json", "w", encoding="utf-8") as f:
            json.dump(relatorio_final, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main(salvar_json=False))
