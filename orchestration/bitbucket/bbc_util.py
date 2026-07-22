import urllib3


def remove_auth_from_url(url: str) -> str:
    href = urllib3.util.parse_url(url)

    return str(
        urllib3.util.Url(
            scheme=href.scheme,
            host=href.host,
            port=href.port,
            path=href.path,
            query=href.query,
            fragment=href.fragment,
        )
    )
