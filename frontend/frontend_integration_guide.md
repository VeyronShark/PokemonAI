# Chat API Response Documentation

The `/chat` endpoint returns a JSON object for every user interaction. The frontend should read the `type` property to determine how to render the response.

There are 4 possible response types:

## 1. Standard Chat
**How to detect:** `type === "standard_chat"`

This is a generic conversational response. It happens during normal chat, web searches, or knowledge base queries. 
*   **Data provided:** Just the AI's text response.
*   **Suggested Rendering:** Standard chat bubble.

**Example Payload:**
```json
{
  "response": "Pikachu evolves into Raichu using a Thunder Stone.",
  "type": "standard_chat"
}
```

---

## 2. Pokémon Data (get_pokemon)
**How to detect:** `type === "pokemon_data"`

Triggered when the user asks for stats, types, or general info about a single Pokémon. 
*   **Data provided:** The AI's text response PLUS an `image_url` containing the high-res official artwork.
*   **Suggested Rendering:** A chat bubble accompanied by an image tag rendering the artwork.

**Example Payload:**
```json
{
  "response": "Charizard is a Fire/Flying type with high Special Attack...",
  "type": "pokemon_data",
  "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/6.png"
}
```

---

## 3. Team Analysis (analyze_team_coverage)
**How to detect:** `type === "team_analysis"`

Triggered when the user asks to build or evaluate a team.
*   **Data provided:** The AI's text response PLUS a `team_sprites` array. Each object in the array contains the Pokémon's name and a link to its animated Showdown SVG.
*   **Suggested Rendering:** A chat bubble, followed by a flexbox/grid displaying the animated SVGs of the team members being discussed.

**Example Payload:**
```json
{
  "response": "To cover your team's weakness to Electric, consider adding Garchomp...",
  "type": "team_analysis",
  "team_sprites": [
    {
      "name": "gengar",
      "showdown_sprite": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/94.gif"
    },
    {
      "name": "gyarados",
      "showdown_sprite": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/130.gif"
    }
  ]
}
```

---

## 4. Character Sheet (generate_character_sheet)
**How to detect:** `type === "character_sheet"`

Triggered when the user explicitly asks to generate a character sheet.
*   **Data provided:** A short text confirmation from the AI, PLUS the entire raw PokeAPI JSON object for that Pokémon.
*   **Suggested Rendering:** Render a rich UI card component using the stats, moves, abilities, and sprites found inside the `character_sheet` object.

**Example Payload:**
```json
{
  "response": "Your character sheet for Mega Mewtwo Y is ready!",
  "type": "character_sheet",
  "character_sheet": {
    "id": 10044,
    "name": "mewtwo-mega-y",
    "base_experience": 351,
    "stats": [...],
    "types": [...],
    "sprites": {...}
    // ... rest of the massive PokeAPI object
  }
}


```

## 5. Battle Simulation (`type: "battle_simulation"`)

### Detection
Check if `response.type === "battle_simulation"`.

### Payload Example
```json
{
  "response": "In a battle between Charizard and Blastoise, Blastoise holds a clear type advantage with super-effective Water-type moves like Hydro Pump...",
  "type": "battle_simulation",
  "battle_data": {
    "player_one": {
      "name": "charizard",
      "max_hp": 266,
      "back_sprite": "[https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/back/6.gif](https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/back/6.gif)",
      "moves": [
        {
          "name": "flamethrower",
          "power": 90,
          "type": "fire",
          "damage_class": "special",
          "damage_to_opponent": 42
        }
      ]
    },
    "player_two": {
      "name": "blastoise",
      "max_hp": 268,
      "front_sprite": "[https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/9.gif](https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/showdown/9.gif)",
      "moves": [
        {
          "name": "surf",
          "power": 90,
          "type": "water",
          "damage_class": "special",
          "damage_to_opponent": 118
        }
      ]
    }
  }
}