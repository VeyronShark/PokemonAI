import difflib
from functools import lru_cache
import logging
from time import perf_counter, sleep

import requests

logger = logging.getLogger("pokemonai.pokemon")


def _get_pokeapi(url, operation):
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        started_at = perf_counter()
        logger.info(
            "PokeAPI request started operation=%s attempt=%d/%d",
            operation,
            attempt,
            max_attempts,
        )
        try:
            response = requests.get(url, timeout=(5, 20))
        except requests.exceptions.RequestException:
            if attempt == max_attempts:
                logger.exception(
                    "PokeAPI request failed operation=%s attempts=%d duration_ms=%.1f",
                    operation,
                    attempt,
                    (perf_counter() - started_at) * 1000,
                )
                raise
            logger.warning(
                "PokeAPI connection error operation=%s attempt=%d; retrying",
                operation,
                attempt,
                exc_info=True,
            )
        else:
            if response.status_code not in {429, 500, 502, 503, 504}:
                logger.info(
                    "PokeAPI request completed operation=%s status=%d duration_ms=%.1f",
                    operation,
                    response.status_code,
                    (perf_counter() - started_at) * 1000,
                )
                return response

            if attempt == max_attempts:
                logger.error(
                    "PokeAPI request exhausted retries operation=%s status=%d attempts=%d",
                    operation,
                    response.status_code,
                    attempt,
                )
                return response
            logger.warning(
                "PokeAPI returned retryable status operation=%s status=%d attempt=%d; retrying",
                operation,
                response.status_code,
                attempt,
            )

        sleep(0.5 * (2 ** (attempt - 1)))


# Cache to store all valid PokeAPI slugs
VALID_POKEMON_SLUGS = []

def get_valid_pokemon_slugs():
    global VALID_POKEMON_SLUGS
    if not VALID_POKEMON_SLUGS:
        url = "https://pokeapi.co/api/v2/pokemon?limit=10000"
        response = _get_pokeapi(url, "load Pokémon index")
        if response.status_code == 200:
            VALID_POKEMON_SLUGS = [p["name"] for p in response.json()["results"]]
            logger.info("Pokémon index loaded entry_count=%d", len(VALID_POKEMON_SLUGS))
        else:
            logger.warning("Pokémon index request returned status=%d", response.status_code)
    return VALID_POKEMON_SLUGS

def find_best_pokemon_match(name):
    valid_slugs = get_valid_pokemon_slugs()
    # Strip out dots (e.g. Mr. Mime) and normalize
    normalized_name = name.lower().replace(" ", "-").replace("'", "").replace(".", "")
    
    parts = normalized_name.split("-")
    permutations = [
        normalized_name,
        "-".join(reversed(parts))
    ]
    
    # Handle forms like "mega aggron" -> ["mega", "aggron"] -> "aggron-mega"
    if len(parts) >= 2:
        permutations.append(f"{parts[1]}-{parts[0]}")
        
    # Handle forms like "mega mewtwo x" -> ["mega", "mewtwo", "x"] -> "mewtwo-mega-x"
    if len(parts) >= 3:
        permutations.append(f"{parts[1]}-{parts[0]}-{parts[2]}") 
        permutations.append(f"{parts[1]}-{parts[2]}-{parts[0]}") # For tauros-paldea-combat
        
    # 1. Try exact permutations first
    for perm in permutations:
        if perm in valid_slugs:
            return perm
            
    # 2. Fallback to fuzzy match
    for perm in permutations:
        matches = difflib.get_close_matches(perm, valid_slugs, n=1, cutoff=0.6)
        if matches:
            return matches[0]
            
    return None

def get_pokemon(name):
    best_match = find_best_pokemon_match(name)
    
    if not best_match:
        return None

    url = f"https://pokeapi.co/api/v2/pokemon/{best_match}"
    response = _get_pokeapi(url, "fetch Pokémon data")

    if response.status_code != 200:
        return None

    pokemon = response.json()
    
    # Safely extract deeply nested sprite URLs
    sprites = pokemon.get("sprites", {})
    other_sprites = sprites.get("other", {})
    
    official_artwork = other_sprites.get("official-artwork", {}).get("front_default")
    showdown_sprite = other_sprites.get("showdown", {}).get("front_default")

    return {
        "name": pokemon["name"],
        "height_decimetres": pokemon["height"],
        "weight_hectograms": pokemon["weight"],
        "types": [
            type_data["type"]["name"]
            for type_data in pokemon["types"]
        ],
        "abilities": [
            ability_data["ability"]["name"]
            for ability_data in pokemon["abilities"]
        ],
        "base_stats": {
            stat["stat"]["name"]: stat["base_stat"]
            for stat in pokemon["stats"]
        },
        "official_artwork": official_artwork,
        "showdown_sprite": showdown_sprite
    }

def get_pokemon_character_sheet(name):
    best_match = find_best_pokemon_match(name)
    
    if not best_match:
        return None
        
    url = f"https://pokeapi.co/api/v2/pokemon/{best_match}"
    response = _get_pokeapi(url, "fetch character sheet")
    
    if response.status_code == 200:
        return response.json()

    return None

# Standard Pokémon Type Effectiveness Chart
TYPE_CHART = {
    "normal": {"rock": 0.5, "ghost": 0, "steel": 0.5},
    "fire": {"fire": 0.5, "water": 0.5, "grass": 2.0, "ice": 2.0, "bug": 2.0, "rock": 0.5, "dragon": 0.5, "steel": 2.0},
    "water": {"fire": 2.0, "water": 0.5, "grass": 0.5, "ground": 2.0, "rock": 2.0, "dragon": 0.5},
    "electric": {"water": 2.0, "electric": 0.5, "grass": 0.5, "ground": 0, "flying": 2.0, "dragon": 0.5},
    "grass": {"fire": 0.5, "water": 2.0, "grass": 0.5, "poison": 0.5, "ground": 2.0, "flying": 0.5, "bug": 0.5, "rock": 2.0, "dragon": 0.5, "steel": 0.5},
    "ice": {"fire": 0.5, "water": 0.5, "grass": 2.0, "ice": 0.5, "ground": 2.0, "flying": 2.0, "dragon": 2.0, "steel": 0.5},
    "fighting": {"normal": 2.0, "ice": 2.0, "poison": 0.5, "flying": 0.5, "psychic": 0.5, "bug": 0.5, "rock": 2.0, "ghost": 0, "dark": 2.0, "steel": 2.0, "fairy": 0.5},
    "poison": {"grass": 2.0, "poison": 0.5, "ground": 0.5, "rock": 0.5, "ghost": 0.5, "steel": 0, "fairy": 2.0},
    "ground": {"fire": 2.0, "electric": 2.0, "grass": 0.5, "poison": 2.0, "flying": 0, "bug": 0.5, "rock": 2.0, "steel": 2.0},
    "flying": {"electric": 0.5, "grass": 2.0, "fighting": 2.0, "bug": 2.0, "rock": 0.5, "steel": 0.5},
    "psychic": {"fighting": 2.0, "poison": 2.0, "psychic": 0.5, "dark": 0, "steel": 0.5},
    "bug": {"fire": 0.5, "grass": 2.0, "fighting": 0.5, "poison": 0.5, "flying": 0.5, "psychic": 2.0, "ghost": 0.5, "dark": 2.0, "steel": 0.5, "fairy": 0.5},
    "rock": {"fire": 2.0, "ice": 2.0, "fighting": 0.5, "ground": 0.5, "flying": 2.0, "bug": 2.0, "steel": 0.5},
    "ghost": {"normal": 0, "psychic": 2.0, "ghost": 2.0, "dark": 0.5},
    "dragon": {"dragon": 2.0, "steel": 0.5, "fairy": 0},
    "dark": {"fighting": 0.5, "psychic": 2.0, "ghost": 2.0, "dark": 0.5, "fairy": 0.5},
    "steel": {"fire": 0.5, "water": 0.5, "electric": 0.5, "ice": 2.0, "rock": 2.0, "steel": 0.5, "fairy": 2.0},
    "fairy": {"fire": 0.5, "fighting": 2.0, "poison": 0.5, "dragon": 2.0, "dark": 2.0, "steel": 0.5}
}

ALL_TYPES = list(TYPE_CHART.keys())

def analyze_team_coverage(pokemon_names: list[str]):
    """Analyzes a team of up to 6 Pokémon for shared defensive weaknesses 
    and missing offensive type coverage."""
    team_data = []
    
    for name in pokemon_names:
        p_data = get_pokemon(name)
        if p_data:
            team_data.append(p_data)
    logger.info(
        "Team members resolved requested_count=%d found_count=%d",
        len(pokemon_names),
        len(team_data),
    )

    if not team_data:
        return {"error": "None of the provided Pokémon could be found."}

    defensive_weaknesses = {t: 0 for t in ALL_TYPES}
    offensive_coverage = set()
    
    # Store a sprite URL for each member for the frontend.
    team_members_info = []

    for member in team_data:
        team_members_info.append({
            "name": member["name"],
            "showdown_sprite": member.get("showdown_sprite") or member.get("official_artwork")
        })
        
        member_types = member["types"]
        
        for t in member_types:
            offensive_coverage.add(t)

        for atk_type in ALL_TYPES:
            multiplier = 1.0
            for def_type in member_types:
                mult_map = TYPE_CHART.get(atk_type, {})
                multiplier *= mult_map.get(def_type, 1.0)
            
            if multiplier > 1.0:
                defensive_weaknesses[atk_type] += 1

    major_weaknesses = [
        type_name for type_name, count in defensive_weaknesses.items() if count >= 1
    ]
    
    best_resistances = set()
    for weakness in major_weaknesses:
        for def_type in ALL_TYPES:
            if TYPE_CHART.get(weakness, {}).get(def_type, 1.0) < 1.0:
                best_resistances.add(def_type)

    uncovered_offensive_types = [
        t for t in ALL_TYPES if t not in offensive_coverage
    ]

    major_weaknesses.sort()
    best_resistances = sorted(list(best_resistances))
    uncovered_offensive_types.sort()

    slots_remaining = 6 - len(team_data)
    
    if slots_remaining > 0:
        slot_instruction = f"To make a full team of 6, you MUST suggest exactly {slots_remaining} more specific Pokémon."
    else:
        slot_instruction = "The team is already full (6 Pokémon)."

    if major_weaknesses:
        tip = (
            f"The current team is vulnerable to attacks of these types: {', '.join(major_weaknesses)}. "
            f"Prioritize additions whose typing resists or is immune to those attacks; "
            f"helpful defensive types include: {', '.join(best_resistances[:5])}. "
            f"Improve offensive coverage where practical. {slot_instruction}"
        )
    else:
        tip = f"Your team has great defensive synergy! {slot_instruction}"

    return {
        "team_members": team_members_info,
        "team_size": len(team_data),
        "defensive_weaknesses": major_weaknesses,
        "missing_offensive_types": uncovered_offensive_types,
        "recommendation_tip": tip
    }

import math

@lru_cache(maxsize=512)
def get_move_details(move_name):
    """Fetch base power, type, and damage class for a specific move from PokeAPI."""
    url = f"https://pokeapi.co/api/v2/move/{move_name.lower().replace(' ', '-')}"
    res = _get_pokeapi(url, "fetch move details")
    if res.status_code != 200:
        return None
    data = res.json()
    
    # Ignore status moves (moves with no base power)
    if not data.get("power"):
        return None
        
    return {
        "name": data["name"],
        "power": data["power"],
        "type": data["type"]["name"],
        "damage_class": data["damage_class"]["name"]  # 'physical' or 'special'
    }

def calculate_move_damage(attacker, defender, move):
    """Calculates exact damage using the official Level 50 Pokémon damage formula."""
    level = 50
    power = move["power"]
    
    # Match physical vs special attacking/defensive stats
    if move["damage_class"] == "physical":
        a = attacker["base_stats"].get("attack", 100)
        d = defender["base_stats"].get("defense", 100)
    else:
        a = attacker["base_stats"].get("special-attack", 100)
        d = defender["base_stats"].get("special-defense", 100)

    # 1. Base Damage Calculation
    base_damage = math.floor(math.floor((2 * level / 5 + 2) * power * a / d) / 50) + 2

    # 2. STAB (Same Type Attack Bonus)
    stab = 1.5 if move["type"] in attacker["types"] else 1.0

    # 3. Type Effectiveness Multiplier
    type_mult = 1.0
    for def_type in defender["types"]:
        type_mult *= TYPE_CHART.get(move["type"], {}).get(def_type, 1.0)

    # Final Damage (using neutral variance multiplier of 0.925)
    final_damage = math.floor(base_damage * stab * type_mult * 0.925)
    return max(1, final_damage)

def select_best_moveset(attacker_data, defender_data):
    """Fetch learned moves, filter damaging ones, and greedily pick the top 4."""
    # Pull raw Pokémon details to get the learnset
    best_match = find_best_pokemon_match(attacker_data["name"])
    res = _get_pokeapi(
        f"https://pokeapi.co/api/v2/pokemon/{best_match}",
        "fetch Pokémon learnset",
    )
    if res.status_code != 200:
        return []
    
    raw_pokemon = res.json()
    learned_moves = [m["move"]["name"] for m in raw_pokemon.get("moves", [])]
    logger.info("Pokémon learnset loaded learned_move_count=%d", len(learned_moves))

    damaging_moves = []
    
    # Cap move lookups to the first 25 learned moves to keep API execution snappy
    for move_name in learned_moves[:25]:
        try:
            details = get_move_details(move_name)
        except requests.exceptions.RequestException:
            logger.warning(
                "Skipping move after PokeAPI request failure move=%s",
                move_name,
                exc_info=True,
            )
            continue
        if details:
            details = details.copy()
            # Pre-calculate damage against opponent
            details["damage_to_opponent"] = calculate_move_damage(attacker_data, defender_data, details)
            damaging_moves.append(details)
    logger.info(
        "Damaging move candidates evaluated candidate_count=%d damaging_count=%d",
        min(len(learned_moves), 25),
        len(damaging_moves),
    )

    # Sort moves by damage output descending
    damaging_moves.sort(key=lambda x: x["damage_to_opponent"], reverse=True)

    # Pick top 4 moves with distinct types when possible
    selected = []
    used_types = set()
    for move in damaging_moves:
        if len(selected) == 4:
            break
        if move["type"] not in used_types or len(damaging_moves) < 4:
            selected.append(move)
            used_types.add(move["type"])

    # Fallback if fewer than 4 distinct types were found
    if len(selected) < 4:
        for move in damaging_moves:
            if len(selected) == 4:
                break
            if move not in selected:
                selected.append(move)

    return selected

def simulate_battle(pokemon1_name: str, pokemon2_name: str):
    """Builds a full battle simulation context between two Pokémon."""
    logger.info("Battle setup started")
    p1 = get_pokemon(pokemon1_name)
    p2 = get_pokemon(pokemon2_name)

    if not p1 or not p2:
        return {"error": "One or both Pokémon could not be found."}

    # Fetch raw sprites for back_default and front_default
    raw_p1 = _get_pokeapi(
        f"https://pokeapi.co/api/v2/pokemon/{find_best_pokemon_match(pokemon1_name)}",
        "fetch first battle sprite",
    ).json()
    raw_p2 = _get_pokeapi(
        f"https://pokeapi.co/api/v2/pokemon/{find_best_pokemon_match(pokemon2_name)}",
        "fetch second battle sprite",
    ).json()

    p1_back_sprite = raw_p1["sprites"]["other"].get("showdown", {}).get("back_default") or raw_p1["sprites"]["back_default"]
    p2_front_sprite = raw_p2["sprites"]["other"].get("showdown", {}).get("front_default") or raw_p2["sprites"]["front_default"]

    # Calculate optimal movesets and damage
    p1_moves = select_best_moveset(p1, p2)
    p2_moves = select_best_moveset(p2, p1)
    logger.info(
        "Battle setup completed first_move_count=%d second_move_count=%d",
        len(p1_moves),
        len(p2_moves),
    )

    return {
        "player_one": {
            "name": p1["name"],
            "max_hp": p1["base_stats"].get("hp", 100) * 2 + 110,  # Level 50 HP formula
            "back_sprite": p1_back_sprite,
            "moves": p1_moves
        },
        "player_two": {
            "name": p2["name"],
            "max_hp": p2["base_stats"].get("hp", 100) * 2 + 110,
            "front_sprite": p2_front_sprite,
            "moves": p2_moves
        }
    }