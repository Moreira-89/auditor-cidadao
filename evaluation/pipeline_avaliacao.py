"""
Pipeline de avaliação automática do agente, rodado como script (não faz parte da API).

Ele testa o agente contra o "golden dataset" (evaluation/golden_dataset.json) — um conjunto
de casos com gabarito: cada caso diz qual edital usar, o que perguntar e o que se espera de
resposta. Para cada caso: indexa o edital de teste no Pinecone, roda o agente de ponta a
ponta (o MESMO grafo/tools/prompt de produção) e mede três métricas independentes:
  - aderencia_tools  — o agente chamou as ferramentas certas? (comparação direta, sem LLM)
  - recall_anomalias — o agente detectou as anomalias esperadas (catálogo A–I)?
  - RAGAS            — o contexto recuperado do edital foi suficiente (context_recall) e a
                       resposta ficou fiel a esse contexto, sem alucinar (faithfulness)?
O resultado consolidado é gravado em evaluation/relatorio.json.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from datetime import date
from typing import Any

from datasets import Dataset
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver
from pinecone import Pinecone
from pinecone.exceptions import NotFoundException
from ragas import evaluate
from ragas.dataset_schema import EvaluationResult
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
    except Exception as e:  # noqa: BLE001 — limpeza é best-effort, não deve propagar
        logger.error("Erro ao limpar o namespace '%s': %s", namespace, str(e))


def _aguardar_contagem_namespace(
    contagem_esperada: int,
    namespace: str = "avaliacao",
    timeout: float = 60.0,
    intervalo: float = 1.0,
):
    """
    Bloqueia até o namespace ter EXATAMENTE `contagem_esperada` vetores consultáveis,
    contornando a consistência eventual do Pinecone: um upsert (ou delete) não fica
    visível para o similarity_search no mesmo instante em que a chamada HTTP retorna.

    Sem essa barreira, o agente podia chamar buscar_contexto_edital antes de os chunks
    do caso terem propagado — recuperando 0/parte dos trechos — o que derrubava
    context_recall e faithfulness de forma não-determinística entre execuções (a origem
    da variância observada no RAGAS). describe_index_stats é o canal recomendado pelo
    Pinecone para checar a freshness da indexação.
    """
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index("auditor-cidadao")

    inicio = time.monotonic()
    while True:
        try:
            namespaces = (
                index.describe_index_stats().to_dict().get("namespaces", {}) or {}
            )
            contagem = namespaces.get(namespace, {}).get("vector_count", 0)
        except NotFoundException:
            # Namespace ainda não existe (ex.: logo após um delete_all que já propagou)
            contagem = 0

        if contagem == contagem_esperada:
            return

        if time.monotonic() - inicio > timeout:
            logger.warning(
                "Timeout (%.0fs) aguardando namespace '%s' atingir %d vetores "
                "(atual=%d) — seguindo mesmo assim; o retrieval deste caso pode "
                "ficar incompleto.",
                timeout,
                namespace,
                contagem_esperada,
                contagem,
            )
            return

        time.sleep(intervalo)


# As três funções abaixo isolam os únicos I/Os de arquivo síncronos e bloqueantes
# do módulo, para serem chamadas via `asyncio.to_thread(...)` a partir de `main`
# (que é uma coroutine) sem travar o event loop durante a leitura/escrita em disco.
def _ler_golden_dataset() -> list[dict]:
    with open("evaluation/golden_dataset.json", "r", encoding="utf-8") as f:
        return json.load(f)


def _ler_arquivo_binario(caminho: str) -> bytes:
    with open(caminho, "rb") as f:
        return f.read()


def _salvar_relatorio(relatorio: dict) -> None:
    with open("evaluation/relatorio.json", "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=2)


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
    # Cada caso recebe um namespace EXCLUSIVO ("avaliacao_<id>"), setado em
    # os.environ["PINECONE_NAMESPACE"] dentro do loop — buscar_contexto_edital
    # (app/services/tools.py) lê essa env em tempo de chamada. O motivo de ser um
    # namespace por caso (em vez de um "avaliacao" único reaproveitado) está no
    # comentário do loop abaixo: elimina a corrida de consistência do delete/re-add.
    # namespaces_usados guarda o que foi criado para uma limpeza final única.
    namespaces_usados: set[str] = set()

    # Lista para guardar o resultado de cada avaliação do golden dataset.
    resultados = []

    # Carrega o golden dataset de avaliação, que contém casos de teste.
    golden_dataset = await asyncio.to_thread(_ler_golden_dataset)

    # Mapa id -> caso, montado uma única vez: acha o caso original de um item de resultados
    # por "id" sem precisar de um loop de busca a cada iteração.
    golden_dataset_por_id = {caso["id"]: caso for caso in golden_dataset}

    # InMemorySaver basta aqui: cada run da avaliação é isolado e efêmero, sem necessidade
    # de persistir o histórico entre processos como faz o Redis em produção (lifespan.py).
    grafo = build_graph(TOOLS, checkpointer=InMemorySaver())

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
                conteudo_bytes = await asyncio.to_thread(_ler_arquivo_binario, caminho_pdf)

                texto_extraido, _ = extrair_texto_pdf(
                    conteudo_bytes, os.path.basename(caminho_pdf)
                )
                texto_extraido += caso.get("trecho_injetado", "")

            metadados = {"estado": caso["estado"], "municipio": caso["municipio"]}

            # Namespace EXCLUSIVO por caso + barreira de consistência.
            #
            # Por que um namespace por caso (e não um "avaliacao" único reaproveitado):
            # com um namespace compartilhado, casos consecutivos do mesmo município
            # (ex.: caso_05 e caso_06, ambos Melgaço) faziam limpar-e-reindexar o MESMO
            # namespace em sequência. Mesmo esperando o vector_count, o filtro por
            # metadados do Pinecone tem um lag de freshness próprio nesse padrão de
            # delete/re-add adjacente, e a busca do caso_06 voltava VAZIA de forma
            # intermitente (flicker VAZIO<->cheio entre execuções) — variância residual
            # do RAGAS. Com um namespace só para este caso, não há adjacência de
            # delete/re-add: limpamos só resíduo de execuções ANTERIORES (já propagado
            # há minutos), esperamos zerar, indexamos e esperamos propagar.
            namespace_caso = f"avaliacao_{caso['id']}"
            # Setado ANTES do turno do agente — a tool lê PINECONE_NAMESPACE em tempo de chamada.
            os.environ["PINECONE_NAMESPACE"] = namespace_caso
            namespaces_usados.add(namespace_caso)

            limpar_namespace_avaliacao(namespace_caso)
            _aguardar_contagem_namespace(0, namespace=namespace_caso)

            lista_chunks = gerenciador.chunkizar_documento(texto_extraido)
            gerenciador.processar_e_salvar(
                lista_chunks, metadados, namespace=namespace_caso
            )
            _aguardar_contagem_namespace(len(lista_chunks), namespace=namespace_caso)

            thread_id = str(uuid.uuid4())
            config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

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
            # Réplica intencional de app/services/ai_engine.py (mesmo padrão de produção)
            data_hoje = date.today().strftime("%Y%m%d")  # noqa: DTZ011
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
                    chunk = evento["data"].get("chunk")
                    if (
                        chunk is not None
                        and chunk.content
                        and not getattr(chunk, "tool_calls", None)
                    ):
                        buffer_temporario += chunk.content

                elif tipo_evento == "on_chat_model_end":
                    # Mensagem completa — agora sabemos com certeza se ela tinha tool_calls
                    mensagem_final = evento["data"].get("output")
                    if not getattr(mensagem_final, "tool_calls", None):
                        laudo_completo += buffer_temporario

                elif tipo_evento == "on_tool_start":
                    tools_chamadas.append(
                        {"tool": evento["name"], "input": evento["data"].get("input")}
                    )

                # Captura o output de buscar_contexto_edital — os trechos do edital que o
                # RAG efetivamente recuperou, para comparar com contexto_edital_esperado.
                # O input de todas as tools já foi capturado em on_tool_start; aqui só nos
                # importa o output do RAG. data["output"] vem como ToolMessage (o ToolNode
                # embrulha o retorno da tool nela) — .content extrai a string crua, senão o
                # pyarrow do datasets não consegue serializar o objeto no Dataset.from_dict.
                elif (
                    tipo_evento == "on_tool_end"
                    and evento["name"] == "buscar_contexto_edital"
                ):
                    saida_tool = evento["data"].get("output")
                    contexto_recuperado.append(getattr(saida_tool, "content", saida_tool))

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
            except Exception as e:  # noqa: BLE001 — isola a falha só desta etapa, ver comentário acima
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
        except Exception as e:  # noqa: BLE001
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

    # Limpa todos os namespaces por caso criados nesta execução — não deixa lixo de
    # teste acumulado no Pinecone entre execuções (um namespace "avaliacao_<id>" por caso).
    for namespace_caso in namespaces_usados:
        limpar_namespace_avaliacao(namespace_caso)

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

        if caso_original.get("excluir_do_ragas"):
            # Casos com contexto_edital_esperado estruturalmente não-avaliável por
            # context_recall (ex.: caso_06 — gabarito é uma afirmação NEGATIVA, "o
            # edital não traz X", que não é um trecho literal atribuível a nenhum
            # chunk recuperado). Continuam normalmente em aderencia_tools e
            # recall_anomalias — só ficam de fora do dataset do RAGAS.
            continue

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
        # evaluate() só devolve Executor quando chamado com return_executor=True (não é o
        # caso aqui) — o assert só existe para o type checker, o retorno real já é sempre
        # EvaluationResult neste ponto.
        assert isinstance(resultado_ragas, EvaluationResult)
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

    aprovacao: dict[str, Any] = {
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
        await asyncio.to_thread(_salvar_relatorio, relatorio_final)


if __name__ == "__main__":
    asyncio.run(main(salvar_json=False))

# Rodar: clear; python -m evaluation.pipeline_avaliacao
