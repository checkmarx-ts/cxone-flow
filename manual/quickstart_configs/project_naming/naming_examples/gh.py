from api_utils.auth_factories import EventContext
from scm_services import BasicSCMService
import logging

#############################################
#### Project Naming Code Example: GitHub ####
#############################################

def normalize_org_name(org_name):
    if len(org_name) < 6:
      return org_name
    else:
      return org_name[0:6]


async def event_project_name_factory(context : EventContext, scm_service : BasicSCMService) -> str:
  # Get an instance of the logger
  log = logging.getLogger(__name__)

  # Output the event context to the debug log
  log.debug(context)

  repo_name = None
  if 'repository' in context.message.keys():
     repo_name = context.message['repository']['name']

  org_name = None
  if 'organization' in context.message.keys():
     org_name = normalize_org_name(context.message['organization']['login'])

  # If both org and repo names are set, set the name of the project.
  if org_name is not None and repo_name is not None:
     return f"{org_name}_{repo_name}"
  
  # Failure causes the default project name to be used
  return None

