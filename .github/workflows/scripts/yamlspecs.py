import requests, re, json, sys
from pathlib import Path


def main():

    if not len(sys.argv) > 1:
        print("Provide an output path")
        exit(1)

    out_path = Path(sys.argv[1])

    if out_path is None or not out_path.exists():
        print("Invalid output path")
        exit(1)

    base_url = "https://ast.checkmarx.net"

    spec_index = requests.get(f"{base_url}/spec/v1/swagger-starter.js")
    if not spec_index.ok:
        print(f"YAML index response: {spec_index}")
        exit(1)


    regex = re.compile("urls.+(\\[.*\\])")
    urls = regex.findall(spec_index.text)
    for found in urls:
        url_list = json.loads(found)
        for entry in url_list:
            if entry.get("url") is not None:
                spec = requests.get(base_url + entry.get("url"))
                if not spec.ok:
                    print(f"Failed to get {entry.get('url')}")
                    exit(1)

                yaml_path = Path(entry.get("url"))

                with open(out_path / yaml_path.name, "wt") as yaml_file:
                    yaml_file.write(spec.text)

if __name__ == "__main__":
    main()

