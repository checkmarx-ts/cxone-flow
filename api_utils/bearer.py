from requests.auth import AuthBase

class HTTPBearerAuth(AuthBase):
    def __init__(self, token):
        AuthBase.__init__(self)
        self.__token = token

    def __call__(self, r):
        r.headers["Authorization"] = f"Bearer {self.__token}"
        return r
