"""
Pipeline de RAG do edital: chunking do texto extraído do PDF, geração de embeddings
e indexação/busca no Pinecone. Instanciado uma única vez como singleton em
app/core/dependencies.py — abrir a conexão com o Pinecone é caro demais para
repetir a cada requisição.
"""

import os

from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pinecone import Pinecone

from app.core.logging_config import logger


class GerenciadorVetorial:
    """
    Orquestra o pipeline completo de indexação e recuperação de editais (RAG).
    Gerencia a conexão com o Pinecone e expõe métodos para chunking, upsert e busca semântica.
    """

    def __init__(self):
        # Instancia o modelo de embedding e a conexão com o Pinecone uma única vez,
        # para reutilizar em todas as chamadas sem recriar conexões desnecessariamente
        self.modelo_embedding = OpenAIEmbeddings(model="text-embedding-3-small")
        self.pinecone = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        self.index_name = "auditor-cidadao"
        self.vector_store = PineconeVectorStore(
            index_name=self.index_name, embedding=self.modelo_embedding
        )

    def chunkizar_documento(
        self, texto_edital: str, tamanho_chunk: int = 2000, overlap: int = 200
    ) -> list[str]:
        """
        Divide o texto bruto do edital em chunks semânticos para indexação.
        Usa separadores hierárquicos (parágrafo → linha → frase → palavra) para
        preservar a coerência do texto e evitar cortes no meio de cláusulas.
        """
        if not texto_edital:
            return []

        # RecursiveCharacterTextSplitter tenta cada separador em ordem,
        # só avança para o próximo se o chunk ainda exceder tamanho_chunk
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=tamanho_chunk,
            chunk_overlap=overlap,
            length_function=len,
            separators=["\n\n", "\n", ".", " "],
        )

        lista_chunks = text_splitter.split_text(texto_edital)
        logger.info(
            "Chunkização concluída | chunks=%d | tamanho_max=%d | overlap=%d",
            len(lista_chunks),
            tamanho_chunk,
            overlap,
        )

        return lista_chunks

    def processar_e_salvar(
        self, lista_chunks: list[str], metadados: dict, namespace: str = "production"
    ) -> None:
        """
        Gera embeddings para cada chunk e realiza o upsert no Pinecone em lote.
        Os metadados são replicados em todos os chunks para permitir filtragem posterior por estado e município.
        """
        logger.info(
            "Enviando chunks ao Pinecone | chunks=%d | index=%s | namespace=%s | metadados=%s",
            len(lista_chunks),
            self.index_name,
            namespace,
            metadados,
        )

        self.vector_store.add_texts(
            texts=lista_chunks,
            metadatas=[metadados] * len(lista_chunks),
            namespace=namespace,
        )
        logger.info("Upsert concluído | index=%s | namespace=%s", self.index_name, namespace)

    def buscar_contexto(
        self,
        pergunta: str,
        estado: str,
        municipio: str,
        namespace: str = "production",
    ) -> str:
        """
        Busca semanticamente os 3 trechos do edital mais relevantes para a pergunta.
        Filtra por estado e município para garantir que o contexto retornado
        pertence ao edital correto e não a outro município indexado.
        """
        logger.info(
            "Busca semântica | pergunta=%s | estado=%s | municipio=%s | namespace=%s",
            pergunta[:80],
            estado,
            municipio,
            namespace,
        )

        # Converte a pergunta em vetor e localiza os K=3 chunks mais próximos semanticamente
        documentos_encontrados = self.vector_store.similarity_search(
            query=pergunta,
            k=3,
            filter={
                "estado": estado,
                "municipio": municipio,
            },
            namespace=namespace,
        )
        logger.info(
            "Busca concluída | documentos_encontrados=%d", len(documentos_encontrados)
        )

        # Retorno explícito evita que o agente receba contexto vazio e tente "adivinhar" o edital
        if not documentos_encontrados:
            return "Nenhum trecho relevante encontrado no edital para a combinação de estado, município e pergunta informados. Verifique se o edital foi indexado corretamente."

        contexto_final = "\n\n".join(
            [doc.page_content for doc in documentos_encontrados]
        )

        return contexto_final

    def executar(
        self, texto_edital: str, metadados: dict, namespace: str = "production"
    ) -> None:
        """
        Ponto de entrada público para indexar um edital no banco vetorial.
        Valida o texto, chunkiza e persiste no Pinecone em sequência.
        """
        if not texto_edital:
            raise ValueError("O texto do edital não pode ser vazio.")

        lista_chunks = self.chunkizar_documento(texto_edital)
        self.processar_e_salvar(lista_chunks, metadados, namespace=namespace)
