from enum import Enum

class KickoffStatusCodes(Enum):
  SCAN_STARTED = 201
  SCAN_EXISTS = 299
  BAD_REQUEST = 400
  NOT_AUTHORIZED = 401
  NO_ROUTE = 403
  TOO_MANY_SCANS = 429
  SERVER_ERROR = 500
