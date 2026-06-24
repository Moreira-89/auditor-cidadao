import json
import logging
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

    _log = logging.getLogger("mcp.coercao")

    async def coroutine_com_coercao(**kwargs):
        _log.info("[COERCAO] kwargs recebidos: %s", kwargs)
        args_convertidos = {}

        for chave, valor in kwargs.items():
            if valor is None:
                continue  # Remove nulls — o MCP usa defaults internos

            tipo_esperado = properties.get(chave, {}).get("type", "string")
            tipo_item = properties.get(chave, {}).get("items", {}).get("type", "string")
            _log.info(
                "[COERCAO] campo=%s | valor=%r | tipo_esperado=%s | tipo_item=%s",
                chave, valor, tipo_esperado, tipo_item,
            )

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
                # Descobre o tipo dos elementos internos do array
                tipo_item = properties.get(chave, {}).get("items", {}).get("type", "string")

                # Converte o item para o tipo correto antes de empacotar na lista
                if tipo_item in ("integer", "number"):
                    try:
                        item_convertido = int(valor) if tipo_item == "integer" else float(valor)
                    except ValueError:
                        item_convertido = valor
                else:
                    item_convertido = valor

                args_convertidos[chave] = [item_convertido]

            elif tipo_esperado == "array" and isinstance(valor, list):
                # Array já veio como lista — garante que os itens internos também estejam corretos
                tipo_item = properties.get(chave, {}).get("items", {}).get("type", "string")
                if tipo_item in ("integer", "number"):
                    items_convertidos = []
                    for item in valor:
                        if isinstance(item, str):
                            try:
                                items_convertidos.append(int(item) if tipo_item == "integer" else float(item))
                            except ValueError:
                                items_convertidos.append(item)
                        else:
                            items_convertidos.append(item)
                    args_convertidos[chave] = items_convertidos
                else:
                    args_convertidos[chave] = valor

            else:
                args_convertidos[chave] = valor

        _log.info("[COERCAO] args_convertidos enviados ao MCP: %s", args_convertidos)
        return await original_coroutine(**args_convertidos)

    return coroutine_com_coercao


def patch_mcp_tools_para_groq(tools: list) -> list:
    """
    Reconstrói os schemas das MCP tools tornando tipos estritos permissivos.
    Trata tanto schemas Pydantic (model_fields) quanto dicts (JSON Schema).
    """
    # DEBUG TEMPORÁRIO — remover após diagnóstico
    for tool in tools:
        if tool.name == "search_licitacoes":
            schema = getattr(tool, "args_schema", None)
            print("\n=== SCHEMA REAL: search_licitacoes ===")
            if isinstance(schema, dict):
                print(json.dumps(schema, indent=2, ensure_ascii=False))
            elif hasattr(schema, "model_json_schema"):
                print(json.dumps(schema.model_json_schema(), indent=2, ensure_ascii=False))
            else:
                print(f"Tipo desconhecido: {type(schema)}")
            print("=====================================\n")
            
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