"""
Pipeline de avaliação automatizada do agente de auditoria contra o golden dataset
(evaluation/golden_dataset.json). Para cada caso: indexa o edital de teste no Pinecone,
roda o agente de ponta a ponta (mesmo grafo/tools/prompt usados em produção) e mede o
resultado em três métricas independentes (aderencia_tools, RAGAS, recall_anomalias),
escrevendo tudo em evaluation/relatorio.json.
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
    EXTRATOR_MODEL,
    EXTRATOR_TEMPERATURE,
    gerenciador,
    retornar_cliente_llm,
)
from app.core.logging_config import logger
from app.core.prompt import PROMPT_DINAMICO, PROMPT_EXTRATOR, SYSTEM_PROMPT
from app.models.laudo import RespostaLaudo
from app.services.ai_engine import escape_xml
from app.services.build_graph import build_graph
from app.services.tools import TOOLS
from app.utils.func_extrair_texto_pdf import extrair_texto_pdf
from evaluation.metricas import calcular_aderencia_tools

# Este script é um ponto de entrada (rodado via `python -m evaluation.pipeline_avaliacao`),
# então é responsabilidade dele configurar o handler do logger "auditor_cidadao" — que por
# padrão só tem um NullHandler (ver app/core/logging_config.py) e absorve tudo silenciosamente.
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logger.addHandler(_handler)
logger.setLevel(logging.INFO)

# Carrega as variáveis de ambiente (como PINECONE_API_KEY) do arquivo .env
load_dotenv()


def _formatar_relatorio_aprovacao(aprovacao: dict, criterios: dict) -> str:
    """
    Monta a versão legível de `aprovacao` para log no terminal — o dict cru (nested,
    com None/True/False misturados) fica ilegível numa linha só de %s no logger.
    """
    LARGURA = 60
    linhas = ["=" * LARGURA, " RESULTADO DA AVALIAÇÃO".center(LARGURA), "=" * LARGURA]

    for nome, resultado in aprovacao.items():
        if nome == "geral":
            continue

        valor = resultado["valor"]
        if valor is None:
            # Métrica não computada (ex.: nenhum caso elegível pro RAGAS ou pra
            # recall_anomalias) — não é reprovação, é "não se aplica".
            linhas.append(f"  {nome:<18}: não computado (métrica não se aplicou)")
            continue

        limiar = criterios[nome]
        # Marcadores em texto puro (não emoji): logging.StreamHandler herda a codepage
        # do console, e no cmd.exe/PowerShell com codepage padrão (cp1252) um emoji aqui
        # derruba o log inteiro com UnicodeEncodeError.
        status = "[OK]     APROVADO" if resultado["aprovado"] else "[FALHOU] REPROVADO"
        linhas.append(f"  {nome:<18}: {valor:.3f}  (mínimo {limiar:.2f})  {status}")

    linhas.append("-" * LARGURA)
    veredito = "[OK]     APROVADO" if aprovacao["geral"] else "[FALHOU] REPROVADO"
    linhas.append(f"  VEREDITO GERAL: {veredito}")
    linhas.append("=" * LARGURA)

    return "\n".join(linhas)


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
    3. Ainda dentro do loop, calcula por caso: aderencia_tools (comparação de tools,
       sem LLM); e, num try/except próprio (ver comentário no loop), roda o extrator
       estruturado sobre o laudo_completo para obter codigos_detectados e o
       recall_anomalias correspondente.
    4. Fora do loop, agrega a média de aderencia_tools e de recall_anomalias entre os
       casos que não falharam (e, no caso de recall_anomalias, que tinham
       anomalias_esperadas de fato).
    5. Limpa o namespace "avaliacao" de novo (não deixa lixo de teste para trás).
    6. Roda o RAGAS só nos casos elegíveis (ver CONTEXTO GERAL DO MÓDULO acima) e
       agrega faithfulness/context_recall.
    7. Compara as três métricas agregadas com CRITERIOS_APROVACAO e monta o veredito
       final (aprovacao["geral"]).
    8. Junta tudo (casos individuais + as três agregações + o veredito de aprovação)
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

    # Réplica do extrator de app/services/ai_engine.py (RespostaLaudo via
    # with_structured_output): não depende de estado entre chamadas, só da configuração
    # do modelo — por isso é criado uma única vez aqui fora, igual ao grafo acima, em vez
    # de recriar um cliente novo a cada caso. Usa EXTRATOR_MODEL/EXTRATOR_TEMPERATURE (o
    # extrator de produção), não AVALIADOR_MODEL — este último é do LLM-juiz do RAGAS,
    # um papel diferente do de extrair a versão estruturada do laudo.
    extrator_estruturado = retornar_cliente_llm(
        model_name=EXTRATOR_MODEL,
        config_params={"temperature": EXTRATOR_TEMPERATURE},
    ).with_structured_output(RespostaLaudo)

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

            # Try/except PRÓPRIO, separado do try do caso: o agente já rodou com sucesso
            # até aqui (laudo_completo, tools_chamadas e aderencia_tools já estão prontos e
            # corretos), então uma falha só na extração estruturada não pode jogar tudo isso
            # fora — mesmo raciocínio de ai_engine.py, que isola a extração num try/except
            # próprio para não derrubar o "done" do streaming se só ela falhar. Aqui, o
            # efeito equivalente de uma falha é: codigos_detectados vira conjunto vazio, e
            # o resto do resultado do caso sobrevive normalmente.
            try:
                resultado_extrator = await extrator_estruturado.ainvoke(
                    [
                        SystemMessage(content=PROMPT_EXTRATOR),
                        HumanMessage(content=laudo_completo),
                    ]
                )
                if resultado_extrator.laudo is not None:
                    codigos_detectados = {
                        anomalia.codigo
                        for anomalia in resultado_extrator.laudo.anomalias
                    }
                else:
                    # laudo=None é esperado para respostas conversacionais (sem anomalia
                    # nenhuma a extrair) — não é uma falha, só não há nada pra detectar.
                    codigos_detectados = set()
            except Exception as e:
                logger.exception(
                    "Erro ao extrair laudo estruturado do caso '%s': %s",
                    caso.get("id", "desconhecido"),
                    str(e),
                )
                codigos_detectados = set()

            # Ambos os branches do try/except acima já deixam codigos_detectados definido
            # (com o conjunto real ou vazio), então o recall pode ser calculado aqui fora,
            # sem duplicar essa conta nos dois lugares.
            codigos_esperados = set(caso.get("anomalias_esperadas", []))
            recall_anomalias = (
                len(codigos_esperados & codigos_detectados) / len(codigos_esperados)
                if codigos_esperados
                else None
            )

            resultados.append(
                {
                    "id": caso.get("id", "desconhecido"),
                    "laudo_completo": laudo_completo,
                    "tools_chamadas": tools_chamadas,
                    "contexto_recuperado": contexto_recuperado,
                    "aderencia_tools": aderencia,
                    "codigos_detectados": sorted(codigos_detectados),
                    "recall_anomalias": recall_anomalias,
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

    # Mesmo raciocínio de agregação de aderencia_tools, só que aqui também precisa excluir
    # os casos com recall_anomalias None — não são "erro", são casos sem anomalias_esperadas
    # (ex.: caso controle conversacional), onde o recall simplesmente não se aplica.
    valores_recall_anomalias = [
        r["recall_anomalias"]
        for r in resultados
        if "erro" not in r and r["recall_anomalias"] is not None
    ]
    media_recall_anomalias = (
        sum(valores_recall_anomalias) / len(valores_recall_anomalias)
        if valores_recall_anomalias
        else None
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
    CRITERIOS_APROVACAO = {
        "aderencia_tools": 0.70,
        "faithfulness": 0.85,
        "context_recall": 0.75,
        "recall_anomalias": 0.80,
    }

    def _avaliar_metrica(nome, valor):
        # valor None significa "não computado" (ex.: nenhum caso elegível pro RAGAS),
        # não "computado e ruim" — por isso aprovado também fica None aqui, e não False.
        # É essa distinção que o `is not False` em aprovacao["geral"] mais abaixo respeita.
        if valor is None:
            return {"valor": None, "aprovado": None}
        return {"valor": valor, "aprovado": valor >= CRITERIOS_APROVACAO[nome]}

    aprovacao = {
        "aderencia_tools": _avaliar_metrica("aderencia_tools", media_aderencia_tools),
        "faithfulness": _avaliar_metrica(
            "faithfulness", ragas_agregado["faithfulness"] if ragas_agregado else None
        ),
        "context_recall": _avaliar_metrica(
            "context_recall",
            ragas_agregado["context_recall"] if ragas_agregado else None,
        ),
        "recall_anomalias": _avaliar_metrica(
            "recall_anomalias", media_recall_anomalias
        ),
    }

    # `is not False` (em vez de checar o valor truthy de "aprovado") é o que garante que uma
    # métrica None (não computada) não reprove a avaliação geral — só uma métrica que
    # rodou e ficou abaixo do limiar (aprovado == False) derruba aprovacao["geral"].
    aprovacao["geral"] = all(m["aprovado"] is not False for m in aprovacao.values())

    relatorio_final = {
        "casos": resultados,
        "ragas_agregado": ragas_agregado,
        "media_aderencia_tools": media_aderencia_tools,
        "media_recall_anomalias": media_recall_anomalias,
        "aprovacao": aprovacao,
    }

    logger.info("\n%s", _formatar_relatorio_aprovacao(aprovacao, CRITERIOS_APROVACAO))

    if salvar_json:
        with open("evaluation/relatorio.json", "w", encoding="utf-8") as f:
            json.dump(relatorio_final, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    asyncio.run(main(salvar_json=False))

# Rodar: clear; python -m evaluation.pipeline_avaliacao