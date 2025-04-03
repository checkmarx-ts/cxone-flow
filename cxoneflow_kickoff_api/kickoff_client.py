import jwt, time, asyncio, logging, requests
from .exceptions import KickoffClientException
from .signature_alg import get_signature_alg
from cryptography.hazmat.primitives.serialization import load_ssh_private_key
from typing import Dict, Union, Tuple, Callable
from .kickoff_msgs import KickoffMsg, KickoffResponseMsg
from .status import KickoffStatusCodes


class KickoffClient:

    __JWT_TIMEOUT = 600
    __JWT_JITTER = 60
    __SLEEP_SECONDS = 15
    __SLEEP_MAX_SECONDS = 180
    __SLEEP_REPORT_MOD = 3

    @classmethod
    def log(clazz) -> logging.Logger:
        return logging.getLogger(clazz.__name__)

    def __init__(self, private_ssh_key : str, private_key_password : Union[str,None], 
                 cxoneflow_ko_url : str, user_agent : str, 
                 proxies : Dict[str, str] = None, ssl_verify : bool = True):
        """A client for orchestrating initial repository scans with CxOneFlow.

        Args:
            private_ssh_key (str): The string representation of a PEM encoded private SSH key.

            private_key_password (Union[str,None]): If the private key is password protected, provide the password.
                                                    If the private key is not protected, set to "None".
            
            cxoneflow_ko_url (str): The URL to the CxOneFlow kickoff endpoint for any given SCM.

                                    Examples for current SCM endpoints:
                                    https://cxoneflow.corp.com/gh/kickoff
                                    https://cxoneflow.corp.com/gl/kickoff
                                    https://cxoneflow.corp.com/adoe/kickoff
                                    https://cxoneflow.corp.com/bbdc/kickoff


            user_agent (str): A user agent string, usually the name/version of your client that is
                              sending payloads to the CxOneFlow endpoint.

            proxies (Dict[str, str], optional): A dictionary that defines proxy connections as defined in the Python Requests API. Defaults to None.


            ssl_verify (bool, optional): Set to False to skip SSL verification.  
                                         This can also be an absolute path to a PEM encoded certificate
                                         used to validate the SSL certificate used on the CxOneFlow endpoint. Defaults to True.
        """
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


    async def kickoff_scan(self, msg : KickoffMsg, 
                           waiting_callback : Callable[[KickoffStatusCodes, KickoffResponseMsg, int], bool] = None) \
                            -> Tuple[KickoffStatusCodes, Union[None, KickoffResponseMsg]]:
        """The method that executes the scan kickoff.

        Args:
            msg (KickoffMsg): A kickoff message type appropriate for the CxOneFlow SCM endpoint where the message will be delivered.


            waiting_callback (Callable[[KickoffResponseMsg], bool]): An optional method that is called
                                                                     when the CxOneFlow endpoint indicates there are too many
                                                                     concurrently running scans.  The client will retry the scan
                                                                     after a delay.  The delay continues until the scan is submitted
                                                                     or the callback returns False. Defaults to None.

                                                                     Callback parameters:

                                                                     KickoffStatusCodes - A status code enumeration that indicates the server's
                                                                                          response status.

                                                                     KickoffResponseMsg - The response payload received from the server
                                                                                          to indicate current state of scanning.  This
                                                                                          can be None if no message was received.

                                                                     int                - The number of seconds the client intends to sleep
                                                                                          before the next submission attempt.
        Raises:
            KickoffClientException: Throws an exception in the event there is an error when attempting to execute a scan kickoff.

        Returns:
            Tuple[KickoffStatusCodes, Union[None,KickoffResponseMsg]]: Returns the status indicated by the server.  If the CxOneFlow endpoint
                                                                       returns a KickoffResponseMsg, it is also returned.  If no 
                                                                       KickoffResponseMsg is available then None is returned.
        """

        cur_sleep_delay = KickoffClient.__SLEEP_SECONDS
        retry_count = 0

        while True:
            self.log().debug(f"Kicking off scan: {msg}")

            resp = await self.__execute_request(msg)

            resp_status = KickoffStatusCodes(resp.status_code)

            if resp.ok or resp_status in [KickoffStatusCodes.SCAN_EXISTS, KickoffStatusCodes.TOO_MANY_SCANS]:
                resp_msg = KickoffResponseMsg.from_dict(resp.json())
            else:
                resp_msg = None

            if resp_status == KickoffStatusCodes.SCAN_STARTED:
                self.log().debug(f"Scan started: {resp_msg.to_json()}") # pylint: disable=E1101
                return resp_status, resp_msg
            elif resp_status == KickoffStatusCodes.SCAN_EXISTS:
                self.log().debug(f"The server indicated a kickoff scan is already running or has finished for {msg}")
                return resp_status, resp_msg
            elif resp_status == KickoffStatusCodes.TOO_MANY_SCANS:

                if waiting_callback is not None and not waiting_callback(resp_status, resp_msg, cur_sleep_delay):
                    self.log().debug("The callback returned False to indicate the client should not retry submission.")
                    return resp_status, resp_msg
                
                if retry_count % KickoffClient.__SLEEP_REPORT_MOD == 0:
                    if waiting_callback is None:
                        self.log().info(f"The server indicated that too many concurrent scans are running." + 
                                        f"Currently running: {len(resp_msg.running_scans)}. Sleeping for {cur_sleep_delay} seconds.")

                    self.log().debug("Running scans list: begin")
                    for running in resp_msg.running_scans:
                        self.log().debug(running)
                    self.log().debug("Running scans list: end")

                self.log().debug(f"Sleeping {cur_sleep_delay}s before retrying...")    
                await asyncio.sleep(cur_sleep_delay)
                cur_sleep_delay = min(KickoffClient.__SLEEP_MAX_SECONDS, cur_sleep_delay + KickoffClient.__SLEEP_SECONDS)
            else:
                raise KickoffClientException(f"Response from {self.__service_url}: {resp.status_code} {resp.reason}")
            
            retry_count += 1


