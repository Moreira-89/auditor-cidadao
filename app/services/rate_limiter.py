"""
Rate limiting (limitação de taxa) por cliente, usando Redis.

Protege endpoints caros da API (upload de edital, conversa com o agente — ambos
disparam chamadas a LLM, Pinecone e serviços externos) contra abuso: um mesmo
cliente não pode fazer mais que N requisições dentro de uma janela de tempo. Sem
isso, um cliente malicioso (ou um bug no frontend em loop) poderia gerar custo de
LLM sem limite algum.

COMO FUNCIONA A CONTAGEM (o script Lua):
A forma "ingênua" de fazer isso seria em Python: ler o contador (GET), checar se já
passou do limite e, se não, incrementar (INCR). O problema é que, com duas
requisições do MESMO cliente chegando ao mesmo tempo, as duas podem executar o GET
antes de qualquer uma delas incrementar — as duas "veem" o contador abaixo do
limite e as duas passam, mesmo que juntas estourem a cota (condição de corrida).

A solução é rodar a checagem + incremento como UM ÚNICO comando atômico dentro do
próprio Redis, via um script Lua. O Redis processa comandos um de cada vez (é
single-threaded para execução de comandos), então enquanto o script está rodando
nenhuma outra operação consegue "entrar no meio" — a checagem e o incremento
acontecem como se fossem uma coisa só.
"""

from fastapi import Depends, HTTPException
from redis.asyncio import Redis
from redis.commands.core import AsyncScript

from app.api.dependencies_http import get_client_id
from app.core.logging_config import logger

# Texto do script Lua — não é código Python, é interpretado pelo próprio Redis.
#
# KEYS[1] = chave do contador desse cliente nessa rota (ex.: "upload:<client_id>",
#           onde client_id vem do cookie assinado, ver app/api/dependencies_http.py)
# ARGV[1] = limite máximo de requisições permitidas na janela
# ARGV[2] = duração da janela, em segundos
#
# Lógica:
# 1. Lê o valor atual do contador (pode não existir ainda — primeira requisição).
# 2. Se já existe E já atingiu o limite, BLOQUEIA (retorna -1) sem incrementar —
#    assim o contador não continua subindo indefinidamente enquanto o cliente
#    insiste dentro da mesma janela.
# 3. Caso contrário, incrementa o contador (INCR cria a chave com valor 1 se ela
#    não existir) e, SÓ na primeira requisição da janela (count == 1), define o
#    TTL. O Redis apaga a chave sozinho quando o TTL expira, o que reinicia a
#    contagem — não precisamos limpar nada manualmente.
# 4. Retorna o valor do contador após o incremento (permitido), para o Python
#    poder logar quanto da cota já foi consumido sem precisar de um segundo
#    round-trip ao Redis (GET) só para isso.
_SCRIPT_RATE_LIMIT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])

local current = redis.call('GET', key)

if current and tonumber(current) >= limit then
    return -1
else
    local count = redis.call('INCR', key)
    if count == 1 then
        redis.call('EXPIRE', key, window)
    end
    return count
end
"""

# Singleton do script Lua já registrado — mesmo padrão usado em
# app/services/build_graph.py (_graph_instance/get_graph): uma variável módulo-level,
# preenchida uma única vez no startup (inicializar_rate_limiter, chamado pelo
# lifespan) e lida por toda a aplicação depois disso. Não guardamos o client Redis
# em si à parte: o script já carrega a conexão internamente, e nada mais aqui
# precisa do client puro — só do script.
_script_instance: AsyncScript | None = None


def _formatar_tempo_restante(segundos: int) -> str:
    """Converte segundos restantes em algo lido de cabeça — "23 horas e 12 minutos"
    em vez do bruto em segundos. Composto (horas+minutos / minutos+segundos) porque
    "restam X horas" sozinho é vago demais para quem está tentando decidir se espera
    ou volta depois."""
    segundos = max(segundos, 0)
    horas, resto = divmod(segundos, 3600)
    minutos, segs = divmod(resto, 60)

    if horas > 0:
        partes = [f"{horas} hora" + ("" if horas == 1 else "s")]
        if minutos > 0:
            partes.append(f"{minutos} minuto" + ("" if minutos == 1 else "s"))
        return " e ".join(partes)
    if minutos > 0:
        partes = [f"{minutos} minuto" + ("" if minutos == 1 else "s")]
        if segs > 0:
            partes.append(f"{segs} segundo" + ("" if segs == 1 else "s"))
        return " e ".join(partes)
    return f"{segs} segundo" + ("" if segs == 1 else "s")


def inicializar_rate_limiter(redis_client: Redis) -> None:
    """
    Chamado uma única vez pelo lifespan, no startup do servidor: registra no
    client Redis recebido o script Lua de rate limit.

    `register_script` não executa o script — ele só cria um objeto Python que sabe
    ENVIAR esse script para o Redis. O Redis então guarda o script em cache (pelo
    hash do texto) e, nas chamadas seguintes, a lib reenvia apenas o hash (EVALSHA)
    em vez do texto completo do script — mais rápido, mas transparente para quem usa.
    """
    global _script_instance
    _script_instance = redis_client.register_script(_SCRIPT_RATE_LIMIT)


def get_rate_limiter() -> AsyncScript:
    """Retorna o script Lua já registrado. Lança RuntimeError se o lifespan ainda não inicializou."""
    if _script_instance is None:
        raise RuntimeError(
            "Rate limiter não inicializado. O lifespan do FastAPI foi executado?"
        )
    return _script_instance


class RateLimiter:
    """
    Fábrica de dependências do FastAPI: cada endpoint que precisa de um limite
    diferente cria a SUA PRÓPRIA instância desta classe, por isso é uma classe (com
    __call__) e não uma função solta — a função solta não teria como "lembrar" de
    qual limite/janela/prefixo usar para cada rota.

    Uso típico:

        limitar_upload = RateLimiter(
            limit=5, window_seconds=60, prefixo="upload", descricao="upload"
        )

        @router.post("/", dependencies=[Depends(limitar_upload)])
        async def upload_edital(...): ...

    O FastAPI chama a instância como se fosse uma função a cada requisição — daí o
    `__call__` assíncrono. O `client_id: str = Depends(get_client_id)` no parâmetro
    é uma SUB-dependency: o FastAPI resolve `get_client_id` primeiro (lendo/gravando
    o cookie assinado do cliente, ver app/api/dependencies_http.py) e só então chama
    `__call__` com o resultado já pronto.

    Por que cookie e não IP: IP é um identificador fraco para rate limit — é fácil
    de trocar (rede móvel, VPN, outro Wi-Fi) e fácil de compartilhar sem querer
    (vários usuários atrás do mesmo NAT caem no mesmo limite). O cookie assinado
    identifica o NAVEGADOR do cliente de forma estável, e como é assinado com uma
    chave secreta do servidor, o cliente não consegue forjar nem adulterar o valor
    para escapar do limite.
    """

    def __init__(
        self, limit: int, window_seconds: int, prefixo: str, descricao: str
    ) -> None:
        # Número máximo de requisições permitidas dentro da janela
        self.limit = limit
        # Duração da janela de tempo, em segundos
        self.window_seconds = window_seconds
        # Identifica QUAL rota está sendo limitada — evita que o consumo de cota em
        # um endpoint (ex.: upload) "vaze" para o limite de outro (ex.: pergunta)
        self.prefixo = prefixo
        # Nome amigável usado na mensagem de erro ao usuário (ex.: "upload de editais",
        # "perguntas ao auditor") — sem isso a mensagem teria que ser genérica demais
        # para servir aos dois endpoints que usam esta classe.
        self.descricao = descricao

    async def __call__(self, client_id: str = Depends(get_client_id)) -> None:
        """Verifica se o cliente da requisição atual ainda tem cota disponível;
        se não tiver, interrompe a requisição com HTTP 429 antes de o endpoint rodar."""
        chave_redis = f"{self.prefixo}:{client_id}"

        script = get_rate_limiter()
        # keys=[...] vira KEYS no Lua, args=[...] vira ARGV — a ordem de args deve
        # bater exatamente com a ordem em que o script lê ARGV[1] e ARGV[2]
        contador = await script(keys=[chave_redis], args=[self.limit, self.window_seconds])

        if contador == -1:
            logger.warning(
                "Rate limit excedido | prefixo=%s | client_id=%s | limite=%d req / %ds",
                self.prefixo,
                client_id,
                self.limit,
                self.window_seconds,
            )
            # TTL da própria chave = tempo real até a cota resetar (a janela "desliza"
            # a partir da primeira requisição do cliente, não tem hora fixa do dia) —
            # por isso não dá pra usar window_seconds direto, precisa perguntar ao Redis.
            segundos_restantes = await script.registered_client.ttl(chave_redis)

            # Se get_client_id acabou de emitir um cookie novo pra esse visitante,
            # levantar essa exceção normalmente o perderia (comportamento padrão
            # do FastAPI ao descartar o Response modificado por dependencies
            # anteriores). Não precisamos tratar isso aqui: o exception handler
            # central (ver _reaplicar_cookie_pendente em main.py) já cobre TODA
            # exceção da requisição, não só esta.
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Você excedeu o limite de {self.descricao}. Volte em "
                    f"{_formatar_tempo_restante(segundos_restantes)} para tentar novamente."
                ),
            )
        else:
            # Log de consumo de cota (não de erro) — sem isso, a única evidência de
            # que o rate limiter está ativo era o warning de bloqueio, que só
            # aparece quando alguém já estourou o limite.
            logger.info(
                "Cota consumida | prefixo=%s | client_id=%s | uso=%d/%d req (janela %ds)",
                self.prefixo,
                client_id,
                contador,
                self.limit,
                self.window_seconds,
            )
