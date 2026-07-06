"""
Integração manual com a API oficial de Consulta do PNCP (Portal Nacional de
Contratações Públicas), usada pela tool `buscar_contratos_fornecedor_pncp`
(ver app/services/tools.py) para verificar se um fornecedor específico já
venceu contratações anteriores junto a um órgão específico.

ATENÇÃO: esta tool está DESATIVADA hoje (ver a nota em app/services/tools.py). A varredura
de todas as modalidades de um órgão é lenta e esbarra no rate limit do PNCP, então o código
fica pronto para reativação futura — este módulo, portanto, não roda em produção no momento.

Feita à parte do MCP LiciNexus (@licinexusbr/mcp, ver app/services/lifespan.py)
porque este fluxo de "órgão + fornecedor -> histórico de contratos" não é
coberto pelas tools MCP selecionadas hoje. Validado manualmente, endpoint a
endpoint, em testes_locais/test_getcontratos_pncp.ipynb antes de virar código
de produção.

Fluxo (3 chamadas encadeadas):
1. GET /contratacoes/publicacao      -> lista as compras do órgão no ano.
2. GET /orgaos/{cnpj}/compras/.../itens          -> lista os itens de cada compra.
3. GET /orgaos/{cnpj}/compras/.../itens/{n}/resultados -> resultado de cada item.
Depois filtra client-side por resultado["niFornecedor"] == cnpj_fornecedor.

NOTA SOBRE AS BASES DE URL: a API do PNCP é dividida em duas aplicações com
bases diferentes — confirmado lendo o OpenAPI (/v3/api-docs) de cada uma:
- /api/consulta -> endpoints de busca/pesquisa (contratacoes/publicacao).
- /api/pncp     -> endpoints por órgão (orgaos/{cnpj}/compras/.../itens e
  .../resultados). Nenhuma das duas exige autenticação para GET.
"""

import asyncio
import re
import time

import httpx

BASE_CONSULTA = "https://pncp.gov.br/api/consulta/v1"
BASE_PNCP = "https://pncp.gov.br/api/pncp/v1"

# Timeout maior que o padrão do projeto (5s, ver consulta_receita_federal.py) porque
# esta consulta pode encadear centenas de requests para órgãos com muitas compras no
# ano, e o PNCP ocasionalmente demora a responder sob esse tipo de carga sustentada.
TIMEOUT = httpx.Timeout(30.0)

# Cache das modalidades ativas — a tabela de domínio muda raramente e não vale a
# pena buscá-la de novo a cada chamada da tool dentro do mesmo processo do servidor.
_MODALIDADES_CACHE: list[int] | None = None

# O PNCP aplica rate limit por IP no nível de WAF ("Limite de Requisições Excedido",
# sem header Retry-After) e, sob carga sustentada por vários minutos, também derruba
# conexões esporadicamente (ConnectError/RemoteProtocolError). Ambos os comportamentos
# foram reproduzidos e confirmados manualmente durante a validação desta integração:
# um burst de ~19 requests simultâneos (uma por modalidade) já é suficiente para
# disparar um bloqueio temporário de alguns minutos. Por isso o espaçamento mínimo
# entre requests é conservador (2s) e qualquer erro de conexão é tratado como
# transiente (retry com backoff), não como falha definitiva.
_INTERVALO_MINIMO_SEGUNDOS = 2.0
_MAX_TENTATIVAS = 5
_proximo_request_liberado_em = 0.0
_lock_intervalo = asyncio.Lock()


async def _respeitar_intervalo_minimo() -> None:
    """Serializa o disparo dos requests para respeitar um intervalo mínimo global entre eles."""
    global _proximo_request_liberado_em
    async with _lock_intervalo:
        agora = time.monotonic()
        espera = _proximo_request_liberado_em - agora
        if espera > 0:
            await asyncio.sleep(espera)
        _proximo_request_liberado_em = max(agora, _proximo_request_liberado_em) + _INTERVALO_MINIMO_SEGUNDOS


async def _get_pncp(client: httpx.AsyncClient, url: str, params: dict | None = None) -> httpx.Response:
    """GET com espaçamento mínimo entre requests e retry (backoff exponencial) em 429/erro de conexão."""
    for tentativa in range(_MAX_TENTATIVAS):
        await _respeitar_intervalo_minimo()
        try:
            response = await client.get(url, params=params)
        except httpx.RequestError:
            # Erros de conexão pontuais (não só timeout) acontecem em lotes longos de
            # requests — sem esse retry, um único blip derruba o asyncio.gather inteiro.
            if tentativa == _MAX_TENTATIVAS - 1:
                raise
            await asyncio.sleep(5 * 2**tentativa)
            continue

        if response.status_code != 429:
            return response
        if tentativa == _MAX_TENTATIVAS - 1:
            return response
        espera = float(response.headers.get("Retry-After", 5 * 2**tentativa))
        await asyncio.sleep(espera)


async def _listar_modalidades_ativas(client: httpx.AsyncClient) -> list[int]:
    """
    Busca a tabela de domínio de modalidades de contratação e retorna os IDs ativos.

    Necessário porque /contratacoes/publicacao exige `codigoModalidadeContratacao`
    como parâmetro obrigatório — a API não aceita "todas as modalidades" num único
    request, então é preciso varrer uma por uma. Buscado ao vivo em vez de fixar os
    IDs no código porque a tabela de domínio pode ganhar/perder modalidades com o
    tempo (ex.: hoje são 19, incluindo modalidades internacionais recentes).
    """
    global _MODALIDADES_CACHE
    if _MODALIDADES_CACHE is not None:
        return _MODALIDADES_CACHE

    response = await _get_pncp(client, f"{BASE_PNCP}/modalidades")
    response.raise_for_status()
    dados = response.json()

    _MODALIDADES_CACHE = [m["id"] for m in dados if m.get("statusAtivo")]
    return _MODALIDADES_CACHE


async def _listar_compras_por_modalidade(
    client: httpx.AsyncClient, cnpj_orgao: str, ano: int, codigo_modalidade: int
) -> list[dict]:
    """Pagina /contratacoes/publicacao para uma única modalidade e retorna todas as compras."""
    compras: list[dict] = []
    pagina = 1

    while True:
        params = {
            "cnpj": cnpj_orgao,
            "dataInicial": f"{ano}0101",
            "dataFinal": f"{ano}1231",
            "codigoModalidadeContratacao": codigo_modalidade,
            "pagina": pagina,
            "tamanhoPagina": 50,
        }
        response = await _get_pncp(client, f"{BASE_CONSULTA}/contratacoes/publicacao", params=params)

        # 204 = sem resultados para esta modalidade/página, não é erro
        if response.status_code == 204:
            break
        response.raise_for_status()

        corpo = response.json()
        compras.extend(corpo.get("data", []))

        if pagina >= corpo.get("totalPaginas", 1):
            break
        pagina += 1

    return compras


async def _listar_compras_orgao(client: httpx.AsyncClient, cnpj_orgao: str, ano: int) -> list[dict]:
    """
    Chamada 1: lista todas as compras publicadas por um órgão em um ano, varrendo
    todas as modalidades de contratação em paralelo (a API exige uma modalidade
    por request).
    """
    modalidades = await _listar_modalidades_ativas(client)

    resultados_por_modalidade = await asyncio.gather(
        *(
            _listar_compras_por_modalidade(client, cnpj_orgao, ano, codigo)
            for codigo in modalidades
        )
    )

    return [compra for lote in resultados_por_modalidade for compra in lote]


async def _listar_itens_compra(
    client: httpx.AsyncClient, cnpj_orgao: str, ano: int, sequencial: int
) -> list[dict]:
    """Chamada 2: lista os itens de uma compra específica."""
    response = await _get_pncp(
        client, f"{BASE_PNCP}/orgaos/{cnpj_orgao}/compras/{ano}/{sequencial}/itens"
    )
    if response.status_code == 204:
        return []
    response.raise_for_status()
    return response.json()


async def _listar_resultados_item(
    client: httpx.AsyncClient, cnpj_orgao: str, ano: int, sequencial: int, numero_item: int
) -> list[dict]:
    """Chamada 3: lista os resultados (vencedores) de um item específico."""
    response = await _get_pncp(
        client,
        f"{BASE_PNCP}/orgaos/{cnpj_orgao}/compras/{ano}/{sequencial}"
        f"/itens/{numero_item}/resultados",
    )
    if response.status_code == 204:
        return []
    response.raise_for_status()
    return response.json()


async def buscar_contratos_por_fornecedor(
    cnpj_orgao_limpo: str, cnpj_fornecedor_limpo: str, ano: int
) -> list[dict]:
    """
    Encadeia as 3 chamadas do PNCP e filtra client-side pelo fornecedor.

    Recebe os CNPJs já limpos (só dígitos) e validados — validação de formato
    é responsabilidade do chamador (ver buscar_contratos_fornecedor_pncp em
    app/services/tools.py). Levanta as exceções nativas do httpx em caso de
    falha; o chamador decide como traduzir cada uma em erro para o LLM.

    Retorna uma lista de dicionários — um por item vencido pelo fornecedor —
    cada um com "numeroControlePNCP", "objeto", "valor", "situacao" e
    "dataResultado". Lista vazia significa que a consulta funcionou, mas o
    fornecedor não venceu nenhum item desse órgão naquele ano.
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Chamada 1: todas as compras do órgão no ano
        compras = await _listar_compras_orgao(client, cnpj_orgao_limpo, ano)

        # Chamada 2: itens de cada compra, em paralelo — a concorrência real de
        # requests HTTP já é limitada dentro de _get_pncp() via _lock_intervalo,
        # então não é preciso um semáforo adicional aqui
        listas_de_itens = await asyncio.gather(
            *(
                _listar_itens_compra(client, cnpj_orgao_limpo, ano, compra["sequencialCompra"])
                for compra in compras
            )
        )

        # zip() pareia cada compra com sua respectiva lista de itens pela posição:
        # asyncio.gather garante que a ordem dos resultados é a mesma ordem das
        # coroutines de entrada, então listas_de_itens[i] é sempre o resultado de
        # compras[i]. Só vale a pena buscar resultado de itens que já têm resultado
        # registrado (temResultado=True) — poupa uma chamada 3 desnecessária.
        itens_com_resultado = [
            (compra, item)
            for compra, itens in zip(compras, listas_de_itens)
            for item in itens
            if item.get("temResultado")
        ]

        # Chamada 3: resultado de cada item com resultado, em paralelo
        listas_de_resultados = await asyncio.gather(
            *(
                _listar_resultados_item(
                    client, cnpj_orgao_limpo, ano, compra["sequencialCompra"], item["numeroItem"]
                )
                for compra, item in itens_com_resultado
            )
        )

    # Filtro client-side: o campo do fornecedor vencedor na API se chama "niFornecedor"
    # (Número de Identificação — aceita CNPJ ou CPF), não "cnpjFornecedor". zip() aqui
    # pareia cada (compra, item) com sua respectiva lista de resultados, pelo mesmo
    # motivo do zip acima.
    return [
        {
            "numeroControlePNCP": resultado.get("numeroControlePNCPCompra"),
            "objeto": compra.get("objetoCompra"),
            "valor": resultado.get("valorTotalHomologado"),
            "situacao": resultado.get("situacaoCompraItemResultadoNome"),
            "dataResultado": resultado.get("dataResultado"),
        }
        for (compra, _item), resultados in zip(itens_com_resultado, listas_de_resultados)
        for resultado in resultados
        if re.sub(r"[./-]", "", resultado.get("niFornecedor", "")) == cnpj_fornecedor_limpo
    ]
