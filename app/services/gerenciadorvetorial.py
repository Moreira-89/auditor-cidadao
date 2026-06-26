import os

from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone

from app.core.logging_config import logger


# -----------------------------------------------------------------------------
# CLASSE GERENCIADOR VETORIAL
# -----------------------------------------------------------------------------
class GerenciadorVetorial:
    """
    Objetivo: Orquestrar o pipeline completo de indexação vetorial e recuperação (RAG).

    COMO FUNCIONA:
    1. Instanciação: Ao inicializar, a classe carrega o modelo de linguagem local 'all-MiniLM-L6-v2' para gerar embeddings e autentica a conexão com a API do Pinecone.
    2. Utilização: Encapsula os métodos responsáveis por particionar o texto (chunking), convertê-lo e persistir no banco, além de expor o mecanismo de busca.

    Attributes:
        modelo_embedding (HuggingFaceEmbeddings): Modelo de embedding carregado.
        index_name (str): Nome do índice Pinecone.
    """

    def __init__(self):
        # --- 1. Inicialização ---
        # Instancia dependências na criação para serem reutilizadas em várias chamadas.
        self.modelo_embedding = OpenAIEmbeddings(model="text-embedding-3-small")
        self.pinecone = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        self.index_name = "auditor-cidadao"

    # ------------------------------------------------------------------
    # MÉTODOS INTERNOS
    # ------------------------------------------------------------------

    def chunkizar_documento(
        self, texto_edital: str, tamanho_chunk: int = 2000, overlap: int = 200
    ) -> list[str]:
        """
        Objetivo: Dividir um texto bruto em chunks semânticos para o banco de dados.

        COMO FUNCIONA:
        1. Configuração do Splitter: Define os separadores lógicos (parágrafos, linhas, frases, palavras) e os limites de caracteres (chunk_size e overlap).
        2. Processamento: Tenta separar o texto respeitando a coerência, só dividindo na palavra se a frase for grande demais. Retorna a lista de pedaços.

        Args:
            texto_edital (str): Texto bruto do edital.
            tamanho_chunk (int): Tamanho máximo do bloco de texto.
            overlap (int): Número de caracteres repetidos entre blocos vizinhos para não quebrar o sentido.

        Returns:
            list[str]: Lista contendo todos os fragmentos gerados.
        """
        if not texto_edital:
            return []

        # --- 1. Configuração do Splitter ---
        # Usa RecursiveCharacterTextSplitter da LangChain para criar blocos coesos.
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=tamanho_chunk,
            chunk_overlap=overlap,
            length_function=len,
            separators=["\n\n", "\n", ".", " "],
        )

        # --- 2. Processamento ---
        lista_chunks = text_splitter.split_text(texto_edital)
        logger.info("Chunkização concluída | chunks=%d | tamanho_max=%d | overlap=%d",
                    len(lista_chunks), tamanho_chunk, overlap)

        return lista_chunks

    def processar_e_salvar(self, lista_chunks: list[str], metadados: dict) -> None:
        """
        Objetivo: Converter chunks de texto em vetores e gravar no Pinecone.

        COMO FUNCIONA:
        1. Persistência em Lote: Usa a LangChain para gerar os embeddings e realizar o upsert (envio) dos dados para o Pinecone em um único lote otimizado.

        Args:
            lista_chunks (list[str]): Fragmentos do texto do edital.
            metadados (dict): Dados extras para filtrar buscas posteriores (estado, município).
        """
        # --- 1. Persistência em Lote ---
        logger.info("Enviando chunks ao Pinecone | chunks=%d | index=%s | metadados=%s",
                    len(lista_chunks), self.index_name, metadados)
        PineconeVectorStore.from_texts(
            texts=lista_chunks,
            embedding=self.modelo_embedding,
            index_name=self.index_name,
            metadatas=[metadados] * len(lista_chunks),
        )
        logger.info("Upsert concluído | index=%s", self.index_name)

    def buscar_contexto(
        self, pergunta: str, estado: str, municipio: str
    ) -> str:
        """
        Objetivo: Realizar a Busca Semântica (Retrieval) no Pinecone baseada na pergunta.

        COMO FUNCIONA:
        1. Conexão com o Índice: Inicializa a conexão da LangChain com o índice do Pinecone já existente e o modelo de embedding.
        2. Busca por Similaridade: Converte a pergunta em vetor e localiza os K=3 blocos mais próximos no banco que obedeçam ao filtro de estado e município.
        3. Consolidação: Extrai apenas o texto contido nestes blocos e os junta, separando por linha, gerando um texto pronto para ser lido pelo Agente.

        Args:
            pergunta (str): A dúvida do usuário em linguagem natural.
            estado (str): Sigla do estado para filtrar o edital correto.
            municipio (str): Nome do município para filtrar o edital correto.

        Returns:
            str: O texto extraído contendo o contexto útil.
        """
        # --- 1. Conexão com o Índice ---
        vector_store = PineconeVectorStore(
            index_name=self.index_name,
            embedding=self.modelo_embedding
        )

        # --- 2. Busca por Similaridade ---
        # Localiza os 3 trechos mais parecidos semanticamente.
        logger.info("Busca semântica | pergunta=%s | estado=%s | municipio=%s",
                    pergunta[:80], estado, municipio)
        documentos_encontrados = vector_store.similarity_search(
            query=pergunta,
            k=3,
            filter={
                "estado": estado,
                "municipio": municipio,
            }
        )
        logger.info("Busca concluída | documentos_encontrados=%d", len(documentos_encontrados))

        # --- 3. Consolidação ---
        # Se nenhum chunk for encontrado (edital não indexado ou filtros muito restritivos),
        # retornamos uma mensagem de fallback explícita. Isso evita que o agente receba
        # a tag <DOCUMENTO_OFICIAL> vazia e tente "adivinhar" o conteúdo do edital.
        if not documentos_encontrados:
            return "Nenhum trecho relevante encontrado no edital para a combinação de estado, município e pergunta informados. Verifique se o edital foi indexado corretamente."

        contexto_final = "\n\n".join([doc.page_content for doc in documentos_encontrados])

        return contexto_final

    # ------------------------------------------------------------------
    # MÉTODOS PÚBLICOS / ORQUESTRADOR
    # ------------------------------------------------------------------

    def executar(self, texto_edital: str, metadados: dict) -> None:
        """
        Objetivo: Ponto de entrada público para injetar o edital no banco vetorial.

        COMO FUNCIONA:
        1. Validação de Entrada: Se o texto do edital for vazio, bloqueia e retorna erro.
        2. Fragmentação do Texto: Aciona o método interno de chunkizar_documento.
        3. Salvamento: Manda os blocos gerados para processar_e_salvar.

        Args:
            texto_edital (str): O texto bruto do edital extraído pelo pdfplumber.
            metadados (dict): Metadados complementares para o filtro de busca posterior
                              (ex: {'estado': 'SP', 'municipio': 'São Paulo', 'arquivo': 'edital.pdf'}).

        Returns:
            None: A função opera por efeito colateral (persistência no Pinecone).
                  A mensagem de confirmação é responsabilidade do chamador (endpoint de upload).

        Raises:
            ValueError: Se o edital não tiver texto ou estiver vazio.
        """
        # --- 1. Validação de Entrada ---
        if not texto_edital:
            raise ValueError("O texto do edital não pode ser vazio.")

        # --- 2. Fragmentação do Texto ---
        lista_chunks = self.chunkizar_documento(texto_edital)

        # --- 3. Salvamento ---
        self.processar_e_salvar(lista_chunks, metadados)
