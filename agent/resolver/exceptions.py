

class ResolverAgentException(Exception):

    @staticmethod
    def signature_validation_failure(tag : str):
        return ResolverAgentException(f"Signature validation failed for message delivered to {tag}")

    @staticmethod
    def cloner_type_exception(cloner_type : str):
        return ResolverAgentException(f"Pickled cloner is of type {cloner_type}, can not proceed.")
