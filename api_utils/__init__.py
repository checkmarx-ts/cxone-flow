from .signatures import signature
from .auth_factories import AuthFactory, StaticAuthFactory
from requests.auth import HTTPBasicAuth
from .bearer import HTTPBearerAuth



def auth_basic(username, password) -> AuthFactory:
    return StaticAuthFactory(HTTPBasicAuth(username, password))

def auth_bearer(token) -> AuthFactory:
    return StaticAuthFactory(HTTPBearerAuth(token))

def verify_signature(signature_header, secret, body) -> bool:
    (algorithm, hash) = signature_header.split("=")

    import hashlib

    if not algorithm in hashlib.algorithms_available:
        return False

    generated_hash = signature.get(algorithm, secret, body)

    return generated_hash == hash


