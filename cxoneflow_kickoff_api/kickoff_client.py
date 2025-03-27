import jwt, time, asyncio, logging, requests
from .exceptions import KickoffClientException
from .signature_alg import get_signature_alg
from cryptography.hazmat.primitives.serialization import load_ssh_private_key
from typing import Dict
from .kickoff_msgs import KickoffMsg, KickoffResponseMsg


class KickoffClient:

    __JWT_TIMEOUT = 600
    __JWT_JITTER = 60
    __SLEEP_SECONDS = 15
    __SLEEP_MAX_SECONDS = 180
    __SLEEP_REPORT_MOD = 3

    @classmethod
    def log(clazz) -> logging.Logger:
        return logging.getLogger(clazz.__name__)

    def __init__(self, private_ssh_key : str, private_key_password : str, 
                 cxoneflow_ko_url : str, user_agent : str, proxies : Dict[str, str] = None, ssl_verify : bool = True):
        self.__lock = asyncio.Lock()
        self.__pkey = load_ssh_private_key(private_ssh_key.encode("UTF-8"), private_key_password)
        self.__service_url = cxoneflow_ko_url
        self.__ssl_verify = ssl_verify
        self.__proxies = proxies
        self.__user_agent = user_agent
        self.__jwt = None
        self.__jwt_exp = None

    async def __get_jwt(self, force = False) -> str:
        async with self.__lock:
            if force or self.__jwt is None or self.__jwt_exp is None or int(time.time()) >= self.__jwt_exp - KickoffClient.__JWT_JITTER:
                self.log().debug("Renewing JWT")
                alg = get_signature_alg(self.__pkey)
                self.__jwt_exp = int(time.time()) + KickoffClient.__JWT_TIMEOUT

                payload = {
                    "exp" : self.__jwt_exp,
                    "alg" : alg
                }

                self.__jwt = jwt.encode(payload, self.__pkey, algorithm=alg)

        return self.__jwt
    
    async def __execute_request(self, msg : KickoffMsg) -> requests.Response:
        auth_retried = False
        auth_retry = True
        
        while auth_retry:
            auth_retry = not auth_retried

            headers = {
                "Authorization" : f"Bearer {await self.__get_jwt(auth_retried)}",
                "User-Agent" : self.__user_agent
            }

            resp = await asyncio.to_thread(requests.post, url=self.__service_url, 
                                        json=msg.to_dict(), headers=headers, proxies=self.__proxies, verify=self.__ssl_verify)

            if resp.status_code == 401 and not auth_retried:
                auth_retried = True
            else:
                return resp


    async def kickoff_scan(self, msg : KickoffMsg) -> KickoffResponseMsg:

        cur_sleep_delay = KickoffClient.__SLEEP_SECONDS
        retry_count = 0

        while True:
            self.log().debug(f"Kicking off scan: {msg}")

            resp = await self.__execute_request(msg)

            if resp.ok or resp.status_code in [299, 429]:
                resp_msg = KickoffResponseMsg(**(resp.json()))
            else:
                resp_msg = None

            if resp.status_code == 201:
                self.log().debug(f"Scan started: {resp_msg.to_json()}")
                return resp_msg
            elif resp.status_code == 299:
                self.log().debug(f"The server indicated a kickoff scan is already running or has finished for {msg}")
                return resp_msg
            elif resp.status_code == 429:
                if retry_count % KickoffClient.__SLEEP_REPORT_MOD == 0:
                    self.log().info(f"The server indicated that too many concurrent scans are running." + 
                                    f"Currently running: {len(resp_msg.running_scans)}. Sleeping for {cur_sleep_delay} seconds.")

                    self.log().debug("Running scans list: begin")
                    for running in resp_msg.running_scans:
                        self.log().debug(running)
                    self.log().debug("Running scans list: end")
                    
                await asyncio.sleep(cur_sleep_delay)
                cur_sleep_delay = min(KickoffClient.__SLEEP_MAX_SECONDS, cur_sleep_delay + KickoffClient.__SLEEP_SECONDS)
            else:
                raise KickoffClientException(f"Response from {self.__service_url}: {resp.status_code} {resp.reason}")
            
            retry_count += 1


