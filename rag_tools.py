import logging
from time import perf_counter

import chromadb
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("pokemonai.knowledge")

client = chromadb.PersistentClient(path="./chroma_db")

collection = client.get_collection(
    name="pokemon_knowledge"
)

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


def search_knowledge(question: str):
    started_at = perf_counter()
    logger.info("Knowledge search embedding started")

    query_embedding = embedding_model.encode(
        question
    ).tolist()
    logger.info(
        "Knowledge search embedding completed vector_size=%d duration_ms=%.1f",
        len(query_embedding),
        (perf_counter() - started_at) * 1000,
    )

    query_started_at = perf_counter()
    logger.info("Knowledge database query started result_limit=2")
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=2
    )

    documents = results["documents"][0]
    logger.info(
        "Knowledge database query completed document_count=%d duration_ms=%.1f",
        len(documents),
        (perf_counter() - query_started_at) * 1000,
    )

    return documents