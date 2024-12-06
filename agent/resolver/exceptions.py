

class ResolverAgentException(Exception):

    @staticmethod
    def signature_validation_failure(tag : str):
        return ResolverAgentException(f"Signature validation failed for message delivered to {tag}")
