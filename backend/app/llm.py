from langchain.chat_models import init_chat_model


def retornar_cliente_llm(model_name: str, config_params: dict | None = None):
    """Cria um cliente LLM via init_chat_model (provider identificado pelo prefixo de model_name)."""
    config_params = config_params or {}  # sentinela: evita default mutável compartilhado
    return init_chat_model(model_name, **config_params)