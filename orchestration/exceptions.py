class OrchestrationException(BaseException):
    @staticmethod
    def from_response(response):
        return OrchestrationException(
            f"Method: {response.request.method} Url: {response.request.url} Status: {response.status_code} Body: {response.text}"
        )
