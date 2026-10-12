import chromadb
from sentence_transformers import SentenceTransformer


client = chromadb.PersistentClient(path="./chroma_db")

collection = client.get_collection(
    name="pokemon_knowledge"
)

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


def search_knowledge(question: str):

    query_embedding = embedding_model.encode(
        question
    ).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=2
    )

    documents = results["documents"][0]

    return documents