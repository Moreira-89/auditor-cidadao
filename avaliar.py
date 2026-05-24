"""
Script: Avaliação automática do Auditor Cidadão contra o Golden Dataset.

COMO FUNCIONA:
1. Leitura do Dataset: Carrega o golden_dataset.json com os casos de teste.
2. Indexação (opcional): Lê cada PDF, extrai o texto e indexa no Pinecone com os metadados do caso.
   Pode ser pulado via flag --skip-upload se os PDFs já estão indexados.
3. Execução do Agente: Para cada caso, busca o contexto e roda o agente.
4. Verificação: Compara a resposta do agente contra as palavras-chave esperadas e proibidas.
5. Relatório: Imprime o status de cada caso e métricas agregadas (recall, precision).

USO:
    python -m avaliar                  # roda tudo (upload + avaliação)
    python -m avaliar --skip-upload    # só avaliação (PDFs já indexados)

PRÉ-REQUISITOS:
- Variáveis de ambiente GROQ_API_KEY e PINECONE_API_KEY configuradas no .env.
- PDFs sintéticos gerados (rode `python -m app.utils.func_gerar_pdfs_teste` antes).
- PDFs reais (ex: Suzano) já presentes em app/editais_teste/.
"""

import argparse
import io
import json
import logging
import time

import pdfplumber

from app.core.dependencies import gerenciador
from app.core.logging_config import logger
from app.services.ai_engine import run_agent
from app.utils.func_pdf_generator import gerar_pdf


# -----------------------------------------------------------------------------
# CONFIGURAÇÃO
# -----------------------------------------------------------------------------
# ATENÇÃO: O caminho deve ser relativo à raiz do projeto, de onde o script
# é executado via `python -m avaliar`. O prefixo `app/` é necessário.
CAMINHO_DATASET = "app/editais_teste/golden_dataset.json"
LIMIAR_COBERTURA = 0.8  # cobertura mínima de palavras-chave pra considerar PASS


# -----------------------------------------------------------------------------
# INDEXAÇÃO DOS PDFs NO PINECONE
# -----------------------------------------------------------------------------

def indexar_pdf(caso: dict) -> None:
    """
    Objetivo: Ler um PDF do caso e indexá-lo no Pinecone com os metadados corretos.

    COMO FUNCIONA:
    1. Leitura: Abre o PDF do caminho indicado em pdf_path.
    2. Extração de Texto: Usa pdfplumber pra extrair texto de todas as páginas.
    3. Indexação: Chama o gerenciador vetorial pra chunkizar e salvar no Pinecone.

    Args:
        caso (dict): Dicionário com os dados do caso, incluindo pdf_path, estado e municipio.

    Raises:
        FileNotFoundError: Se o pdf_path indicado no caso não existir no disco.
        Exception: Qualquer erro propagado pelo gerenciador vetorial durante a indexação.
    """
    # --- 1. Leitura ---
    with open(caso["pdf_path"], "rb") as f:
        conteudo_bytes = f.read()

    # --- 2. Extração de Texto ---
    # io.BytesIO cria um "arquivo virtual" na RAM para evitar I/O em disco.
    # `or ""` previne erros em páginas que contenham apenas imagens (retorno None).
    with pdfplumber.open(io.BytesIO(conteudo_bytes)) as pdf:
        texto = "\n".join(pagina.extract_text() or "" for pagina in pdf.pages)

    # --- 3. Indexação ---
    # O gerenciador é o singleton de `dependencies` — sem overhead de reconexão.
    # Os metadados são cruciais para o filtro na busca semântica posterior.
    gerenciador.executar(
        texto_edital=texto,
        metadados={
            "municipio": caso["municipio"],
            "estado": caso["estado"],
            "arquivo": caso["pdf_path"],
        },
    )


# -----------------------------------------------------------------------------
# AVALIAÇÃO DE UM CASO
# -----------------------------------------------------------------------------

def avaliar_caso(caso: dict) -> dict:
    """
    Objetivo: Executar o agente para um caso de teste e verificar se a resposta atende aos critérios.

    COMO FUNCIONA:
    1. Busca de Contexto: Recupera os chunks relevantes do Pinecone com filtro por estado/município.
    2. Execução do Agente: Roda o agente com a pergunta e os CNPJs do caso.
    3. Checagem de Palavras-Chave: Calcula a cobertura — quantas palavras-chave esperadas
       apareceram na resposta (proxy de recall).
    4. Checagem de Palavras Proibidas: Identifica termos que NÃO deveriam aparecer
       (proxy de precisão / detecção de alucinação).
    5. Decisão: Marca como PASS se cobertura >= LIMIAR_COBERTURA E não houver violações.

    Args:
        caso (dict): Caso completo do golden dataset.

    Returns:
        dict: Resultado estruturado contendo id, tipo, status, métricas e resposta resumida.
    """
    # --- 1. Busca de Contexto ---
    inicio = time.time()
    contexto = gerenciador.buscar_contexto(
        pergunta=caso["pergunta"],
        estado=caso["estado"],
        municipio=caso["municipio"],
    )

    # --- 2. Execução do Agente ---
    resposta = run_agent(
        pergunta_usuario=caso["pergunta"],
        lista_cnpj=caso["cnpjs"],
        contexto=contexto,
        user_name="Avaliador",
    )
    duracao = time.time() - inicio

    resposta_lower = resposta.lower()

    # --- 3. Checagem de Palavras-Chave Esperadas ---
    acertos = [
        palavra for palavra in caso["palavras_chave_esperadas"]
        if palavra.lower() in resposta_lower
    ]
    cobertura = (
        len(acertos) / len(caso["palavras_chave_esperadas"])
        if caso["palavras_chave_esperadas"] else 1.0
    )

    # --- 4. Checagem de Palavras Proibidas ---
    violacoes = [
        palavra for palavra in caso["palavras_proibidas"]
        if palavra.lower() in resposta_lower
    ]

    # --- 5. Decisão ---
    passou = cobertura >= LIMIAR_COBERTURA and len(violacoes) == 0

    return {
        "id": caso["id"],
        "tipo": caso["tipo"],
        "passou": passou,
        "cobertura": cobertura,
        "acertos": acertos,
        "faltas": [p for p in caso["palavras_chave_esperadas"] if p not in acertos],
        "violacoes": violacoes,
        "duracao_s": round(duracao, 2),
        "resposta": resposta,
    }


# -----------------------------------------------------------------------------
# EXECUÇÃO PRINCIPAL
# -----------------------------------------------------------------------------

def main() -> None:
    """
    Objetivo: Orquestrar o fluxo de avaliação completo.

    COMO FUNCIONA:
    1. Parse de Argumentos: Detecta a flag --skip-upload pra pular as fases de preparo.
    2. Geração dos PDFs Sintéticos: Cria os arquivos PDF (casos 001-005) a partir do
       `pdf_content` do JSON, antes de tentar indexá-los. PDFs reais são pulados.
    3. Indexação: Sobe todos os PDFs (sintéticos + reais) no Pinecone.
    4. Avaliação: Roda o agente em cada caso e coleta os resultados.
    5. Relatório: Apresenta detalhamento por caso e métricas agregadas.
    """
    # --- 1. Parse de Argumentos ---
    parser = argparse.ArgumentParser(description="Avaliador do Auditor Cidadão.")
    parser.add_argument(
        "--skip-upload",
        action="store_true",
        help="Pula a indexação dos PDFs (use se já estão no Pinecone).",
    )
    args = parser.parse_args()

    # Carrega o dataset
    with open(CAMINHO_DATASET, encoding="utf-8") as f:
        casos = json.load(f)

    # --- 2. Geração dos PDFs Sintéticos ---
    # Antes de indexar, precisamos garantir que os PDFs sintéticos existem em disco.
    # Casos sem `pdf_content` são PDFs reais (já existem) e são pulados automaticamente.
    if not args.skip_upload:
        logger.info("=" * 60)
        logger.info("FASE 0 — GERANDO PDFs SINTÉTICOS")
        logger.info("=" * 60)
        for caso in casos:
            if "pdf_content" not in caso:
                # PDF real não precisa ser gerado — apenas registramos o aviso.
                logger.warning("  ~ %-10s | PDF real — não gerado", caso["id"])
                continue
            try:
                gerar_pdf(
                    caminho_saida=caso["pdf_path"],
                    titulo=caso["pdf_content"]["titulo"],
                    paragrafos=caso["pdf_content"]["paragrafos"],
                )
                logger.info("  ✓ %-10s | GERADO → %s", caso["id"], caso["pdf_path"])
            except Exception as e:
                # Registramos o erro mas continuamos os demais casos.
                logger.error("  ✗ %-10s | ERRO ao gerar: %s", caso["id"], e)

    # --- 3. Indexação dos PDFs ---
    if not args.skip_upload:
        logger.info("=" * 60)
        logger.info("FASE 1 — INDEXANDO %d PDFs NO PINECONE", len(casos))
        logger.info("=" * 60)
        for caso in casos:
            try:
                indexar_pdf(caso)
                logger.info("  ✓ %-10s | indexado", caso["id"])
            except FileNotFoundError:
                # O PDF não foi encontrado em disco — provável caso real não disponível.
                logger.error("  ✗ %-10s | PDF não encontrado: %s", caso["id"], caso["pdf_path"])
            except Exception as e:
                logger.error("  ✗ %-10s | ERRO: %s", caso["id"], e)
    else:
        # Flag --skip-upload ativa: pulamos a indexação pois os vetores já estão no Pinecone.
        logger.info("Etapa de upload pulada (--skip-upload).")

    # --- 4. Avaliação ---
    logger.info("=" * 60)
    logger.info("FASE 2 — AVALIANDO %d CASOS", len(casos))
    logger.info("=" * 60)

    resultados = []
    for caso in casos:
        logger.info("  → Rodando %s...", caso["id"])
        try:
            resultado = avaliar_caso(caso)
            resultados.append(resultado)
            status = "PASS" if resultado["passou"] else "FAIL"
            # Registramos o resultado final do caso com o tempo de execução.
            logger.info("  %s %s (%ss)", status, caso["id"], resultado["duracao_s"])
        except Exception as e:
            logger.error("  ERRO no caso %s: %s", caso["id"], e)

    # --- 5. Relatório Final ---
    logger.info("=" * 60)
    logger.info("RELATÓRIO FINAL")
    logger.info("=" * 60)

    total = len(resultados)
    if total == 0:
        logger.warning("Nenhum caso foi avaliado com sucesso.")
        return

    passaram = sum(1 for r in resultados if r["passou"])
    taxa = passaram / total

    logger.info("Total: %d | Passaram: %d | Falharam: %d", total, passaram, total - passaram)
    logger.info("Taxa de sucesso: %.0f%%", taxa * 100)

    # Detalhamento por caso
    logger.info("─" * 60)
    logger.info("DETALHAMENTO POR CASO")
    logger.info("─" * 60)
    for r in resultados:
        status = "[PASS]" if r["passou"] else "[FAIL]"
        logger.info(
            "%s %-10s | cobertura: %.0f%% | violações: %d | tempo: %ss",
            status, r["id"], r["cobertura"] * 100, len(r["violacoes"]), r["duracao_s"],
        )
        if r["faltas"]:
            # Palavras-chave esperadas que não apareceram na resposta do agente.
            logger.warning("        ⚠ faltou: %s", r["faltas"])
        if r["violacoes"]:
            # Termos proibidos que apareceram — possível alucinação do modelo.
            logger.warning("        ⚠ violou: %s", r["violacoes"])

    # Métricas separadas: anomalia x limpo
    logger.info("─" * 60)
    logger.info("MÉTRICAS POR TIPO")
    logger.info("─" * 60)
    anomalias = [r for r in resultados if r["tipo"] == "anomalia"]
    limpos = [r for r in resultados if r["tipo"] == "limpo"]

    if anomalias:
        recall = sum(1 for r in anomalias if r["passou"]) / len(anomalias)
        logger.info(
            "Recall em anomalias: %.0f%% (%d/%d) — o agente detectou os problemas?",
            recall * 100,
            sum(1 for r in anomalias if r["passou"]),
            len(anomalias),
        )
    if limpos:
        precision = sum(1 for r in limpos if r["passou"]) / len(limpos)
        logger.info(
            "Precision em limpos:  %.0f%% (%d/%d) — o agente NÃO inventou problemas?",
            precision * 100,
            sum(1 for r in limpos if r["passou"]),
            len(limpos),
        )

    # Tempo médio por caso — indica o custo operacional de cada avaliação.
    tempo_medio = sum(r["duracao_s"] for r in resultados) / total
    logger.info("Tempo médio por caso: %.2fs", tempo_medio)

    # Salvar log completo em JSON para análise posterior detalhada.
    with open("avaliacao_log.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    logger.info("Log completo salvo em: avaliacao_log.json")


if __name__ == "__main__":
    # Configuramos o basicConfig aqui, no ponto de entrada do script CLI.
    # Isso evita que a configuração do handler "vaze" para quem importar este módulo
    # como biblioteca — é uma boa prática do módulo logging do Python.
    # O formato exibe nível, timestamp, módulo e mensagem para facilitar a depuração.
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(asctime)s — %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    main()