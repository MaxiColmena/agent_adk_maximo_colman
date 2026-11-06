import re

import chromadb
from ddgs import DDGS
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

VECTOR_STORE_PATH = "./vector_store"


def _validar_nombre_coleccion(collection_name: str):
    """Chroma solo acepta nombres de 3 a 63 caracteres: letras, numeros, puntos, guiones y guiones bajos."""
    if not collection_name or not collection_name.strip():
        return "Error: el nombre de la coleccion no puede estar vacio."
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{1,61}[a-zA-Z0-9]", collection_name.strip()):
        return (
            "Error: nombre de coleccion invalido. Debe tener entre 3 y 63 caracteres, "
            "solo letras, numeros, puntos, guiones o guiones bajos, sin espacios."
        )
    return None


def web_search(query: str, max_results: int = 5):
    """
    Herramienta para busquedas en internet utilizando duckduckgo_search
    Args:
        query: str -> La consulta buscar en internet.
        max_results: int -> cantidad maxima de resultados (entre 1 y 10).
    """
    if not query or not query.strip():
        return "Error: la consulta no puede estar vacia."
    if not isinstance(max_results, int) or not 1 <= max_results <= 10:
        return "Error: max_results debe ser un numero entero entre 1 y 10."
    try:
        results = DDGS().text(query=query, max_results=max_results)
        if not results:
            return "No se encontraron resultados en internet para esa consulta."
        return results
    except Exception as e:
        print("Error interno al utilizar la herramienta", e)
        return str(e)


def index_data(query: str, collection_name: str):
    """
    Herramienta para indexar data en la base de datos vectorial,
    Args:
        query: str -> Texto a indexar
        collection_name: str -> Nombre de la colección a utilizar
    """
    if not query or not query.strip():
        return "Error: no hay texto para indexar."
    error = _validar_nombre_coleccion(collection_name)
    if error:
        return error
    try:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
        )
        docs = text_splitter.create_documents([query])
        vector_store = Chroma(
            embedding_function=OllamaEmbeddings(
                model="nomic-embed-text",
            ),
            persist_directory=VECTOR_STORE_PATH,
            collection_name=collection_name.strip(),
        )
        results = vector_store.add_documents(documents=docs)
        print("Documentos vectorizados: ", results)
        return f"Documentos vectorizados: {len(results)}"
    except Exception as e:
        return str(e)


def list_collection():
    """
    Herramienta para listar las colleciones disponibles.
    """
    try:
        client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
        collections = client.list_collections()
        print(collections)
        if not collections:
            return "No hay colecciones en la base de datos vectorial."
        return [c.name for c in collections]
    except Exception as e:
        return str(e)


def retrieval(query: str, collection_name: str, k: int = 5):
    """
    Herramienta para consultar la base de datos vectorial
    Args:
        query: str -> consulta
        collection_name: str -> nombre de la coleccion a utilizar.
        k:int -> cantidad de documentos a obtener de la busqueda (entre 1 y 10)
    """
    if not query or not query.strip():
        return "Error: la consulta no puede estar vacia."
    error = _validar_nombre_coleccion(collection_name)
    if error:
        return error
    if not isinstance(k, int) or not 1 <= k <= 10:
        return "Error: k debe ser un numero entero entre 1 y 10."
    try:
        client = chromadb.PersistentClient(path=VECTOR_STORE_PATH)
        existentes = [c.name for c in client.list_collections()]
        if collection_name.strip() not in existentes:
            return f"Error: la coleccion '{collection_name}' no existe. Colecciones disponibles: {existentes}"

        vector_store = Chroma(
            embedding_function=OllamaEmbeddings(
                model="nomic-embed-text",
            ),
            persist_directory=VECTOR_STORE_PATH,
            collection_name=collection_name.strip(),
        )
        results = vector_store.similarity_search_with_relevance_scores(query=query, k=k)
        if not results:
            return "No se encontraron documentos relacionados en la coleccion."
        return [{"contenido": doc.page_content, "relevancia": round(score, 3)} for doc, score in results]
    except Exception as e:
        return str(e)
