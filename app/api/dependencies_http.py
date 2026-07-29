"""
Dependencies do FastAPI reutilizadas entre os endpoints HTTP (routers em app/api/).

Hoje contém a identificação de cliente via cookie assinado — usada como base para
o rate limiting (ver app/services/rate_limiter.py) em vez do IP, porque IP é um
identificador fraco: fácil de trocar (rede móvel, VPN, proxy) e fácil de
compartilhar sem querer (vários usuários atrás do mesmo NAT/Wi-Fi de escritório
caindo no mesmo limite). O cookie assinado (ver app/utils/cookie_manager.py)
identifica o NAVEGADOR do cliente de forma estável entre requisições, e como é
assinado com uma chave secreta do servidor, o cliente não consegue forjar nem
adulterar o valor para escapar do limite.
"""

from fastapi import Request, Response

from app.core.dependencies import AMBIENTE_PRODUCAO
from app.utils.cookie_manager import (
    IDADE_MAXIMA_COOKIE_SEGUNDOS,
    gerar_cookie_assinado,
    verificar_cookie,
)

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

        # httponly=True: o cookie fica invisível para JavaScript no navegador
        # (document.cookie não o enxerga), o que impede um ataque XSS de roubar
        # ou forjar o identificador de sessão — decisão já registrada no roadmap.
        #
        # secure=AMBIENTE_PRODUCAO: em produção (HTTPS, Railway) o navegador só
        # reenvia um cookie Secure em conexões HTTPS — é o comportamento que
        # queremos. Mas se deixássemos `secure=True` fixo, em desenvolvimento local
        # (uvicorn em http://localhost, sem TLS) o navegador aceitaria o cookie na
        # resposta e NUNCA o devolveria nas requisições seguintes — cada request
        # pareceria vir de um cliente novo, e o rate limiter nunca acumularia
        # contagem pra ninguém. Um bug silencioso: nenhum erro aparece, o rate
        # limit simplesmente nunca dispara. Por isso a flag varia com o ambiente.
        #
        # samesite="lax": bloqueia o cookie em requisições cross-site (CSRF),
        # mas ainda permite navegação normal (ex.: abrir um link da própria app).
        response.set_cookie(
            key=NOME_COOKIE_SESSAO,
            value=cookie_assinado,
            max_age=IDADE_MAXIMA_COOKIE_SEGUNDOS,
            httponly=True,
            secure=AMBIENTE_PRODUCAO,
            samesite="lax",
        )

        # Por padrão, se QUALQUER exceção (HTTPException ou erro de validação do
        # corpo da requisição) acontecer depois desse ponto — em outra dependency
        # OU dentro do próprio endpoint —, o FastAPI descarta este `response` e
        # monta uma resposta de erro do zero, perdendo o Set-Cookie que acabamos
        # de gravar. Um visitante novo cujo primeiro request falhasse por QUALQUER
        # motivo (ex.: upload de um PDF inválido) nunca receberia o cookie, e
        # seguiria sendo tratado como "visitante novo" a cada tentativa seguinte.
        #
        # Por isso guardamos uma cópia do header em request.state: o exception
        # handler central (ver main.py) sabe reaplicar esse cookie em QUALQUER
        # resposta de erro da requisição, não só na do próprio rate limiter.
        request.state.cookie_pendente = response.headers.get("set-cookie")

    return client_id
