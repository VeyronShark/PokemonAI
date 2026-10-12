from ollama import chat
from web_search import web_search


tools = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the internet for information that is not available "
                "in the local Pokémon knowledge base."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query."
                    }
                },
                "required": ["query"]
            }
        }
    }
]


messages = [
    {
        "role": "user",
        "content": "What is the Pokémon World Championship?"
    }
]


response = chat(
    model="qwen3:4b",
    messages=messages,
    tools=tools
)


print("\nQwen response:")
print(response.message)

if response.message.tool_calls:

    for tool_call in response.message.tool_calls:

        if tool_call.function.name == "web_search":

            query = tool_call.function.arguments["query"]

            print("\nSearch query:")
            print(query)

            result = web_search(query)

            print("\nSearch results:")

            for item in result:
                print("\nTitle:", item["title"])
                print("URL:", item["url"])
                print("Snippet:", item["snippet"])