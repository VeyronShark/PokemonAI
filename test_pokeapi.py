import requests

url = "https://pokeapi.co/api/v2/pokemon/charizard"

response = requests.get(url)

if response.status_code == 200:
    pokemon = response.json()

    print("Name:", pokemon["name"])
    print("Height:", pokemon["height"])
    print("Weight:", pokemon["weight"])
    print("Types:")

    for type_data in pokemon["types"]:
        print("-", type_data["type"]["name"])
else:
    print("Failed to contact PokéAPI")