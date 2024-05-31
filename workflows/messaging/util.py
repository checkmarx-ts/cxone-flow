from datetime import datetime, timedelta, UTC

def compute_drop_by_timestamp(keep_alive : timedelta = timedelta(seconds=0) ):
    max_iso = "9999-12-31T00:00:00Z"
    
    if keep_alive.total_seconds():
            return (datetime.now(UTC) + keep_alive).isoformat()
    else:
          return max_iso


def is_expired(msg_drop_time):
  compare_time = None

  if type(msg_drop_time) is datetime:
    compare_time = msg_drop_time
  elif type(msg_drop_time) is str:
      compare_time = datetime.fromisoformat(msg_drop_time)

  return datetime.now(UTC) >= compare_time