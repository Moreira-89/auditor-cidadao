import os

from langchain.chat_models import init_chat_model


def retornar_cliente_llm(model_name: str, config_params: dict | None = None):
    """Cria um cliente LLM via init_chat_model (provider identificado pelo prefixo de model_name)."""
    config_params = dict(config_params or {})  # sentinela: evita default mutável compartilhado

    # Maritaca (Sabiá) não é provider nativo do init_chat_model, mas expõe uma API
    # OpenAI-compatível — roteia via ChatOpenAI trocando só base_url + chave.
    if model_name.startswith("maritaca:"):
        config_params.setdefault("api_key", os.environ["MARITACA_API_KEY"])
        config_params.setdefault(
            "base_url", os.getenv("MARITACA_BASE_URL", "https://chat.maritaca.ai/api")
        )
        return init_chat_model(
            model_name.removeprefix("maritaca:"),
            model_provider="openai",
            **config_params,
        )

    return init_chat_model(model_name, **config_params)
