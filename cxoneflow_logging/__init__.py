import logging, logging.config, json, os, pathlib, re
from threading import Lock

class SecretRegistry:
     __lock = Lock()
     __default_regex = "Authorization: .+ (?P<header>[a-zA-Z0-9=+\\/-]+)"
     __compiled_regex = re.compile(__default_regex,  re.RegexFlag.I | re.RegexFlag.M)
     __secrets = []
     
     @staticmethod
     def register(secret : str) -> str:
        if secret is not None:
            with SecretRegistry.__lock:
                if not secret in SecretRegistry.__secrets:
                    SecretRegistry.__secrets.append(re.escape(secret.replace("\n", "").replace("\r", "")))
                    SecretRegistry.__compiled_regex = re.compile(f"{SecretRegistry.__default_regex}|(?P<any>{'|'.join(SecretRegistry.__secrets)})", \
                                                                 re.RegexFlag.I | re.RegexFlag.M)
        return secret
          
     
     @staticmethod
     def get_match_iter(logmsg : str) -> re.Match:
          with SecretRegistry.__lock:
              return SecretRegistry.__compiled_regex.finditer(logmsg)


class RedactingStreamHandler(logging.StreamHandler):
     
    def format(self, record):
        msg = super().format(record)
        for secret in SecretRegistry.get_match_iter(msg):
            for m in secret.groupdict().keys():
                msg = msg[0:secret.start(m)] + ('*' * (secret.end(m) - secret.start(m))) + msg[secret.end(m):]
        
        return msg


def get_log_level():
    return "INFO" if os.getenv('LOG_LEVEL') is None else os.getenv('LOG_LEVEL')


def load_logging_config_dict(filename):
    with open(filename, "rt") as cfg:
        config = json.load(cfg) 
        config['loggers']['root']['level'] = get_log_level()
        return config
    
def bootstrap():
        
        dest_file_path = f"/var/log/cxoneflow/cxoneflow.{os.getpid()}.log"

        dir = os.path.dirname(dest_file_path)

        if not os.path.exists(dir):
             dest_file_path = pathlib.Path(".") / pathlib.Path(dest_file_path).name
        
        log_cfg = {
            "version": 1,
            "handlers": {
                "console": {
                    "class": "cxoneflow_logging.RedactingStreamHandler",
                    "formatter": "default",
                    "stream": "ext://sys.stdout"
                },
                # "file": {
                #     "class": "logging.handlers.RotatingFileHandler",
                #     "formatter": "default",
                #     "filename": dest_file_path,
                #     "backupCount" : 10,
                #     "maxBytes" : 1024000000
                # }
            },
            "formatters": {
                "default": {
                    "format": "[%(asctime)s][%(process)d][%(name)s][%(levelname)s] %(message)s",
                    "datefmt": "%Y-%m-%dT%H:%M:%S%z"
                }
            },
            "loggers": {
                "root": {
                    "handlers": ["console"],
                    "level": get_log_level()
                }
            }
        }

        logging.config.dictConfig(log_cfg)
