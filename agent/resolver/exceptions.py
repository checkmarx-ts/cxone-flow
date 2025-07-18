

class ResolverAgentException(Exception):

    @staticmethod
    def signature_validation_failure(tag : str):
        return ResolverAgentException(f"Signature validation failed for message delivered to {tag}")

    @staticmethod
    def type_mismatch_exception(expected_type, service_type : str):
        return ResolverAgentException(f"Expected pickled type {expected_type} but found type {service_type}, can not proceed.")
