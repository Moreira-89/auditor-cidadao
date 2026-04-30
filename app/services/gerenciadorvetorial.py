from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone


class GerenciadorVetorial:
    """Orquestra o pipeline completo de indexação vetorial de editais públicos.

    Responsável por três etapas sequenciais:
    1. **Chunking** — divide o texto bruto em fragmentos semânticos via
       ``RecursiveCharacterTextSplitter``.
    2. **Embedding + Indexação** — converte os chunks em vetores usando o modelo
       ``all-MiniLM-L6-v2`` (HuggingFace) e os persiste no Pinecone Vector Store,
       junto com os metadados do edital.

    O método de entrada pública é :meth:`executar`, que encadeia as etapas acima
    de forma transparente. Os métodos internos (:meth:`chunkizar_documento` e
    :meth:`processar_e_salvar`) ficam disponíveis para uso e testes isolados.

    Attributes:
        modelo_embedding (HuggingFaceEmbeddings): Modelo de embedding carregado na
            inicialização. Reutilizado em todas as chamadas para evitar recarregamento.
        pinecone (Pinecone): Cliente autenticado do Pinecone.
        index_name (str): Nome do índice Pinecone onde os vetores serão armazenados.
    """

    def __init__(self):
        self.modelo_embedding = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        self.pinecone = Pinecone(api_key="[PINECONE_API_KEY]")
        self.index_name = "auditor-cidadao"

    # ------------------------------------------------------------------
    # Métodos internos
    # ------------------------------------------------------------------

    def chunkizar_documento(
        self, texto_edital: str, tamanho_chunk: int = 2000, overlap: int = 200
    ) -> list[str]:
        """Divide um texto em chunks semânticos usando ``RecursiveCharacterTextSplitter``.

        Ao contrário de uma divisão simples por caracteres, esta função tenta preservar
        a coerência semântica do texto respeitando uma hierarquia de separadores:
        parágrafos (``\\n\\n``) → linhas (``\\n``) → sentenças (``.``) → palavras (`` ``).
        Só avança para o próximo separador se o chunk ainda ultrapassar ``tamanho_chunk``
        com o separador anterior — garantindo fragmentos mais naturais e adequados para
        pipelines de RAG aplicados a editais e documentos jurídicos longos.

        Args:
            texto_edital (str): Texto bruto do edital a ser fragmentado.
            tamanho_chunk (int): Tamanho máximo de cada chunk, em número de caracteres.
                Padrão: 2000.
            overlap (int): Número de caracteres compartilhados entre chunks consecutivos.
                A sobreposição preserva contexto nas bordas e melhora a qualidade da
                recuperação semântica. Deve ser menor que ``tamanho_chunk``. Padrão: 200.

        Returns:
            list[str]: Lista de strings representando os chunks do texto original,
                respeitando os separadores configurados. Retorna uma lista vazia se
                ``texto_edital`` for vazio ou ``None``.
        """
        if not texto_edital:
            return []

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=tamanho_chunk,
            chunk_overlap=overlap,
            length_function=len,
            separators=["\n\n", "\n", ".", " "],
        )

        lista_chunks = text_splitter.split_text(texto_edital)

        return lista_chunks

    def processar_e_salvar(self, lista_chunks: list[str], metadados: dict) -> None:
        """Converte chunks em vetores e os persiste no Pinecone Vector Store.

        Utiliza ``PineconeVectorStore.from_texts`` para gerar embeddings e indexar
        todos os chunks em uma única operação em lote. Os mesmos ``metadados`` são
        replicados para cada chunk, permitindo filtros por edital na recuperação.

        Args:
            lista_chunks (list[str]): Lista de fragmentos de texto a serem vetorizados
                e salvos. Gerada tipicamente por :meth:`chunkizar_documento`.
            metadados (dict): Dicionário com informações do edital associado aos chunks
                (ex: ``{"municipio": "São Paulo", "estado": "SP", "arquivo": "edital.pdf"}``).
                O mesmo dicionário é aplicado a todos os chunks.
        """
        PineconeVectorStore.from_texts(
            texts=lista_chunks,
            embedding=self.modelo_embedding,
            index_name=self.index_name,
            metadatas=[metadados] * len(lista_chunks),
        )

    def buscar_contexto(
        self, pergunta: str, estado: str, municipio: str
    ) -> str:
        """
        Realiza a Busca Semântica (Retrieval) no banco de dados vetorial Pinecone.

        COMO FUNCIONA:
        Em vez de procurar por palavras-chave exatas (como no Google antigo), esta 
        função transforma a `pergunta` em um vetor matemático. Em seguida, ela 
        procura no Pinecone quais "fatias" (chunks) de texto do edital têm 
        vetores matematicamente mais próximos ao vetor da pergunta. 
        Assim, conseguimos achar textos com o mesmo significado, mesmo que 
        usem palavras diferentes.

        Args:
            pergunta (str): A dúvida do usuário em linguagem natural.
            estado (str): Sigla do estado (usado como filtro para focar a busca).
            municipio (str): Nome do município (usado como filtro para focar a busca).

        Returns:
            str: Um grande bloco de texto consolidado contendo apenas os trechos 
                 mais relevantes do edital que respondem à pergunta.
        """
        
        # --- 1. CONEXÃO COM O ÍNDICE ---
        # Instancia a interface de busca da biblioteca LangChain apontando para
        # o nosso índice no Pinecone e usando o mesmo modelo de embedding que
        # foi usado na hora de salvar o texto (HuggingFace).
        vector_store = PineconeVectorStore(
            index_name=self.index_name,
            embedding=self.modelo_embedding
        )

        # --- 2. BUSCA POR SIMILARIDADE ---
        # A função similarity_search faz a mágica acontecer: ela converte a pergunta
        # e acha os documentos mais próximos no espaço vetorial.
        documentos_encontrados = vector_store.similarity_search(
            query=pergunta,
            k=3, # Define que queremos apenas os 3 pedaços de texto MAIS relevantes (evita lixo e economiza tokens)
            filter={
                # O filtro é extremamente importante no cenário de múltiplos editais!
                # Garante que, se perguntarmos de um edital de "Campinas-SP", 
                # a busca não traga trechos de um edital de "Recife-PE" que 
                # estivesse falando de um assunto parecido.
                "estado": estado,
                "municipio": municipio,
            }
        )

        # --- 3. CONSOLIDAÇÃO DO CONTEXTO ---
        # A busca retorna uma lista de objetos 'Document'. O texto real está 
        # dentro de 'page_content'. Extraímos esses textos e juntamos todos 
        # separados por duas quebras de linha para ficar fácil para a IA ler depois.
        contexto_final = "\n\n".join([doc.page_content for doc in documentos_encontrados])

        return contexto_final

    # ------------------------------------------------------------------
    # Método orquestrador (ponto de entrada público)
    # ------------------------------------------------------------------

    def executar(self, texto_edital: str, metadados: dict) -> str:
        """Executa o pipeline completo de indexação vetorial do edital.

        Encadeia :meth:`chunkizar_documento` e :meth:`processar_e_salvar` em sequência,
        expondo um único ponto de entrada para o uso externo (ex: endpoints FastAPI).
        Falha rapidamente se o texto estiver vazio, evitando chamadas desnecessárias
        ao Pinecone.

        Args:
            texto_edital (str): Texto bruto extraído do PDF do edital.
            metadados (dict): Metadados do edital a serem associados a cada chunk
                no índice vetorial (ex: município, estado, nome do arquivo).

        Returns:
            str: Mensagem de confirmação ao término do processamento.

        Raises:
            ValueError: Se ``texto_edital`` for vazio ou ``None``.
        """
        if not texto_edital:
            raise ValueError("O texto do edital não pode ser vazio.")

        lista_chunks = self.chunkizar_documento(texto_edital)
        self.processar_e_salvar(lista_chunks, metadados)

        return "Edital analisado com sucesso! Pode fazer perguntas sobre o edital..."
