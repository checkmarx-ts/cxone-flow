from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey, EllipticCurvePublicKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from .exceptions import KickoffClientException


def get_signature_alg(key):
    if isinstance(key, EllipticCurvePrivateKey) or isinstance(key, EllipticCurvePublicKey):
        return "ES256"
    elif isinstance(key, RSAPrivateKey) or isinstance(key, RSAPublicKey):
        return "RS256"
    elif isinstance(key, Ed25519PrivateKey) or isinstance(key, Ed25519PublicKey):
        return "EdDSA"
    else:
        raise KickoffClientException(f"JWT algorithm unsupported for private key parameters or type {type(key)}.")
