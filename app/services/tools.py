def consultar_receita_federal(cnpj: str) -> dict:
    """Consulta dados abertos da Receita Federal utilizando o CNPJ."""
    print(f"[LOG DO SISTEMA] - Acionando Tool de Receita para CNPJ: {cnpj}")
    return {"razao_social": "Mock LTDA", "status": "Ativa"}