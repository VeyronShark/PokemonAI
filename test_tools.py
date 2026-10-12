from ollama import chat
from pokemon_tools import get_pokemon


tools = [
    {
        "type": "function",
        "function": {
            "name": "get_pokemon",
            "description": "Look up factual information about a specific Pokémon using the Pokémon database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the Pokémon to look up."
                    }
                },
                "required": ["name"]
            }
        }
    }
]


messages = [
    {
        "role": "user",
        "content": "What can you tell me about Pikachu?"
    }
]


response = chat(
    model="qwen3:4b",
    messages=messages,
    tools=tools
)


messages.append(response.message)


if response.message.tool_calls:

    for tool_call in response.message.tool_calls:

        if tool_call.function.name == "get_pokemon":

            name = tool_call.function.arguments["name"]

            result = get_pokemon(name)

            print("Tool executed:")
            print(result)

            messages.append({
                "role": "tool",
                "content": str(result)
            })


final_response = chat(
    model="qwen3:4b",
    messages=messages,
    tools=tools
)


print("\nFinal answer:")
print(final_response.message.content)