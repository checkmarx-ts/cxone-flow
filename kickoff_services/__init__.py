from cryptography.hazmat.primitives.serialization import load_ssh_public_key
from cxoneflow_kickoff_api.signature_alg import get_signature_alg
from cxoneflow_kickoff_api import ExecutingScan
from cxone_api import CxOneClient
from cxone_api.low.scans import retrieve_list_of_scans
from cxone_api.util import page_generator
from typing import List
import time, jwt, logging


class KickoffServerException(BaseException):...


class KickoffService:

  __TAG_KEY = "kickoff"

  @classmethod
  def log(clazz) -> logging.Logger:
      return logging.getLogger(clazz.__name__)

  def __init__(self, client : CxOneClient, public_key : str, service_moniker : str, max_concurrent_scans : int):
    self.__pkey = load_ssh_public_key(public_key.encode("UTF-8"))
    self.__algs = [get_signature_alg(self.__pkey)]
    self.__moniker = service_moniker
    self.__max_scans = max_concurrent_scans
    self.__client = client

  @property
  def max_concurrent_scans(self):
    return self.__max_scans
  
  @property
  def scan_tag_dict(self):
    return {KickoffService.__TAG_KEY : self.__moniker}
  
  async def validate_jwt(self, token : str) -> bool:

    if token is None:
      self.log().debug("Invalid JWT")
      return False

    try:
      decoded_payload = jwt.decode(token, self.__pkey, algorithms=self.__algs)
      
      if decoded_payload is None:
        self.log().debug("Unable to decode JWT")
        return False
      
      if time.time() >= decoded_payload['exp']:
        self.log().debug("JWT has expired")
        return False

    except Exception as ex:
      self.log().exception(ex)
      return False

    return True
  
  async def get_completed_ko_scans_by_project(self, project_name : str) -> List[ExecutingScan]:
    scans = []

    async for scan in page_generator(retrieve_list_of_scans, array_element="scans", project_names=project_name,
                                     client=self.__client, tags_keys = KickoffService.__TAG_KEY, 
                                     tags_values = self.__moniker, statuses = ["Running", "Queued","Completed"]):
      scans.append(ExecutingScan(project_name, scan['projectId'], scan['id'], scan['branch']))

    return scans
  
  async def get_running_ko_scans(self) -> List[ExecutingScan]:
    
    scans = []

    async for scan in page_generator(retrieve_list_of_scans, array_element="scans", 
                                     client=self.__client, tags_keys = KickoffService.__TAG_KEY, 
                                     tags_values = self.__moniker, statuses = ["Running", "Queued"]):
      scans.append(ExecutingScan(scan['projectName'], scan['projectId'], scan['id'], scan['branch']))

    return scans



class DummyKickoffService(KickoffService):

  def __init__(self, *args, **kwargs): ...

  async def validate_jwt(self, token : str) -> bool:
    return False

  async def get_completed_ko_scans_by_project(self, client : CxOneClient, project_name : str) -> List[ExecutingScan]:
    return []

  async def get_running_ko_scans(self, client : CxOneClient) -> List[ExecutingScan]:
    return []
