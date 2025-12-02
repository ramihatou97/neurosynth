import re

text = "42.2 Patient Selection"
pattern = r'^\s*(?:[0-9]+(?:\.[0-9]+)*\.?|[IVX]+\.)?\s*Patient\s+Selection\s*$'

match = re.match(pattern, text)
print(f"Text: '{text}'")
print(f"Pattern: '{pattern}'")
print(f"Match: {match}")

if match:
    print("MATCHED!")
else:
    print("NO MATCH")
