from ollama import chat
from web_page import fetch_web_page


tools = [
    {
        "type": "function",
        "function": {
            "name": "fetch_web_page",
            "description": (
                "Fetch and read the contents of a webpage. "
                "Use this when you need detailed information from "
                "a specific webpage found through web search."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL of the webpage to read."
                    }
                },
                "required": ["url"]
            }
        }
    }
]


messages = [
    {
        "role": "user",
        "content": (
            "Read this webpage and tell me what the Pokémon World "
            "Championships are: "
            "https://en.wikipedia.org/wiki/Pok%C3%A9mon_World_Championships"
        )
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

        if tool_call.function.name == "fetch_web_page":

            url = tool_call.function.arguments["url"]

            print("\nFetching page:")
            print(url)

            result = fetch_web_page(url)

            print("\nPage fetched successfully.")

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