from rag_tools import search_knowledge


question = input("Question: ")

results = search_knowledge(question)

print("\nResults:")

for result in results:
    print("\n---")
    print(result)