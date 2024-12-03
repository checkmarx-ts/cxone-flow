import hmac
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
from cryptography.hazmat.primitives.hashes import SHA3_512
from cryptography.hazmat.primitives.asymmetric.padding import PSS, MGF1
from cryptography.hazmat.primitives.asymmetric.ec import ECDSA, EllipticCurvePrivateKey, EllipticCurvePublicKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from typing import Callable, Union, Any


class signature:

    @staticmethod
    def hmac(algorithm_name, secret, payload) -> str:
        h = hmac.new(bytes(secret, 'UTF-8'), payload, algorithm_name)
        return str(h.hexdigest())


class AsymmetricSignatureVerifier:

    _hash_alg = SHA3_512()
    _ecda_hash_alg = ECDSA(_hash_alg)
    _padding = PSS(MGF1(_hash_alg), PSS.MAX_LENGTH)

    @staticmethod
    def from_public_key(public_key : bytearray):
        self = AsymmetricSignatureVerifier()

        key = load_pem_public_key(public_key, None)

        if isinstance(key, EllipticCurvePublicKey):
            self._internal_init(key, self._ec_verify)
        elif isinstance(key, RSAPublicKey):
            self._internal_init(key, self._rsa_verify)
        else:
            raise TypeError(key)
        
        return self

    def _internal_init(self, public_key : Union[RSAPublicKey, EllipticCurvePublicKey], verifier : Callable[[bytearray, bytearray], None]):
        self.__public_key = public_key
        self.__verifier = verifier

    def verify(self, signature : bytearray, data : bytearray) -> None:
        self.__verifier(signature, data)

    def _ec_verify(self, signature : bytearray, data : bytearray) -> None:
        self.__public_key.verify(signature, data, AsymmetricSignatureVerifier._ecda_hash_alg)

    def _rsa_verify(self, signature : bytearray, data : bytearray) -> None:
        self.__public_key.verify(signature, data, AsymmetricSignatureVerifier._padding, AsymmetricSignatureVerifier._hash_alg)


class AsymmetricSignatureSignerVerifier(AsymmetricSignatureVerifier):

    @staticmethod
    def from_private_key(private_key : bytearray) -> Any:

        self = AsymmetricSignatureSignerVerifier()

        self.__private_key = load_pem_private_key(private_key, None)

        if isinstance(self.__private_key, EllipticCurvePrivateKey):
            self._internal_init(self.__private_key.public_key(), self._ec_verify)
            self.__signer = self._ec_sign
        elif isinstance(self.__private_key, RSAPrivateKey):
            self._internal_init(self.__private_key.public_key(), self._rsa_verify)
            self.__signer = self._rsa_sign
        else:
            raise TypeError(self.__private_key)
        
        return self
        

    def sign(self, data : bytearray) -> bytearray:
        return self.__signer(data)

    def _ec_sign(self, data : bytearray) -> bytearray:
        return self.__private_key.sign(data, AsymmetricSignatureVerifier._ecda_hash_alg)

    def _rsa_sign(self, data : bytearray) -> bytearray:
        return self.__private_key.sign(data, AsymmetricSignatureVerifier._padding, AsymmetricSignatureVerifier._hash_alg)

