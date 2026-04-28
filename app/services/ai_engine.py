from app.core.config_groq import retornar_cliente_groq
from app.models.consulta_cnpj import ConsultaCNPJ
from app.services.tools import consultar_receita_federal
import json

def run_agent(texto_edital: str, lista_cnpj: list) -> str:
    """
    Executa o agente de auditoria sobre o texto de um edital ou contrato público.

    O agente opera em um laço (agentic loop): a cada iteração ele chama o modelo
    de linguagem e verifica se o modelo quer executar alguma ferramenta (ex: consulta
    de CNPJ na Receita Federal). Se sim, executa a ferramenta e devolve o resultado
    ao modelo na próxima iteração. O laço termina quando o modelo produz uma resposta
    textual final (sem pedido de ferramenta) ou quando o número máximo de tentativas
    é atingido.

    Args:
        texto_edital (str): Texto extraído do edital, contrato ou documento público
                           que será analisado pelo agente.
        lista_cnpj (list[str]): Lista de CNPJs encontrados no documento.

    Returns:
        str: Análise gerada pelo modelo com base no documento e nos dados da Receita
             Federal, ou uma mensagem de erro se o processo falhar.
    """

    # Histórico de mensagens da conversa. Começa com o system prompt (identidade e regras
    # do agente) e a mensagem do usuário (o texto do edital). A cada volta do laço,
    # novas mensagens são appendadas aqui — isso permite que o modelo "lembre" de tudo
    # que aconteceu, incluindo os resultados das ferramentas executadas.
    
    cnpjs_formatados = ", ".join(lista_cnpj) if lista_cnpj else "Nenhum CNPJ encontrado."

    prompt_dinamico = f"""
        O usuário enviou um edital público. Nosso sistema de extração encontrou os seguintes CNPJs no documento:
        [{cnpjs_formatados}]
    
        Por favor, utilize a ferramenta de consulta à Receita Federal para validar cada um destes CNPJs 
        e me entregue um relatório com a Razão Social e a Situação Cadastral de cada empresa.
    """

    messages=[
        {
            "role": "system",
            "content": """
            Você é o 'Auditor Cidadão', um assistente especializado em análise de licitações, contratos públicos e editais brasileiros.

            ## TAREFA PRIMÁRIA — OBRIGATÓRIA

            Ao receber qualquer documento (edital, contrato ou anexo), sua **primeira e obrigatória ação** é:
            1. Identificar **todos os CNPJs** mencionados no documento.
            2. Para **cada CNPJ encontrado**, chamar imediatamente a ferramenta `consultar_receita_federal`.
            3. **Nunca pular esta etapa.** Se não houver CNPJ explícito, informe ao usuário antes de prosseguir.

            ## COMPORTAMENTO APÓS A CONSULTA

            **Se a ferramenta retornar dados com sucesso:**
            - Use os dados retornados (razão social, status, CNAE, etc.) como fonte primária de verdade.
            - Compare-os com as informações declaradas no documento e sinalize qualquer divergência.

            **Se a ferramenta retornar um erro (ex: CNPJ inválido, serviço indisponível, timeout):**
            - Informe claramente ao usuário: "Não foi possível consultar o CNPJ [XXXX] junto à Receita Federal: [motivo do erro]."
            - Continue a análise utilizando **apenas** as informações disponíveis no documento, sinalizando que os dados da Receita Federal não puderam ser verificados.
            - **Nunca invente ou assuma** dados que deveriam ter vindo da ferramenta.

            ## REGRAS GERAIS

            - Baseie suas conclusões estritamente nos documentos oficiais e nos dados retornados pela ferramenta.
            - Seja preciso, imparcial e direto.
            - Sinalize claramente quando uma informação não pôde ser verificada.
            """
        },
        {
            "role": "user",
            "content": prompt_dinamico
        }
    ]

    # Instancia o cliente da API Groq (as credenciais são lidas de variáveis de ambiente
    # dentro de retornar_cliente_groq(), mantendo segredos fora do código).
    cliente = retornar_cliente_groq()

    # Contador de segurança: impede que o agente fique preso em um laço infinito
    # caso o modelo continue pedindo ferramentas sem convergir para uma resposta final.
    tentativa = 0

    # --- AGENTIC LOOP ---
    # Cada iteração representa um "turno" do agente:
    #   1. Chama o modelo com o histórico atual.
    #   2. Se o modelo retornar tool_calls → executa a ferramenta e continua.
    #   3. Se o modelo retornar texto puro → resposta final encontrada, encerra.
    while tentativa < 3:

        response = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile", # melhor modelo gratuito da groq para trabalhar com editais de licitação. É o modelo mais robusto da lista. Para auditoria, modelos menores (como o 8B) falham em entender nuances jurídicas e perdem o fio da meada ao cruzar dados de dois arquivos diferentes. O 70B tem o raciocínio necessário para identificar se um contrato está em desacordo com o edital original. Mas futuramente testar com o Claude 3.5 Sonnet que é o padrão de ouro.
            messages=messages,
            tools=[{
                "type": "function",
                "function": {
                    "name": "consultar_receita_federal",
                    "description": "Consulta dados abertos da Receita Federal utilizando o CNPJ.",
                    "parameters": ConsultaCNPJ.model_json_schema()
                }
            }]
        )

        if response.choices[0].message.tool_calls:
            # O modelo pode solicitar múltiplas ferramentas em um único turno (ex: edital
            # com vários CNPJs). A mensagem do assistente é appendada UMA única vez pois ela
            # carrega todos os tool_calls juntos. Os resultados são appendados individualmente.
            messages.append(response.choices[0].message)

            for tool_call in response.choices[0].message.tool_calls:
                # Extrai o objeto tool_call (contém nome da função, argumentos e um ID único)
                # e desserializa os argumentos JSON para obter o CNPJ solicitado.
                extrair_cnpj = json.loads(tool_call.function.arguments)["cnpj"]

                resultado_tool = consultar_receita_federal(extrair_cnpj)

                # Cada resultado é vinculado ao seu tool_call_id correspondente.
                # Sem esse vínculo, a API rejeita o contexto como inválido.
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": "consultar_receita_federal",
                    "content": json.dumps(resultado_tool, ensure_ascii=False)
                })

            tentativa += 1

        else:
            # O modelo não pediu nenhuma ferramenta: ele já processou todos os dados
            # disponíveis (documento + resultados das consultas) e produziu a análise final.
            response_final = str(response.choices[0].message.content)
            return response_final

    # Atingiu o limite de tentativas sem o modelo produzir uma resposta textual final.
    # Retorna uma mensagem de erro controlada em vez de deixar a função retornar None.
    return "[ERRO] - Falha no processo de auditoria. Tente novamente"