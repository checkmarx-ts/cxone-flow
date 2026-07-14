from orchestration.base import AbstractOrchestrator
from api_utils.auth_factories import EventContext
from api_utils import signature

class BitBucketAbstractOrchestrator(AbstractOrchestrator):

  def __init__(self, event_context : EventContext):
    AbstractOrchestrator.__init__(self, event_context)
    self.__event = self.get_header_key_safe('X-Event-Key') 

  @property
  def event_name(self) -> str:
    return self.__event
  
  @property
  def _repo_name(self) -> str:
    return self.__repo_name

  @_repo_name.setter
  def _repo_name(self, value : str):
    self.__repo_name = value

  @property
  def _repo_project_name(self) -> str:
    return self.__repo_project_name
  
  @_repo_project_name.setter
  def _repo_project_name(self, value : str):
    self.__repo_project_name = value

  @property
  def _repo_organization(self) -> str:
      return self.__repo_organization
  
  @_repo_organization.setter
  def _repo_organization(self, value : str):
      self.__repo_organization = value

  @property
  def _repo_slug(self) -> str:
      return self.__repo_slug

  @_repo_slug.setter
  def _repo_slug(self, value : str):
      self.__repo_slug = value

  @property
  def _repo_project_key(self) -> str:
      return self.__repo_project_key

  @_repo_project_key.setter
  def _repo_project_key(self, value : str):
      self.__repo_project_key = value

  async def is_signature_valid(self, shared_secret : str) -> bool:
    sig = self.get_header_key_safe('X-Hub-Signature')
    
    if sig is None:
      BitBucketAbstractOrchestrator.log().warning("X-Hub-Signature header is missing, rejecting.")
      return False

    hashalg,hash = sig.split("=")
    payload_hash = signature.hmac(hashalg, shared_secret, self.event_context.raw_event_payload)

    return hash == payload_hash

