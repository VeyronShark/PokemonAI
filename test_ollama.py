from ollama import chat

response = chat(
    model="qwen3:4b",
    messages=[
        {
            "role": "user",
            "content": "What is Pikachu?"
        }
    ]
)

print(response.message.content)