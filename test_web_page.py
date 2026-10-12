from web_page import fetch_web_page


url = "https://en.wikipedia.org/wiki/Pok%C3%A9mon_World_Championships"

result = fetch_web_page(url)

print("URL:")
print(result["url"])

print("\nPage content:")
print(result["content"][:5000])