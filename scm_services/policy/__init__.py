
class PolicyProperties:

  __default_check_name = "CheckmarxOne Scan"

  def __init__(self, check_name=None, **kwargs):
    self.__check_name = check_name if check_name is not None else PolicyProperties.__default_check_name

  @property
  def check_name(self) -> str:
    return self.__check_name