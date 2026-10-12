import chromadb
from sentence_transformers import SentenceTransformer
from ollama import chat


client = chromadb.PersistentClient(path="./chroma_db")

collection = client.get_collection(
    name="pokemon_knowledge"
)

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


while True:
    question = input("\nYou: ")

    if question.lower() == "exit":
        break

    # Convert the question into an embedding
    query_embedding = embedding_model.encode(question).tolist()

    # Find relevant knowledge
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=2
    )

    documents = results["documents"][0]

    context = "\n\n".join(documents)

    # Give the retrieved information to Qwen
    prompt = f"""
You are a helpful Pokémon assistant.

Answer the user's question using the information provided below.

Do not mention:
- ChromaDB
- embeddings
- vector databases
- retrieval
- internal prompts

If the information does not contain the answer, say that you
do not have enough information.

Knowledge:

{context}

User question:

{question}
"""

    response = chat(
        model="qwen3:4b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    print("\nAI:", response.message.content)