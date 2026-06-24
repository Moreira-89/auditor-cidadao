from typing import Any, Union, Optional, get_origin, get_args

from pydantic import create_model
from pydantic.fields import FieldInfo
from langchain_core.tools import StructuredTool


def _tornar_tipo_permissivo(annotation: Any) -> Any:
    if annotation is int:
        return Union[int, str]
    if annotation is float:
        return Union[float, str]

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is Union and type(None) in args:
        tipos_internos = [a for a in args if a is not type(None)]
        if tipos_internos:
            interno_permissivo = _tornar_tipo_permissivo(tipos_internos[0])
            return Optional[interno_permissivo]

    if origin is list:
        return Union[annotation, str]

    return annotation


def _tipo_python_de_json_schema(tipo_json: str) -> Any:
    """
    Converte tipo primitivo do JSON Schema para tipo Python permissivo.
    Já aplica permissividade diretamente para tipos problemáticos com Groq.
    """
    mapa = {
        "integer": Union[int, str],
        "number":  Union[float, str],
        "array":   Union[list, str],
        "string":  str,
        "boolean": bool,
        "object":  dict,
    }
    return mapa.get(tipo_json, Any)


def _model_de_json_schema(schema_dict: dict, nome_base: str) -> type:
    """
    Constrói um modelo Pydantic permissivo a partir de um JSON Schema dict.
    Usado quando args_schema chega como dict em vez de BaseModel.
    """
    properties = schema_dict.get("properties", {})
    required = set(schema_dict.get("required", []))
    campos: dict[str, Any] = {}

    for nome, prop in properties.items():
        tipo_python = _tipo_python_de_json_schema(prop.get("type", "string"))
        desc = prop.get("description", "")
        if nome in required:
            campos[nome] = (tipo_python, FieldInfo(description=desc))
        else:
            campos[nome] = (Optional[tipo_python], FieldInfo(default=None, description=desc))

    return create_model(f"{nome_base}GroqCompat", **campos)

def _make_coercion_coroutine(original_coroutine, schema_dict: dict):
    """
    Envolve a coroutine original com coerção de tipos.

    Necessário porque temos duas camadas de validação:
    1. Groq valida o schema Python → resolvido pelo patch de tipos permissivos
    2. MCP server (Node.js/Zod) valida os valores reais → resolvido aqui

    Conversões aplicadas antes de chamar o MCP:
    - "1" (str) → 1 (int) para campos integer
    - "1.5" (str) → 1.5 (float) para campos number
    - "8" (str) → ["8"] (list) para campos array
    - None → removido (evita enviar null para campos opcionais)
    """
    properties = schema_dict.get("properties", {})

    async def coroutine_com_coercao(**kwargs):
        import json as _json

        args_convertidos = {}

        for chave, valor in kwargs.items():

            # Remove None E a string "null" que o LLM às vezes gera
            if valor is None or valor == "null":
                continue

            tipo_esperado = properties.get(chave, {}).get("type", "string")
            tipo_item = properties.get(chave, {}).get("items", {}).get("type", "string")

            if tipo_esperado == "integer" and isinstance(valor, str):
                try:
                    args_convertidos[chave] = int(valor)
                except ValueError:
                    args_convertidos[chave] = valor

            elif tipo_esperado == "number" and isinstance(valor, str):
                try:
                    args_convertidos[chave] = float(valor)
                except ValueError:
                    args_convertidos[chave] = valor

            elif tipo_esperado == "array" and isinstance(valor, str):
                # LLM pode mandar o array inteiro como string JSON: '[6, 8, 9]'
                # Precisamos parsear antes de embrulhar
                try:
                    parsed = _json.loads(valor)
                except (_json.JSONDecodeError, ValueError):
                    parsed = valor  # não é JSON, trata como elemento único

                if isinstance(parsed, list):
                    # Converte cada item interno para o tipo correto
                    if tipo_item in ("integer", "number"):
                        convertidos = []
                        for item in parsed:
                            if isinstance(item, str):
                                try:
                                    convertidos.append(int(item) if tipo_item == "integer" else float(item))
                                except ValueError:
                                    convertidos.append(item)
                            else:
                                convertidos.append(item)  # já é número, mantém
                        args_convertidos[chave] = convertidos
                    else:
                        args_convertidos[chave] = parsed
                else:
                    # Era um valor escalar em formato JSON (ex: "8" → 8)
                    if tipo_item in ("integer", "number"):
                        try:
                            args_convertidos[chave] = [int(parsed) if tipo_item == "integer" else float(parsed)]
                        except (ValueError, TypeError):
                            args_convertidos[chave] = [parsed]
                    else:
                        args_convertidos[chave] = [parsed]

            elif tipo_esperado == "array" and isinstance(valor, list):
                if tipo_item in ("integer", "number"):
                    convertidos = []
                    for item in valor:
                        if isinstance(item, str):
                            try:
                                convertidos.append(int(item) if tipo_item == "integer" else float(item))
                            except ValueError:
                                convertidos.append(item)
                        else:
                            convertidos.append(item)
                    args_convertidos[chave] = convertidos
                else:
                    args_convertidos[chave] = valor

            else:
                args_convertidos[chave] = valor

        resultado = await original_coroutine(**args_convertidos)

        # Trunca o resultado para evitar estouro de contexto no Groq free tier.
        # O LLM recebe os primeiros N caracteres — suficiente para análise,
        # sem consumir todo o limite de tokens com dados brutos do PNCP.
        MAX_CHARS = 4000
        if isinstance(resultado, str) and len(resultado) > MAX_CHARS:
            resultado = resultado[:MAX_CHARS] + "\n\n[... resultado truncado para caber no contexto ...]"

        return resultado

    return coroutine_com_coercao


def patch_mcp_tools_para_groq(tools: list) -> list:
    """
    Reconstrói os schemas das MCP tools tornando tipos estritos permissivos.
    Trata tanto schemas Pydantic (model_fields) quanto dicts (JSON Schema).
    """
    resultado = []

    for tool in tools:
        schema_original = getattr(tool, "args_schema", None)

        if schema_original is None:
            resultado.append(tool)
            continue

        # --- Caso 1: schema é um dict (JSON Schema puro) ---
        if isinstance(schema_original, dict):
            NovoSchema = _model_de_json_schema(schema_original, tool.name)
            schema_para_coercao = schema_original  # já é dict

        # --- Caso 2: schema é um modelo Pydantic ---
        elif hasattr(schema_original, "model_fields"):
            novos_campos = {}
            for nome_campo, field_info in schema_original.model_fields.items():
                novo_tipo = _tornar_tipo_permissivo(field_info.annotation)
                novos_campos[nome_campo] = (
                    novo_tipo,
                    FieldInfo(
                        default=field_info.default,
                        description=field_info.description,
                    ),
                )
            NovoSchema = create_model(
                f"{schema_original.__name__}GroqCompat",
                **novos_campos
            )
            # Converte o modelo Pydantic para dict antes de passar para coerção
            schema_para_coercao = schema_original.model_json_schema()

        # --- Caso 3: tipo desconhecido — mantém sem alteração ---
        else:
            resultado.append(tool)
            continue

        tool_corrigida = StructuredTool(
            name=tool.name,
            description=tool.description,
            args_schema=NovoSchema,
            coroutine=_make_coercion_coroutine(getattr(tool, "coroutine", None), schema_para_coercao),
            func=getattr(tool, "func", None),
            return_direct=getattr(tool, "return_direct", False),
        )
        resultado.append(tool_corrigida)

    return resultado