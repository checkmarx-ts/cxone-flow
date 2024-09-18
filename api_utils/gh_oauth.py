from requests.auth import AuthBase
import logging


class GithubOauth(AuthBase):

    @staticmethod
    def log():
        return logging.getLogger("GithubOauth")

    def __init__(self, id, secret):
        pass

    def __call__(self, r):
        GithubOauth.log().debug(type(r))
        return r

