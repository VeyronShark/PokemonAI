import chromadb
from sentence_transformers import SentenceTransformer


client = chromadb.PersistentClient(path="./chroma_db")

collection = client.get_collection(
    name="pokemon_knowledge"
)

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


while True:
    question = input("\nQuestion: ")

    if question.lower() == "exit":
        break

    query_embedding = embedding_model.encode(question).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=2
    )

    print("\nRelevant information:")

    for document in results["documents"][0]:
        print("-", document)