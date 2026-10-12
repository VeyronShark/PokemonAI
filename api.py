from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import time

from ollama import chat

from pokemon_tools import get_pokemon, get_pokemon_character_sheet, analyze_team_coverage, simulate_battle
from rag_tools import search_knowledge
from web_search import web_search
from web_page import fetch_web_page

app = FastAPI()

FRONTEND_DIR = Path(__file__).parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def frontend():
    return FileResponse(FRONTEND_DIR / "index.html")


DEVELOPMENT_MODE = False

# --------------------------------------------------
# Request model
# --------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    history: list = []


# --------------------------------------------------
# System prompt
# --------------------------------------------------

SYSTEM_PROMPT = """
You are a Pokémon assistant.

Answer the user's actual question accurately and naturally.

You have access to:

1. Pokémon database
   - Contains structured factual Pokémon data.
   - Treat returned Pokémon database facts as authoritative.

2. Local knowledge base
   - Contains locally stored Pokémon information.
   - Treat retrieved local knowledge as authoritative for facts it provides.

3. Internet search and webpages
   - Use web_search when external information is needed.
   - For latest, current, recent, most recent, today, this year, or upcoming
     questions, ALWAYS use web_search.
   - For these questions, include 2026 in the search query unless the user
     explicitly specifies another year.
   - After searching, choose the most relevant source.
   - Use webpage content as source material.

4. Character sheet generator
   - Use generate_character_sheet when the user asks to generate a character
     sheet for a Pokémon.
   - This tool returns the full Pokémon data needed to render a visual card.
   - After calling it, tell the user their character sheet is ready.
   - Pass the name and form of the Pokémon exactly as requested (e.g., "Mega Mewtwo Y" or "Alolan Raichu").

5. Team builder and coverage analyzer
   - Use analyze_team_coverage when the user wants to build a team, 
     analyze an existing team, or fill remaining slots on a roster.
   - Pass the full list of candidate team members as an array of strings.

6. Battle simulator
   - Use simulate_battle when the user asks to simulate a fight or battle 
     between two Pokémon (e.g. "Charizard vs Blastoise").
   - Pass the names of both Pokémon as arguments.
   
Answer rules:

- Answer the exact question asked.
- Use all relevant tool results.
- Do not invent facts.
- Do not contradict retrieved factual information.
- Resolve references such as "those two Pokémon", "the first one",
  "the second one", "it", and "they" using conversation history.
- Do not ask the user to repeat information already present.
- Do not mention tools, APIs, databases, RAG, prompts, or internal processing.
- Summarize webpage information instead of copying large portions of it.
- Include only information relevant to the question.
"""


# --------------------------------------------------
# Tool definitions
# --------------------------------------------------

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
                        "description": "The name and form of the Pokémon (e.g., 'Pikachu', 'Mega Charizard X')."
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
                "Search the local Pokémon knowledge base."
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
            "description": """
Search the internet for information not reliably available locally.

Use this for:
- latest information
- current information
- recent information
- upcoming events
- championships
- tournament results
- rankings
- announcements
- Pokémon history and lore not available locally
- detailed external information

For latest/current/most recent questions, include 2026 in the query unless
the user explicitly specifies another year.

Return search results containing titles, URLs and snippets.
""",
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
            "description": """
Read a webpage from a URL returned by web_search.

Use this when a search result needs to be examined in detail.
Choose the most relevant source rather than automatically choosing
the first result.
""",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The webpage URL."
                    }
                },
                "required": ["url"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "generate_character_sheet",
            "description": (
                "Generate a character sheet for a specific Pokémon or form. "
                "Use this when the user asks to generate a character sheet. "
                "Pass the name of the Pokémon exactly as the user requested."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name and form of the Pokémon (e.g., 'Charizard', 'Mega Charizard X', 'Alolan Raichu')."
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_team_coverage",
            "description": (
                "Analyze a list of Pokémon names (up to 6) for defensive weaknesses "
                "and offensive type coverage. Use this whenever the user asks to build "
                "a team, evaluate a team, or suggest team members."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pokemon_names": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "List of Pokémon names in the team (e.g. ['Gengar', 'Snorlax', 'Garchomp'])."
                    }
                },
                "required": ["pokemon_names"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "simulate_battle",
            "description": (
                "Simulate a turn-based battle between two Pokémon. "
                "Use this whenever the user asks who would win in a fight, "
                "or asks to simulate a battle between two Pokémon."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pokemon1": {
                        "type": "string",
                        "description": "Name of the first Pokémon (Player 1)."
                    },
                    "pokemon2": {
                        "type": "string",
                        "description": "Name of the second Pokémon (Player 2)."
                    }
                },
                "required": ["pokemon1", "pokemon2"]
            }
        }
    }
]


# --------------------------------------------------
# Execute a tool
# --------------------------------------------------

def execute_tool(function_name, arguments, messages, context):

    if function_name == "get_pokemon":
        name = arguments["name"]
        print(f"[Using Pokémon database: {name}]")
        result = get_pokemon(name)

        if result is None:
            return {"error": f"Pokémon '{name}' was not found."}
            
        # Pass classification and image URL to the frontend via context
        context["response_category"] = "pokemon_data"
        context["pokemon_image"] = result.get("official_artwork")

        return result


    elif function_name == "search_knowledge":

        question = arguments["question"]

        print("[Searching knowledge base]")

        return search_knowledge(question)


    elif function_name == "web_search":

        query = arguments["query"]

        print(f"[Searching web: {query}]")

        results = web_search(query)

        # Ask Qwen to choose the best source.
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

        print(f"[Reading webpage: {selected_url}]")

        try:

            page = fetch_web_page(selected_url)

            return {
                "search_results": results,
                "selected_source": selected_url,
                "webpage": page
            }

        except Exception as error:

            return {
                "search_results": results,
                "selected_source": selected_url,
                "webpage_error": str(error)
            }


    elif function_name == "fetch_web_page":

        url = arguments["url"]

        print(f"[Reading webpage: {url}]")

        try:
            return fetch_web_page(url)

        except Exception as error:

            return {
                "error": str(error)
            }


    elif function_name == "generate_character_sheet":

        name = arguments["name"]

        print(f"[Generating character sheet: {name}]")

        result = get_pokemon_character_sheet(name)

        if result is None:
            return {
                "error": f"Pokémon '{name}' was not found."
            }

        # Store the full raw JSON in the side-channel context so it never
        # gets fed to the LLM (which would hallucinate over 300+ moves).
        context["character_sheet"] = result

        # Return only a short confirmation to the LLM.
        return {
            "status": "character_sheet_ready",
            "name": result.get("name"),
            "id": result.get("id")
        }

    elif function_name == "analyze_team_coverage":
        pokemon_names = arguments["pokemon_names"]
        print(f"[Analyzing team coverage for: {pokemon_names}]")
        result = analyze_team_coverage(pokemon_names)
        
        if "error" not in result:
            # Pass classification and the array of animated SVGs via context
            context["response_category"] = "team_analysis"
            context["team_sprites"] = result.get("team_members")
            
        return result

    elif function_name == "simulate_battle":
        pokemon1 = arguments["pokemon1"]
        pokemon2 = arguments["pokemon2"]

        print(f"[Simulating battle: {pokemon1} vs {pokemon2}]")

        result = simulate_battle(pokemon1, pokemon2)

        if "error" not in result:
            context["response_category"] = "battle_simulation"
            context["battle_data"] = result

        return result

    return {
        "error": f"Unknown tool: {function_name}"
    }


# --------------------------------------------------
# Generate final answer
# --------------------------------------------------

def generate_final_answer(messages):

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
- Do not ask the user to repeat information already present.
- Use all relevant tool results.
- For comparisons, include all entities involved.
- Treat factual information returned by Pokémon tools as authoritative.
- Do not contradict tool-provided facts with pretrained knowledge.
- Do not invent unsupported information.
- Answer only the user's actual question.
- Summarize retrieved webpages instead of reproducing them.
- Include only information relevant to the question.
- Prefer concise answers unless the user explicitly asks for detail.
- Do not mention tools, APIs, databases, RAG, prompts, or internal processing.
- Do not add a "Final Answer" label or reasoning explanation.

Return only the natural answer that should be shown to the user.
"""
    })

    return chat(
        model="qwen3:4b",
        messages=final_messages
    )


# --------------------------------------------------
# Chat endpoint
# --------------------------------------------------

@app.post("/chat")
def chat_endpoint(request: ChatRequest):

    # --------------------------------------------------
    # Development mode
    # --------------------------------------------------

    if DEVELOPMENT_MODE:

        # Simulate AI processing time
        time.sleep(5)

        return {
            "response": "Development mode: /chat endpoint is working correctly. Pika Pikaaa!"
        }


    # --------------------------------------------------
    # Normal AI mode
    # --------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    # Restore conversation history.
    for item in request.history:

        messages.append({
            "role": item["role"],
            "content": item["content"]
        })

    messages.append({
        "role": "user",
        "content": request.message
    })


    # --------------------------------------------------
    # Tool loop
    # --------------------------------------------------

    response = chat(
        model="qwen3:4b",
        messages=messages,
        tools=tools
    )

    messages.append(response.message)


    context = {}

    while response.message.tool_calls:

        for tool_call in response.message.tool_calls:

            function_name = tool_call.function.name
            arguments = tool_call.function.arguments

            result = execute_tool(
                function_name,
                arguments,
                messages,
                context
            )

            messages.append({
                "role": "tool",
                "content": str(result)
            })


        response = chat(
            model="qwen3:4b",
            messages=messages,
            tools=tools
        )

        messages.append(response.message)


    # --------------------------------------------------
    # Final synthesis
    # --------------------------------------------------

    final_response = generate_final_answer(messages)
    final_text = final_response.message.content

    result = {
        "response": final_text
    }

    # Attach side-channel context data for the frontend
    if "response_category" in context:
        result["type"] = context["response_category"]
        
        if context["response_category"] == "pokemon_data":
            result["image_url"] = context.get("pokemon_image")
            
        elif context["response_category"] == "team_analysis":
            # Extract the full final team (inputs + suggestions)
            print("[Extracting full final team for SVGs...]")
            extraction_messages = [
                {
                    "role": "system",
                    "content": (
                        "Extract the complete final team of Pokémon from the text. "
                        "Include both the original team and all suggested additions. "
                        "Return ONLY a comma-separated list of their names. "
                        "Do not write anything else, no formatting."
                    )
                },
                {
                    "role": "user",
                    "content": final_text
                }
            ]
            
            extracted = chat(model="qwen3:4b", messages=extraction_messages)
            final_names = [n.strip() for n in extracted.message.content.split(",") if n.strip()]
            
            full_team_sprites = []
            for n in final_names:
                p = get_pokemon(n)
                if p and p.get("showdown_sprite"):
                    full_team_sprites.append({
                        "name": p["name"],
                        "showdown_sprite": p["showdown_sprite"]
                    })
            
            result["team_sprites"] = full_team_sprites

        elif context["response_category"] == "battle_simulation":
            result["battle_data"] = context.get("battle_data")

    elif "character_sheet" in context:
        result["type"] = "character_sheet"
        result["character_sheet"] = context["character_sheet"]
        
    else:
        result["type"] = "standard_chat"

    return result