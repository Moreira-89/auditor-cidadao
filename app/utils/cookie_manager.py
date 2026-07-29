"""
Geração e verificação de cookies assinados, usados para identificar um cliente
entre requisições sem precisar de login/senha (ex.: reconhecer o mesmo navegador
em requisições futuras).

COMO FUNCIONA A ASSINATURA:
O valor do cookie não é só um ID aleatório — é um ID + uma "assinatura" calculada
com uma chave secreta que só o servidor conhece (COOKIE_SECRET_KEY, em
app/core/dependencies.py). Isso significa que:
- O cliente PODE LER o valor do cookie (ele não é criptografado, só assinado).
- O cliente NÃO CONSEGUE forjar nem adulterar o valor, porque não tem a chave
  secreta para gerar uma assinatura válida. Qualquer alteração no cookie
  (mudar o ID, tentar se passar por outro usuário) invalida a assinatura.

Usamos `URLSafeTimedSerializer` da lib itsdangerous, que além de assinar já:
- Codifica o valor em formato seguro para URL/cookie (sem caracteres especiais).
- Embute um timestamp de criação, permitindo expirar cookies antigos automaticamente.
"""

import uuid

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.dependencies import COOKIE_SECRET_KEY
from app.core.logging_config import logger

# Tempo máximo de vida de um cookie, em segundos, antes de ser considerado expirado
# (30 dias). Depois desse prazo, verificar_cookie() trata o cookie como inválido
# mesmo que a assinatura em si ainda esteja correta.
IDADE_MAXIMA_COOKIE_SEGUNDOS = 30 * 24 * 60 * 60

# "salt" é um tempero extra somado à chave secreta na hora de assinar/verificar.
# Serve para que essa mesma COOKIE_SECRET_KEY, se um dia for reaproveitada para
# assinar outro tipo de token no projeto, gere assinaturas diferentes e incompatíveis
# entre os dois usos — evita que um token de um contexto seja aceito em outro.
_SALT_COOKIE_SESSAO = "cookie-sessao-auditor-cidadao"

# Serializer instanciado uma única vez no import do módulo e reutilizado por todas
# as chamadas — ele não guarda estado entre uma assinatura e outra, então é seguro
# compartilhar a mesma instância.
_serializer = URLSafeTimedSerializer(secret_key=COOKIE_SECRET_KEY, salt=_SALT_COOKIE_SESSAO)


def gerar_cookie_assinado() -> tuple[str, str]:
    """
    Cria um novo ID de sessão (UUID4) e devolve os dois valores que quem chama
    precisa, prontos para uso:
    - `id_puro`: o ID em si, no MESMO formato que `verificar_cookie` devolve nas
      requisições seguintes — usado direto como identificador (ex.: chave do
      rate limiter), sem precisar decodificar nada de volta.
    - `token_assinado`: o ID + assinatura, no formato que efetivamente vai como
      valor do cookie no navegador.
    """
    id_puro = str(uuid.uuid4())
    token_assinado = _serializer.dumps(id_puro)
    return id_puro, token_assinado


def verificar_cookie(valor: str) -> str | None:
    """
    Valida a assinatura de um cookie recebido do cliente e devolve o ID de sessão
    original se ele for autêntico e ainda não tiver expirado.

    Devolve None se o cookie for inválido por qualquer motivo (assinatura
    adulterada, formato corrompido, ou expirado) — nunca lança exceção, porque um
    cookie inválido deve ser tratado igual a "cliente sem cookie nenhum" (ex.:
    geramos um novo), não como um erro do servidor.
    """
    try:
        return _serializer.loads(valor, max_age=IDADE_MAXIMA_COOKIE_SEGUNDOS)
    except SignatureExpired:
        logger.info("Cookie de sessão expirado.")
        return None
    except BadSignature:
        # Cobre assinatura inválida, valor adulterado ou formato corrompido —
        # tudo que a lib classifica como "não é um cookie que nós emitimos".
        logger.warning("Cookie de sessão com assinatura inválida (possível adulteração).")
        return None
