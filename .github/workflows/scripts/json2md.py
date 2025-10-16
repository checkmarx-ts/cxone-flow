import sys
import json
from typing import List, Dict

# Converts JSON structure to Markdown release notes.
# Assumes a dictionary where keys are the release version, value of each key
# is a list of strings.  Order of keys in file is the order the markdown will be generated.
# The last argument can optionally match a key value and limit the output
# to content in that key value.

def output_items(items : List[str], prefix="") -> None:
  for item in items:
    sys.stdout.write(f"{prefix}* {item}\n")

def output_dict(d : Dict) -> None:
  for version in d:
    sys.stdout.write(f"**{version}**\n")
    output_items(d[version], "  ")

if __name__ == "__main__":
  json_file_path = sys.argv[1]

  with open(json_file_path, "rt", encoding="UTF-8") as json_in:
    rn_json = json.load(json_in)

  if len(sys.argv) > 2:
    if sys.argv[2] in rn_json.keys():
      output_items(rn_json[sys.argv[2]])
    else:
      sys.stdout.write("**No release notes available**")
  else:
    output_dict(rn_json)


