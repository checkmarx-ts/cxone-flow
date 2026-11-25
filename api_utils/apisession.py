from _agent import __agent__
from requests import Response
from requests import request
from requests.exceptions import ProxyError
from typing import Dict, Union, Any
import logging, asyncio, random
from api_utils import AuthFactory
from api_utils.auth_factories import EventContext
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone


class SCMAuthException(Exception):
    pass


class RetriesExhausted(Exception):
    pass


class APISession:

    RATE_LIMIT_HEADERS = [
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-used",
        "x-ratelimit-reset",
        "x-ratelimit-resource",
        "x-ratelimit-delay",
        "x-ratelimit-cost",
        "retry-after",
    ]

    RL_RETRY_DELAY_HEADERS = ["retry-after", "x-ratelimit-reset", "x-ratelimit-delay"]

    DEFAULT_RL_DELAY_S = 60
    MAXIMUM_RL_DELAY_S = 180

    @classmethod
    def log(clazz) -> logging.Logger:
        return logging.getLogger(clazz.__name__)

    def __init__(
        self,
        api_endpoint: str,
        auth: AuthFactory,
        timeout: int = 60,
        retries: int = 3,
        retry_delay: int = 30,
        proxies: Dict = None,
        ssl_verify: Union[bool, str] = True,
    ):

        self.__headers = {"User-Agent": __agent__}

        self.__api_endpoint = api_endpoint
        self.__timeout = timeout
        self.__retries = retries
        self.__retry_delay = retry_delay

        self.__verify = ssl_verify
        self.__proxies = proxies
        self.__auth_factory = auth

    @staticmethod
    def form_api_endpoint(base_endpoint: str, suffix: str):
        ret = base_endpoint.rstrip("/")
        if suffix is not None and len(suffix) > 0:
            ret = f"{ret}/{suffix.lstrip("/").rstrip("/")}"
        return ret

    @property
    def api_endpoint(self):
        return self.__api_endpoint

    def __concat_path_to_endpoint(self, path: str):
        return self.api_endpoint.rstrip("/") + "/" + path.lstrip("/")

    async def exec(
        self,
        event_context: EventContext,
        method: str,
        path: str,
        query: Dict = None,
        body: Any = None,
        extra_headers: Dict = None,
        url_vars: Dict = None,
    ) -> Response:
        url = self.__concat_path_to_endpoint(path)
        if url_vars is not None:
            for var in url_vars.keys():
                url = url.replace(f":{var}", url_vars[var])

        headers = dict(self.__headers)
        if not extra_headers is None:
            headers.update(extra_headers)

        prepStr = f"[{method} {url}]"

        for tryCount in range(0, self.__retries):

            try:
                APISession.log().debug(f"Executing: {prepStr} #{tryCount}")
                response = await asyncio.to_thread(
                    request,
                    method=method,
                    url=url,
                    params=query,
                    data=body,
                    headers=headers,
                    auth=await self.__auth_factory.get_auth(
                        event_context, tryCount > 0
                    ),
                    timeout=self.__timeout,
                    proxies=self.__proxies,
                    verify=self.__verify,
                )
            except ProxyError as pex:
                APISession.log().error(pex)
                await asyncio.sleep(random.randint(1, self.__retry_delay))
                continue

            logStr = f"{response.status_code}: {response.reason} {prepStr}"
            APISession.log().debug(f"Response #{tryCount}: {logStr} : {response.text}")

            if not response.ok:
                if response.status_code == 401:
                    APISession.log().error(
                        f"{prepStr} : Raising authorization exception, not retrying."
                    )
                    raise SCMAuthException(logStr)
                elif response.status_code in [403, 429]:
                    rl_headers = {
                        x: response.headers[x].lower()
                        for x in response.headers.keys()
                        if x.lower() in APISession.RATE_LIMIT_HEADERS
                    }
                    delay_headers = {
                        x: rl_headers[x]
                        for x in rl_headers.keys()
                        if x in APISession.RL_RETRY_DELAY_HEADERS
                    }

                    if len(delay_headers.keys()) == 0 and response.status_code == 403:
                        APISession.log().error(
                            f"{prepStr} : Action is not authorized for the API user."
                        )
                        raise SCMAuthException(logStr)
                    else:
                        calculated_delays = []
                        for header in delay_headers:
                            calc_delay = APISession.__time_conversion_map[header](
                                rl_headers[header]
                            )
                            if calc_delay > 0:
                                calculated_delays.append(calc_delay)

                        min_delay = min(calculated_delays)
                        delay_s = (
                            min_delay
                            if min_delay > 0
                            else APISession.DEFAULT_RL_DELAY_S
                        )

                        if APISession.log().isEnabledFor(logging.DEBUG):
                            header_strings = [
                                f"{x}:{rl_headers[x]}" for x in rl_headers.keys()
                            ]
                            APISession.log().debug(
                                f"Throttling delay of {delay_s}s: {' '.join(header_strings)}"
                            )

                        await asyncio.sleep(delay_s)

                        APISession.log().debug(
                            f"{logStr} retry after throttling: Attempt {tryCount}"
                        )

                else:
                    APISession.log().error(f"{logStr} : Attempt {tryCount}")
                    await asyncio.sleep(random.randint(1, self.__retry_delay))
            else:
                return response

        raise RetriesExhausted(f"Retries exhausted for {prepStr}")

    @staticmethod
    def __convert_retry_after_to_seconds(value: str) -> int:
        try:
            dt = parsedate_to_datetime(value)
            return min(
                (dt - datetime.now(timezone.utc)).seconds, APISession.MAXIMUM_RL_DELAY_S
            )
        except ValueError:
            pass

        try:
            return min(int(value), APISession.MAXIMUM_RL_DELAY_S)
        except (ValueError, TypeError):
            return APISession.DEFAULT_RL_DELAY_S

    @staticmethod
    def __convert_utc_epoch_to_seconds(value: str) -> int:
        try:
            return min(
                (
                    datetime.fromtimestamp(int(value), timezone.utc)
                    - datetime.now(timezone.utc)
                ).seconds,
                APISession.MAXIMUM_RL_DELAY_S,
            )
        except (ValueError, TypeError):
            return APISession.DEFAULT_RL_DELAY_S

    __time_conversion_map = {
        "retry-after": __convert_retry_after_to_seconds,
        "x-ratelimit-reset": __convert_utc_epoch_to_seconds,
        "x-ratelimit-delay": int,
    }
