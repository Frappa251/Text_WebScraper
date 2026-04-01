from parsers.wikipedia_parser import parse_wikipedia

url = "https://en.wikipedia.org/wiki/Artificial_intelligence"
result = parse_wikipedia(url)

print("TITLE:")
print(result["title"])

print("\nHTML TEXT START:")
print(result["html_text"][:300])

print("\nPARSED TEXT START:")
print(result["parsed_text"][:1000])