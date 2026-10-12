import chromadb
from sentence_transformers import SentenceTransformer


# Create the vector database
client = chromadb.PersistentClient(path="./chroma_db")

collection = client.get_or_create_collection(
    name="pokemon_knowledge"
)

# Embedding model
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


documents = [
    """
    Pikachu is an Electric-type Pokémon. It is known as the Mouse Pokémon.
    Pikachu can evolve from Pichu when its friendship is high enough.
    Pikachu evolves into Raichu when exposed to a Thunder Stone.
    """,

    """
    Charizard is a Fire/Flying-type Pokémon. It is the final evolution
    of Charmander. Charmander evolves into Charmeleon, which then evolves
    into Charizard.
    """,

    """
    Bulbasaur is a Grass/Poison-type Pokémon. It is one of the original
    starter Pokémon from the Kanto region. Bulbasaur can evolve into
    Ivysaur and then Venusaur.
    """,

    """
    Squirtle is a Water-type Pokémon. It is one of the original starter
    Pokémon from the Kanto region. Squirtle evolves into Wartortle and
    then Blastoise.
    """,

    """
    Pokémon are fictional creatures that can be caught, trained and used
    in battles. Different Pokémon have different types, abilities,
    statistics, moves and evolutionary families.
    """
]


# Add the documents to ChromaDB
for index, document in enumerate(documents):

    embedding = embedding_model.encode(document).tolist()

    collection.upsert(
        ids=[f"document_{index}"],
        documents=[document],
        embeddings=[embedding]
    )


print("Knowledge base created successfully.")