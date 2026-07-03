import json
from typing import Any, Optional, Union, get_args, get_origin

from langchain_core.tools import StructuredTool
from pydantic import create_model
from pydantic.fields import FieldInfo

# =============================================================================
# CONTEXTO GERAL DO MÓDULO
#
# Provedores LLM exigem que cada tool tenha um schema Python estrito
# (ex: campo "idade" deve ser int). O problema: LLMs frequentemente enviam
# os valores como strings ("42" em vez de 42), causando erro de validação
# do Pydantic antes mesmo de chamar o MCP server.
#
# Este módulo resolve isso em duas etapas:
#   1. Torna os tipos do schema permissivos (int → Union[int, str])
#      para que o LLM passe na validação do Pydantic.
#   2. Converte os valores de volta ao tipo correto (str → int)
#      antes de enviá-los ao MCP server, que valida via Zod (Node.js).
# =============================================================================


def _tornar_tipo_permissivo(annotation: Any) -> Any:
    """Transforma um tipo estrito Python em permissivo, aceitando str como alternativa."""

    # int e float são os tipos que LLMs mais quebram — mandam "42" em vez de 42
    if annotation is int:
        return Union[int, str]
    if annotation is float:
        return Union[float, str]

    # get_origin revela o tipo "base" de um genérico: get_origin(Optional[int]) → Union
    origin = get_origin(annotation)
    # get_args extrai os parâmetros internos: get_args(Optional[int]) → (int, NoneType)
    args = get_args(annotation)

    # Detecta Optional[X], que internamente é Union[X, None]
    if origin is Union and type(None) in args:
        # Filtra o NoneType para obter apenas os tipos reais dentro do Optional
        tipos_internos = [a for a in args if a is not type(None)]
        if tipos_internos:
            # Aplica a permissividade recursivamente no tipo interno
            # Ex: Optional[int] → Optional[Union[int, str]]
            interno_permissivo = _tornar_tipo_permissivo(tipos_internos[0])
            return Optional[interno_permissivo]

    # Para listas, aceita também string para cobrir o caso em que o LLM manda "[1,2,3]" como texto
    if origin is list:
        return Union[annotation, str]

    # Tipos desconhecidos (bool, dict, str) são retornados sem modificação
    return annotation


def _tipo_python_de_json_schema(tipo_json: str) -> Any:
    """Converte um tipo do JSON Schema (string) para o tipo Python permissivo equivalente."""

    # Mapeamento direto de tipos JSON Schema → tipos Python já permissivos.
    # integer e number já viram Union com str para absorver strings que o LLM envia.
    # array também aceita str pois o LLM pode mandar '[1,2,3]' como texto.
    mapa = {
        "integer": Union[int, str],
        "number": Union[float, str],
        "array": Union[list, str],
        "string": str,
        "boolean": bool,
        "object": dict,
    }
    # Retorna Any para tipos não mapeados, nunca falha com KeyError
    return mapa.get(tipo_json, Any)


def _model_de_json_schema(schema_dict: dict, nome_base: str) -> type:
    """Constrói um modelo Pydantic permissivo a partir de um JSON Schema dict."""

    # Lê a lista de propriedades do schema (cada campo da tool)
    properties = schema_dict.get("properties", {})
    # "required" lista os campos obrigatórios — os ausentes são opcionais (default None)
    required = set(schema_dict.get("required", []))
    campos: dict[str, Any] = {}

    for nome, prop in properties.items():
        # Converte o tipo JSON Schema do campo para o tipo Python permissivo
        tipo_python = _tipo_python_de_json_schema(prop.get("type", "string"))
        desc = prop.get("description", "")

        if nome in required:
            # Campo obrigatório: sem default, Pydantic exige que seja enviado
            campos[nome] = (tipo_python, FieldInfo(description=desc))
        else:
            # Campo opcional: envolve em Optional e define default=None
            campos[nome] = (
                Optional[tipo_python],
                FieldInfo(default=None, description=desc),
            )

    # Cria dinamicamente uma classe Pydantic com os campos construídos acima.
    # O sufixo "MCPCompat" sinaliza que este modelo foi tornado permissivo para
    # passar na validação do provedor LLM, e não é o schema original do MCP server.
    return create_model(f"{nome_base}MCPCompat", **campos)


def _make_coercion_coroutine(original_coroutine, schema_dict: dict):
    """
    Envolve a coroutine original da tool MCP com uma camada de coerção de tipos.

    Por que isso é necessário — a validação acontece em duas camadas diferentes,
    e este arquivo cobre as duas:
    1. O LLM (via LangChain/Pydantic) valida o schema Python já tornado permissivo
       por `_tornar_tipo_permissivo`/`_model_de_json_schema` — por isso "42" passa
       como string sem erro nessa etapa.
    2. O MCP server (Node.js, validado via Zod) valida os *valores reais* recebidos
       e rejeita "42" (string) onde espera 42 (número). É aqui que essa segunda
       camada de validação seria quebrada se não convertêssemos antes de enviar.

    Esta função resolve a camada 2: converte cada valor para o tipo Python nativo
    esperado pelo schema original (não o permissivo) logo antes de chamar o MCP.

    Conversões aplicadas:
    - "1" (str) → 1 (int) para campos integer
    - "1.5" (str) → 1.5 (float) para campos number
    - "true"/"sim" (str) → True (bool) para campos boolean
    - '{"k":"v"}' (str) → {"k": "v"} (dict) para campos object
    - "[1,2]" (str) → [1, 2] (list) para campos array
    - None / "null" → removido do dict de args (não envia campo nulo)
    """
    # Extrai as definições de cada propriedade para consultar tipo e tipo do item de array
    properties = schema_dict.get("properties", {})

    async def coroutine_com_coercao(**kwargs):
        args_convertidos = {}

        for chave, valor in kwargs.items():
            # Descarta campos nulos: o MCP server rejeita null em campos opcionais
            if valor is None or valor == "null":
                continue

            # Descobre o tipo esperado pelo schema para este campo
            tipo_esperado = properties.get(chave, {}).get("type", "string")
            # Para arrays, também precisa saber o tipo de cada item interno
            tipo_item = properties.get(chave, {}).get("items", {}).get("type", "string")

            if tipo_esperado == "integer" and isinstance(valor, str):
                # LLM mandou "42" em vez de 42 — converte para int
                try:
                    args_convertidos[chave] = int(valor)
                except ValueError:
                    # Se falhar (ex: "abc"), mantém como string e deixa o MCP rejeitar
                    args_convertidos[chave] = valor

            elif tipo_esperado == "number" and isinstance(valor, str):
                # LLM mandou "3.14" em vez de 3.14 — converte para float
                try:
                    args_convertidos[chave] = float(valor)
                except ValueError:
                    args_convertidos[chave] = valor

            elif tipo_esperado == "boolean" and isinstance(valor, str):
                # LLM pode mandar "true", "True", "1", "sim" — normaliza para bool Python
                args_convertidos[chave] = valor.lower() in ("true", "1", "yes", "sim")

            elif tipo_esperado == "object" and isinstance(valor, str):
                # LLM mandou o objeto inteiro como string JSON — desserializa para dict
                try:
                    args_convertidos[chave] = json.loads(valor)
                except (json.JSONDecodeError, ValueError):
                    # Não era JSON válido — mantém como string
                    args_convertidos[chave] = valor

            elif tipo_esperado == "array" and isinstance(valor, str):
                # LLM pode mandar o array inteiro como string JSON: '[6, 8, 9]'
                # Precisamos parsear antes de embrulhar
                try:
                    parsed = json.loads(valor)
                except (json.JSONDecodeError, ValueError):
                    parsed = valor  # não é JSON, trata como elemento único

                if isinstance(parsed, list):
                    # Converte cada item interno para o tipo correto
                    if tipo_item in ("integer", "number"):
                        convertidos = []
                        for item in parsed:
                            if isinstance(item, str):
                                # Item dentro da lista também pode vir como string
                                try:
                                    convertidos.append(
                                        int(item)
                                        if tipo_item == "integer"
                                        else float(item)
                                    )
                                except ValueError:
                                    convertidos.append(item)
                            else:
                                convertidos.append(item)  # já é número, mantém
                        args_convertidos[chave] = convertidos
                    else:
                        # Array de strings ou outros tipos — usa diretamente
                        args_convertidos[chave] = parsed
                else:
                    # Era um valor escalar em formato JSON (ex: "8" → 8)
                    # Empacota como lista de um elemento, convertendo o tipo se necessário
                    if tipo_item in ("integer", "number"):
                        try:
                            args_convertidos[chave] = [
                                int(parsed) if tipo_item == "integer" else float(parsed)
                            ]
                        except (ValueError, TypeError):
                            args_convertidos[chave] = [parsed]
                    else:
                        args_convertidos[chave] = [parsed]

            elif tipo_esperado == "array" and isinstance(valor, list):
                # Array chegou como lista Python, mas os itens ainda podem ser strings
                if tipo_item in ("integer", "number"):
                    convertidos = []
                    for item in valor:
                        if isinstance(item, str):
                            try:
                                convertidos.append(
                                    int(item) if tipo_item == "integer" else float(item)
                                )
                            except ValueError:
                                convertidos.append(item)
                        else:
                            convertidos.append(item)
                    args_convertidos[chave] = convertidos
                else:
                    # Itens já são do tipo correto — passa direto
                    args_convertidos[chave] = valor

            else:
                # Tipo já correto ou sem conversão necessária — passa sem alteração
                args_convertidos[chave] = valor

        # Chama o MCP server com os valores já no tipo correto
        try:
            resultado = await original_coroutine(**args_convertidos)
        except Exception as e:
            resultado = f"Erro ao executar a ferramenta: {str(e)}"
            
        # Limita o tamanho do retorno de cada tool para controlar custo e qualidade.
        # Com múltiplas chamadas MCP por turno, retornos volumosos acumulam tokens
        # rapidamente no contexto — aumentando custo e podendo degradar a atenção do modelo.
        # 4000 chars (~1000 tokens) é suficiente para análise sem desperdiçar contexto.
        MAX_CHARS = 4000
        if isinstance(resultado, str) and len(resultado) > MAX_CHARS:
            resultado = (
                resultado[:MAX_CHARS]
                + "\n\n[... resultado truncado para caber no contexto ...]"
            )

        return resultado

    return coroutine_com_coercao


def patch_mcp_tools(tools: list) -> list:
    """Reconstrói os schemas das MCP tools tornando tipos estritos permissivos para qualquer provedor LLM."""

    resultado = []

    for tool in tools:
        # Tenta acessar o schema de argumentos da tool (pode ser Pydantic ou dict)
        schema_original = getattr(tool, "args_schema", None)

        # Se a tool não tem schema, não há nada para corrigir — mantém como está
        if schema_original is None:
            resultado.append(tool)
            continue

        # --- Caso 1: schema é um dict (JSON Schema puro) ---
        # Algumas tools MCP retornam o schema diretamente como dicionário,
        # sem transformar em classe Pydantic. Usamos _model_de_json_schema para criar o modelo.
        if isinstance(schema_original, dict):
            NovoSchema = _model_de_json_schema(schema_original, tool.name)
            schema_para_coercao = schema_original  # já é dict, usa direto na coerção

        # --- Caso 2: schema é um modelo Pydantic ---
        # Tools geradas pelo LangChain usam BaseModel como schema.
        # Iteramos pelos campos e tornamos cada tipo permissivo individualmente.
        elif hasattr(schema_original, "model_fields"):
            novos_campos = {}
            for nome_campo, field_info in schema_original.model_fields.items():
                # Torna o tipo do campo permissivo (ex: int → Union[int, str])
                novo_tipo = _tornar_tipo_permissivo(field_info.annotation)
                novos_campos[nome_campo] = (
                    novo_tipo,
                    FieldInfo(
                        default=field_info.default,
                        description=field_info.description,
                    ),
                )
            # Cria um novo modelo Pydantic com os campos permissivos
            NovoSchema = create_model(
                f"{schema_original.__name__}MCPCompat", **novos_campos
            )
            # Converte o modelo Pydantic para dict antes de passar para coerção
            # pois _make_coercion_coroutine espera um JSON Schema dict
            schema_para_coercao = schema_original.model_json_schema()

        # --- Caso 3: tipo desconhecido — mantém sem alteração ---
        else:
            resultado.append(tool)
            continue

        # Toda tool MCP deve ter uma coroutine (é sempre chamada de forma assíncrona)
        coroutine_original = getattr(tool, "coroutine", None)
        if coroutine_original is None:
            raise ValueError(
                f"Tool MCP '{tool.name}' não possui atributo 'coroutine' "
                "e não pode ser usada de forma assíncrona. "
                "Verifique se o MCP server retornou a tool corretamente."
            )

        # Reconstrói a tool com o novo schema permissivo e a coroutine com coerção de tipos
        # Todos os outros atributos (name, description, func, return_direct) são preservados
        tool_corrigida = StructuredTool(
            name=tool.name,
            description=tool.description,
            args_schema=NovoSchema,
            coroutine=_make_coercion_coroutine(
                coroutine_original,
                schema_para_coercao,
            ),
            func=getattr(tool, "func", None),
            return_direct=getattr(tool, "return_direct", False),
        )
        resultado.append(tool_corrigida)

    return resultado
