import sys
import json
from typing import List

# Converts JSON structure to Latex release notes
# Assumes a dictionary where keys are the release version, value of each key
# is a list of strings.  Order of keys in file is the order the latex will be generated.

def format_latex(text : str):
  # Escape underscores
  fixed = text.replace("_", "\\_")

  # Backticks => \texttt
  converted = ""
  toggle_off = False
  for pos in range(0, len(fixed)):
    if fixed[pos] == "`":
      if toggle_off:
        converted += "}"
        toggle_off = False
      else:
        toggle_off = True
        converted += "\\texttt{"
    else:
      converted += fixed[pos]

  return converted



def write_section(fp, version : str, items : List[str]) -> None:
  fp.write(f"\\section{{{version}}}\n")
  fp.write("\\begin{itemize}\n")
  for line in items:
    fp.write(f"\t\\item {format_latex(line)}\n")
  fp.write("\\end{itemize}\n")

if __name__ == "__main__":
  json_file_path = sys.argv[1]
  latex_out_path = sys.argv[2]

  with open(json_file_path, "rt", encoding="UTF-8") as json_in:
    rn_json = json.load(json_in)


  with open(latex_out_path, "wt", encoding="UTF-8") as tex_out:
    for version in rn_json:
      write_section(tex_out, version, rn_json[version])
