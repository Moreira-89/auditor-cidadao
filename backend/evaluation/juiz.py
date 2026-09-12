from deepeval.models import DeepEvalBaseLLM, GeminiModel, OpenAIModel


def construir_juiz(modelo: str, temperatura: float) -> DeepEvalBaseLLM:
    """Modelo-juiz a partir do prefixo provider:model em AVALIADOR_MODEL — mesma
    convenção do LLM_MODEL (app/llm.py). Hoje suporta openai: (default) e gemini:."""
    if modelo.startswith("gemini:"):
        return GeminiModel(model=modelo.removeprefix("gemini:"), temperature=temperatura)
    return OpenAIModel(model=modelo.removeprefix("openai:"), temperature=temperatura)
