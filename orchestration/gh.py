from .base import OrchestratorBase
from api_utils import signature
import logging

class GithubOrchestrator(OrchestratorBase):


    @staticmethod
    def log():
        return logging.getLogger("BitBucketDataCenterOrchestrator")

    @property
    def config_key(self):
        return "gh"

    @property
    def is_diagnostic(self) -> bool:
        return self.__isdiagnostic


    def __init__(self, headers : dict, webhook_payload : dict):
        OrchestratorBase.__init__(self, headers, webhook_payload)

        self.__isdiagnostic = False

        self.__event = self.get_header_key_safe('X-GitHub-Event') 

        if not self.__event is None and self.__event == "ping":
            self.__isdiagnostic = True
            return


    async def is_signature_valid(self, shared_secret : str) -> bool:
        sig = self.get_header_key_safe('X-Hub-Signature-256')
        if sig is None:
            GithubOrchestrator.log().warning("X-Hub-Signature-256 header is missing, rejecting.")
            return False
        
        hashalg,hash = sig.split("=")
        payload_hash = signature.get(hashalg, shared_secret, self._webhook_payload)

        return hash == payload_hash
