from functools import lru_cache
import logging
from pathlib import Path
from time import perf_counter
from urllib.parse import urlparse

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import time

from ollama import chat

from pokemon_tools import get_pokemon, get_pokemon_character_sheet, analyze_team_coverage, simulate_battle
from rag_tools import search_knowledge
from web_search import web_search
from web_page import fetch_web_page

app = FastAPI()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("pokemonai")

FRONTEND_DIR = Path(__file__).parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.middleware("http")
async def log_http_requests(request: Request, call_next):
    started_at = perf_counter()
    logger.info("HTTP request started method=%s path=%s", request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "HTTP request failed method=%s path=%s duration_ms=%.1f",
            request.method,
            request.url.path,
            (perf_counter() - started_at) * 1000,
        )
        raise

    logger.info(
        "HTTP request completed method=%s path=%s status=%s duration_ms=%.1f",
        request.method,
        request.url.path,
        response.status_code,
        (perf_counter() - started_at) * 1000,
    )
    return response


@app.get("/")
def frontend():
    logger.info("Serving frontend index")
    return FileResponse(FRONTEND_DIR / "index.html")


@lru_cache(maxsize=128)
def fetch_sprite_image(url):
    response = requests.get(url, timeout=(5, 20))
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").split(";", 1)[0]
    if not content_type.startswith("image/"):
        raise ValueError("Upstream response is not an image")
    return response.content, content_type


@app.get("/sprite")
def sprite_image(url: str):
    parsed_url = urlparse(url)
    allowed_path = "/PokeAPI/sprites/master/sprites/pokemon/"
    if (
        parsed_url.scheme != "https"
        or parsed_url.hostname != "raw.githubusercontent.com"
        or not parsed_url.path.startswith(allowed_path)
        or ".." in parsed_url.path.split("/")
        or parsed_url.query
    ):
        raise HTTPException(status_code=400, detail="Unsupported sprite URL")

    try:
        content, content_type = fetch_sprite_image(url)
    except requests.exceptions.RequestException as error:
        logger.warning(
            "Sprite proxy request failed host=%s error_type=%s",
            parsed_url.hostname,
            type(error).__name__,
        )
        raise HTTPException(status_code=502, detail="Could not retrieve Pokémon sprite") from error
    except ValueError as error:
        logger.warning("Sprite proxy received invalid content host=%s", parsed_url.hostname)
        raise HTTPException(status_code=502, detail="Sprite source returned invalid image data") from error

    logger.info(
        "Sprite served host=%s content_type=%s bytes=%d",
        parsed_url.hostname,
        content_type,
        len(content),
    )
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )


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
   - For team building, pass only Pokémon the user explicitly selected as
     the starting core. Never invent additions for the tool arguments.
   - Keep every Pokémon the user chose; recommend additions, not replacements,
     unless the user explicitly asks for swaps.
   - Add exactly enough Pokémon to bring a partial roster to six.

6. Battle simulator
   - Use simulate_battle when the user asks to simulate a fight or battle 
     between two Pokémon (e.g. "Charizard vs Blastoise").
   - Pass the names of both Pokémon as arguments.
   - After a battle simulation is prepared, do not narrate or explain it.
     The only response text should be exactly:
     "Here is a battle simulation between <pokemon> and <pokemon>!"
   
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
                "Analyze up to 6 Pokémon explicitly selected by the user for defensive "
                "weaknesses and offensive type coverage. For a team-building request, "
                "pass only the user's starting Pokémon, not proposed additions."
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
    started_at = perf_counter()
    logger.info(
        "Tool started name=%s argument_fields=%s",
        function_name,
        sorted(arguments.keys()),
    )
    try:
        result = _execute_tool(function_name, arguments, messages, context)
    except Exception:
        logger.exception(
            "Tool failed name=%s duration_ms=%.1f",
            function_name,
            (perf_counter() - started_at) * 1000,
        )
        raise

    result_keys = sorted(result.keys()) if isinstance(result, dict) else None
    result_count = len(result) if isinstance(result, (list, tuple)) else None
    logger.info(
        "Tool completed name=%s result_type=%s result_keys=%s result_count=%s error=%s duration_ms=%.1f",
        function_name,
        type(result).__name__,
        result_keys,
        result_count,
        isinstance(result, dict) and "error" in result,
        (perf_counter() - started_at) * 1000,
    )
    return result


def _execute_tool(function_name, arguments, messages, context):

    if function_name == "get_pokemon":
        name = arguments["name"]
        logger.info("Looking up Pokémon data")
        result = get_pokemon(name)

        if result is None:
            return {"error": f"Pokémon '{name}' was not found."}
            
        # Pass classification and image URL to the frontend via context
        context["response_category"] = "pokemon_data"
        context["pokemon_image"] = result.get("official_artwork")

        return result


    elif function_name == "search_knowledge":

        question = arguments["question"]

        logger.info("Searching local knowledge base")

        return search_knowledge(question)


    elif function_name == "web_search":

        query = arguments["query"]

        logger.info("Searching web")

        results = web_search(query)
        logger.info("Web search completed result_count=%d", len(results))

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

        selection_response = call_model("web source selection", selection_messages)

        selected_url = (
            selection_response.message.content
            .strip()
            .strip("`")
            .strip()
        )

        logger.info(
            "Fetching selected webpage host=%s",
            urlparse(selected_url).hostname or "unknown",
        )

        try:

            page = fetch_web_page(selected_url)

            return {
                "search_results": results,
                "selected_source": selected_url,
                "webpage": page
            }

        except Exception as error:
            logger.exception("Selected webpage fetch failed")

            return {
                "search_results": results,
                "selected_source": selected_url,
                "webpage_error": str(error)
            }


    elif function_name == "fetch_web_page":

        url = arguments["url"]

        logger.info("Fetching requested webpage host=%s", urlparse(url).hostname or "unknown")

        try:
            return fetch_web_page(url)

        except Exception as error:
            logger.exception("Requested webpage fetch failed")

            return {
                "error": str(error)
            }


    elif function_name == "generate_character_sheet":

        name = arguments["name"]

        logger.info("Generating Pokémon character sheet")

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
        logger.info("Analyzing team coverage member_count=%d", len(pokemon_names))
        result = analyze_team_coverage(pokemon_names)
        
        if "error" not in result:
            # Keep the selected members and coverage facts for answer rendering.
            context["response_category"] = "team_analysis"
            context["team_sprites"] = result.get("team_members")
            context["team_analysis"] = result
            
        return result

    elif function_name == "simulate_battle":
        pokemon1 = arguments["pokemon1"]
        pokemon2 = arguments["pokemon2"]

        logger.info("Simulating battle")

        result = simulate_battle(pokemon1, pokemon2)

        if "error" not in result:
            context["response_category"] = "battle_simulation"
            context["battle_data"] = result

        return result

    return {
        "error": f"Unknown tool: {function_name}"
    }


def call_model(stage, messages, tools=None):
    started_at = perf_counter()
    logger.info(
        "Ollama call started stage=%s model=qwen3:4b message_count=%d tools_enabled=%s",
        stage,
        len(messages),
        tools is not None,
    )
    try:
        response = chat(model="qwen3:4b", messages=messages, **({"tools": tools} if tools is not None else {}))
    except Exception:
        logger.exception(
            "Ollama call failed stage=%s duration_ms=%.1f",
            stage,
            (perf_counter() - started_at) * 1000,
        )
        raise

    tool_calls = getattr(response.message, "tool_calls", None) or []
    content = getattr(response.message, "content", None) or ""
    logger.info(
        "Ollama call completed stage=%s tool_call_count=%d response_chars=%d duration_ms=%.1f",
        stage,
        len(tool_calls),
        len(content),
        (perf_counter() - started_at) * 1000,
    )
    return response


# --------------------------------------------------
# Generate final answer
# --------------------------------------------------

def generate_final_answer(messages, additional_instruction=None):

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

    if additional_instruction:
        final_messages.append({
            "role": "system",
            "content": additional_instruction
        })

    return call_model("final answer synthesis", final_messages)


# --------------------------------------------------
# Chat endpoint
# --------------------------------------------------

@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    started_at = perf_counter()
    logger.info(
        "Chat request received message_chars=%d history_turns=%d development_mode=%s",
        len(request.message),
        len(request.history),
        DEVELOPMENT_MODE,
    )

    # --------------------------------------------------
    # Development mode
    # --------------------------------------------------

    if DEVELOPMENT_MODE:

        # Simulate AI processing time
        time.sleep(5)
        logger.info("Development-mode chat response ready")

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
    logger.info("Conversation assembled message_count=%d", len(messages))


    # --------------------------------------------------
    # Tool loop
    # --------------------------------------------------

    response = call_model("initial response", messages, tools)

    messages.append(response.message)

    context = {}
    tool_round = 0

    while response.message.tool_calls:
        tool_round += 1
        logger.info(
            "Tool round started round=%d tool_call_count=%d",
            tool_round,
            len(response.message.tool_calls),
        )

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

        logger.info("Tool round completed round=%d message_count=%d", tool_round, len(messages))
        response = call_model(f"tool round {tool_round}", messages, tools)

        messages.append(response.message)


    # --------------------------------------------------
    # Final synthesis
    # --------------------------------------------------

    is_battle = context.get("response_category") == "battle_simulation"
    battle_instruction = None
    if is_battle:
        battle_instruction = (
            "This is a battle simulation. Do not display narration, explanations, "
            "move descriptions, or any other text. Respond with only this exact "
            "sentence, replacing the placeholders with the two Pokémon names from "
            "the battle data: 'Here is a battle simulation between <pokemon> and "
            "<pokemon>!'"
        )

    team_instruction = None
    if context.get("response_category") == "team_analysis":
        analysis = context["team_analysis"]
        current_members = analysis.get("team_members", [])
        slots_remaining = max(0, 6 - analysis.get("team_size", len(current_members)))
        selected_names = ", ".join(member["name"] for member in current_members)
        team_instruction = (
            f"The user-selected starting Pokémon are: {selected_names}. Keep all of them; "
            "do not replace or remove any. "
            f"Recommend exactly {slots_remaining} additional distinct Pokémon so the final "
            "roster contains six Pokémon total. Do not say the team is full unless six "
            "Pokémon were provided. Clearly list the complete six-Pokémon roster and "
            "briefly explain how any additions complement the selected core. Use the "
            "coverage analysis, and do not claim that every uncovered type is covered."
        )

    final_instruction = "\n".join(
        instruction for instruction in (battle_instruction, team_instruction) if instruction
    ) or None
    final_response = generate_final_answer(messages, final_instruction)
    final_text = final_response.message.content
    logger.info("Final answer generated response_chars=%d", len(final_text))

    if is_battle:
        battle_data = context["battle_data"]
        pokemon_one = battle_data["player_one"]["name"].replace("-", " ").title()
        pokemon_two = battle_data["player_two"]["name"].replace("-", " ").title()
        final_text = f"Here is a battle simulation between {pokemon_one} and {pokemon_two}!"
        logger.info("Battle response constrained to intro sentence")

    result = {
        "response": final_text
    }

    # Attach side-channel context data for the frontend
    if "response_category" in context:
        result["type"] = context["response_category"]
        
        if context["response_category"] == "pokemon_data":
            result["image_url"] = context.get("pokemon_image")
            
        elif context["response_category"] == "team_analysis":
            analysis = context["team_analysis"]
            current_members = analysis.get("team_members", [])
            slots_remaining = max(0, 6 - analysis.get("team_size", len(current_members)))
            full_team_sprites = list(current_members)

            if slots_remaining:
                logger.info("Extracting suggested team additions count=%d", slots_remaining)
                selected_names = ", ".join(member["name"] for member in current_members)
                extraction_messages = [
                    {
                        "role": "system",
                        "content": (
                            f"Extract exactly {slots_remaining} distinct Pokémon names that "
                            "the assistant recommended as additions in the response. Do not "
                            f"return any of these already-selected Pokémon: {selected_names}. "
                            "Return only a comma-separated list of names actually present in "
                            "the response. Do not include explanations or formatting."
                        )
                    },
                    {
                        "role": "user",
                        "content": final_text
                    }
                ]

                extracted = call_model("team addition extraction", extraction_messages)
                final_names = [
                    name.strip().strip(" -*")
                    for name in extracted.message.content.split(",")
                    if name.strip().strip(" -*")
                ][:slots_remaining]
                logger.info(
                    "Team addition extraction completed addition_count=%d expected_count=%d",
                    len(final_names),
                    slots_remaining,
                )

                existing_names = {member["name"].casefold() for member in full_team_sprites}
                for name in final_names:
                    pokemon = get_pokemon(name)
                    if not pokemon:
                        logger.warning("Could not resolve suggested team member name=%s", name)
                        continue
                    canonical_name = pokemon["name"]
                    if canonical_name.casefold() in existing_names:
                        continue
                    sprite = pokemon.get("showdown_sprite") or pokemon.get("official_artwork")
                    full_team_sprites.append({
                        "name": canonical_name,
                        "showdown_sprite": sprite
                    })
                    existing_names.add(canonical_name.casefold())

            result["team_sprites"] = full_team_sprites
            logger.info(
                "Final team sprites assembled sprite_count=%d expected_count=6",
                len(full_team_sprites),
            )
            if len(full_team_sprites) != 6 or any(
                not member.get("showdown_sprite") for member in full_team_sprites
            ):
                logger.error(
                    "Could not assemble a complete team response sprite_count=%d",
                    len(full_team_sprites),
                )
                raise HTTPException(
                    status_code=502,
                    detail="Could not assemble all six Pokémon for the recommended team.",
                )

        elif context["response_category"] == "battle_simulation":
            result["battle_data"] = context.get("battle_data")

    elif "character_sheet" in context:
        result["type"] = "character_sheet"
        result["character_sheet"] = context["character_sheet"]
        
    else:
        result["type"] = "standard_chat"

    logger.info(
        "Chat request completed response_type=%s response_chars=%d duration_ms=%.1f",
        result["type"],
        len(final_text),
        (perf_counter() - started_at) * 1000,
    )
    return result