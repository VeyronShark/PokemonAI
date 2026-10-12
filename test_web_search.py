from web_search import web_search


results = web_search(
    "Pokemon World Championship"
)

for result in results:

    print("\nTitle:", result["title"])
    print("URL:", result["url"])
    print("Snippet:", result["snippet"])