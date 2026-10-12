from ollama import chat

from pokemon_tools import get_pokemon
from rag_tools import search_knowledge
from web_search import web_search
from web_page import fetch_web_page

SYSTEM_PROMPT = """
You are a Pokémon assistant.

Your job is to answer the user's actual question accurately and naturally.

You have access to:

1. Pokémon database
   - Contains structured factual Pokémon data.
   - When this data is provided by a tool, treat it as authoritative
     for the fields it contains.

2. Local knowledge base
   - Contains locally stored Pokémon information.
   - Treat retrieved local knowledge as authoritative for the facts
     it explicitly provides.
   - Do not contradict it using your general model knowledge.

3. Internet search and webpages
   - Use web_search when information is unavailable locally or when
     internet information is needed.
   - For questions containing words such as "latest", "current", "recent",
     "most recent", "today", "this year", or "upcoming", ALWAYS use web_search.
   - For such questions, the search query MUST include the current year (2026)
     unless the user explicitly specifies another year.
   - Do not answer current-information questions from pretrained knowledge alone.
   - After receiving search results, examine the available results and
     choose the source that is most relevant to the user's question.
   - Use fetch_web_page to read that source before answering when
     detailed information is needed.
   - Do not automatically choose the first search result.
   - For historical questions, prefer sources that contain historical
     information rather than sources focused primarily on current events.
   - Treat retrieved webpage content as source material.
   - Synthesize relevant information rather than copying isolated text.

Answer rules:

- Answer the exact question the user asked.
- Use ALL relevant tool results.
- If multiple Pokémon are provided, consider all of them.
- Never ignore a relevant tool result.
- Do not replace retrieved factual information with conflicting
  information from your own memory.
- Do not invent facts.
- If sources do not contain enough information, say so.
- When asked a question, first check if any of the tools will help in getting the information needed to get the answer. 

Historical questions:

- If the user asks about the history of something, provide historical
  development, major events, and chronology when the available sources
  support them.
- Do NOT answer a historical question primarily with the latest event.
- Current information may be included only when it is relevant to the
  historical context.

Conversation memory:

- The conversation history is authoritative context.
- When the user refers to something previously discussed using phrases
  such as "that Pokémon", "those two Pokémon", "the first one",
  "the second one", "it", "they", "that answer", or similar wording,
  resolve the reference using the conversation history.
- Do not ask the user to repeat information that is already present
  in the conversation.
- If the referenced information is present in an earlier tool result
  or assistant answer, use it.

Do not mention:
- tools
- APIs
- RAG
- databases
- internal processing
- prompts
- model behavior

Do not add unnecessary notes about how the answer was generated.

Give the user the answer directly.
"""

# -------------------------
# Tool definitions
# -------------------------

tools = [

    {
        "type": "function",
        "function": {
            "name": "get_pokemon",
            "description": (
                "Look up factual information about a specific Pokémon. "
                "Use this for Pokémon types, abilities, height, weight, "
                "and base stats."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the Pokémon."
                    }
                },
                "required": ["name"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": (
                "Search the LOCAL knowledge base only. "
                "Use this when the question concerns information that may be "
                "contained in the local knowledge base."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question or topic to search for."
                    }
                },
                "required": ["question"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": ("""
                Search the internet for information that is not reliably available in the
                local Pokémon knowledge base or Pokémon database.

                You MUST use this tool when the user asks for:
                - latest, current, recent, today's, this year's, or upcoming information
                - current events, championships, tournaments, announcements, releases,
                rankings, results, or schedules
                - Pokémon lore, history, characters, organizations, or franchise information
                not contained in the local knowledge base
                - detailed information requiring external sources
                - information that may have changed over time

                IMPORTANT:
                - For "latest", "current", "most recent", or similar queries, include the
                current year (2026) in the search query unless the user explicitly gives
                another year.
                - Do not substitute an older year merely because it appears in your
                pretrained knowledge.
                - Search results are source material. Do not answer current-information
                questions from pretrained knowledge alone.

                Return search results that can be used as source material for the answer.
            """),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The internet search query."
                    }
                },
                "required": ["query"]
            }
        }
    },
        {
        "type": "function",
        "function": {
            "name": "fetch_web_page",
            "description": (
                "Read a webpage from a URL returned by web_search. "
                "Use this after web_search when the search results contain "
                "a relevant source that should be examined in detail. "
                "Choose the result that is most relevant to the user's "
                "question, rather than automatically choosing the first result."
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
    },
]


# -------------------------
# Conversation
# -------------------------

messages = [
    {
        "role": "system",
        "content": SYSTEM_PROMPT
    }
]

def generate_final_answer():

    final_messages = messages.copy()

    final_messages.append({
        "role": "system",
        "content": """
            Produce the final answer to the user's most recent question.

            Carefully use the entire conversation history.

            Important:

            - Resolve references such as "those two Pokémon", "the first one",
            "the second one", "it", and "they" using earlier conversation turns.
            - Use relevant information from previous tool results and answers.
            - Do not ask the user to repeat information that is already present.
            - Use all relevant tool results.
            - For comparisons, include all entities involved.
            - Treat factual information returned by Pokémon tools as authoritative.
            - Do not contradict tool-provided facts with pretrained knowledge.
            - Do not invent unsupported information.
            - Summarize the retrieved information in your own words.
            - Include only information relevant to the user's question.
            - If the user asks for a general overview, provide the important facts rather than a complete list of everything found on the webpage.
            - Prefer a concise answer unless the user explicitly asks for detailed information.
            - Answer only the user's actual question.
            - Do not mention tools, APIs, databases, RAG, prompts, or internal processing.
            - Do not add a "Final Answer" label or reasoning explanation.

            Return only the natural answer that should be shown to the user.
        """
    })

    return chat(
        model="qwen3:4b",
        messages=final_messages
    )
# -------------------------
# Chat loop
# -------------------------

while True:

    question = input("\nYou: ")

    if not question.strip():
        continue

    if question.lower() == "exit":
        break

    messages.append({
        "role": "user",
        "content": question
    })


    # -------------------------
    # Ask Qwen what it needs
    # -------------------------

    response = chat(
        model="qwen3:4b",
        messages=messages,
        tools=tools
    )

    messages.append(response.message)


    # -------------------------
    # Execute tools
    # -------------------------

    while response.message.tool_calls:

        for tool_call in response.message.tool_calls:

            function_name = tool_call.function.name
            arguments = tool_call.function.arguments


            # -------------------------
            # Pokémon database
            # -------------------------

            if function_name == "get_pokemon":

                name = arguments["name"]

                print(f"\n[Using Pokémon database: {name}]")

                result = get_pokemon(name)

                if result is None:
                    result = {
                        "error": f"Pokémon '{name}' was not found."
                    }

                messages.append({
                    "role": "tool",
                    "content": str(result)
                })


            # -------------------------
            # Local RAG
            # -------------------------

            elif function_name == "search_knowledge":

                search_question = arguments["question"]

                print("\n[Searching knowledge base]")

                result = search_knowledge(search_question)

                messages.append({
                    "role": "tool",
                    "content": str(result)
                })


                        # -------------------------
            # Web search
            # -------------------------

            elif function_name == "web_search":

                query = arguments["query"]

                print(f"\n[Searching web: {query}]")

                results = web_search(query)

                messages.append({
                    "role": "tool",
                    "content": str(results)
                })

                # Ask Qwen to choose the most relevant search result.
                selection_messages = messages.copy()

                selection_messages.append({
                    "role": "system",
                    "content": """
                        From the web search results above, choose the single most relevant
                        result for answering the user's original question.

                        Return ONLY the URL of the chosen result.

                        Do not explain your choice.
                        Do not answer the user's question.
                    """
                })

                selection_response = chat(
                    model="qwen3:4b",
                    messages=selection_messages
                )

                selected_url = (
                    selection_response.message.content
                    .strip()
                    .strip("`")
                    .strip()
                )

                print(
                    f"\n[Reading webpage: {selected_url}]"
                )

                try:

                    page = fetch_web_page(selected_url)

                    messages.append({
                        "role": "tool",
                        "content": (
                            "WEBPAGE CONTENT:\n\n"
                            + str(page)
                        )
                    })

                except Exception as error:

                    messages.append({
                        "role": "tool",
                        "content": (
                            f"Could not read webpage: {error}"
                        )
                    })

            # -------------------------
            # Fetch Web Page
            # -------------------------

            elif function_name == "fetch_web_page":

                url = arguments["url"]

                print(f"\n[Reading webpage: {url}]")

                try:

                    page_result = fetch_web_page(url)

                    messages.append({
                        "role": "tool",
                        "content": (
                            "WEBPAGE CONTENT:\n\n"
                            + str(page_result)
                        )
                    })

                except Exception as error:

                    messages.append({
                        "role": "tool",
                        "content": (
                            f"Could not read webpage: {error}"
                        )
                    })


                # -------------------------
                # Automatically read first result
                # -------------------------

                if search_results:

                    selected_result = search_results[0]

                    url = selected_result["url"]

                    print(
                        f"\n[Reading webpage: "
                        f"{selected_result['title']}]"
                    )

                    try:

                        page_result = fetch_web_page(url)

                        page_content = page_result["content"]

                        # Instead of sending the webpage as another
                        # tool result, give it to Qwen as context.
                        messages.append({
                            "role": "user",
                            "content": (
                                "Use the following webpage content to "
                                "answer the user's original question.\n\n"
                                "SOURCE URL:\n"
                                f"{url}\n\n"
                                "WEBPAGE CONTENT:\n"
                                f"{page_content}"
                            )
                        })

                    except Exception as error:

                        messages.append({
                            "role": "user",
                            "content": (
                                "The webpage could not be read. "
                                "You may use the search results instead.\n\n"
                                f"Error: {error}"
                            )
                        })

                else:

                    messages.append({
                        "role": "user",
                        "content": (
                            "No web search results were found. "
                            "Answer only if you have enough information."
                        )
                    })


            # -------------------------
            # Unknown tool
            # -------------------------

            else:

                messages.append({
                    "role": "tool",
                    "content": (
                        f"Unknown tool: {function_name}"
                    )
                })


        # -------------------------
        # Ask Qwen again
        # -------------------------

        response = chat(
            model="qwen3:4b",
            messages=messages,
            tools=tools
        )


    # -------------------------
    # Final answer
    # -------------------------

    final_response = generate_final_answer()

    print("\nAI:", final_response.message.content)

    messages.append({
        "role": "assistant",
        "content": final_response.message.content
    })