from app.api.cookies import (
    IDADE_MAXIMA_COOKIE_SEGUNDOS,
    gerar_cookie_assinado,
    verificar_cookie,
)
from app.config.settings import AMBIENTE_PRODUCAO
from fastapi import Request, Response

# Nome do cookie salvo no navegador do cliente. Prefixo "auditor_" evita colisão
# com cookies de outras aplicações no mesmo domínio.
NOME_COOKIE_SESSAO = "auditor_client_id"


async def get_client_id(request: Request, response: Response) -> str:
    """
    Identifica o cliente (navegador) que fez a requisição, usando um cookie
    assinado e httpOnly como identificador estável entre requisições.

    Fluxo:
    1. Tenta ler o cookie `auditor_client_id` que o navegador já mandou.
    2. Se existir e a assinatura for válida (verificar_cookie), reaproveita o
       mesmo ID — o cliente já tinha "se apresentado" numa requisição anterior.
    3. Se não existir, ou a assinatura for inválida/adulterada, gera um ID novo
       (gerar_cookie_assinado) e grava no cookie de resposta, para que as
       PRÓXIMAS requisições desse navegador já cheguem com o cookie certo.

    Em ambos os casos, devolve o ID — pronto para ser usado, por exemplo, como
    chave do rate limiter.
    """
    cookie_recebido = request.cookies.get(NOME_COOKIE_SESSAO)

    # cookie_recebido pode ser None (nunca visitou antes) OU uma string inválida
    # (adulterada, expirada, ou assinada com uma chave antiga do servidor) —
    # verificar_cookie() trata os dois casos e devolve None sem lançar exceção
    client_id = verificar_cookie(cookie_recebido) if cookie_recebido else None

    if client_id is None:
        # Cliente novo (ou cookie inválido): gerar_cookie_assinado() já devolve os
        # dois valores prontos — o ID puro (mesmo formato que verificar_cookie
        # devolveria numa próxima requisição, usado direto como client_id) e o
        # token assinado (o que efetivamente vai gravado no cookie). Sem essa
        # separação, seria preciso assinar e imediatamente desassinar o mesmo
        # valor só para recuperar o que já se tinha em mãos.
        client_id, cookie_assinado = gerar_cookie_assinado()

        # Por que cada flag varia com o ambiente: ver docs/arquitetura/visao_geral.md
        # ("Identificação do cliente: cookie assinado e CORS cross-site").
        response.set_cookie(
            key=NOME_COOKIE_SESSAO,
            value=cookie_assinado,
            max_age=IDADE_MAXIMA_COOKIE_SEGUNDOS,
            httponly=True,
            secure=AMBIENTE_PRODUCAO,
            samesite="none" if AMBIENTE_PRODUCAO else "lax",
        )

        # Guardado para o exception handler central reaplicar em respostas de
        # erro (ver "Cookie perdido em resposta de erro" em
        # docs/arquitetura/visao_geral.md e _reaplicar_cookie_pendente em main.py).
        request.state.cookie_pendente = response.headers.get("set-cookie")

    return client_id
