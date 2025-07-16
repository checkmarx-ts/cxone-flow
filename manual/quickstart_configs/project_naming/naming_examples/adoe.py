from api_utils.auth_factories import EventContext
from scm_services import BasicSCMService

###################################################
#### Project Naming Code Example: Azure DevOps ####
###################################################

def normalize_collection_name(col_name):
    if len(col_name) < 6:
      return col_name
    else:
      return col_name[0:6]


async def event_project_name_factory(context : EventContext, scm_service : BasicSCMService) -> str:
  if 'resource' in context.message.keys():
    # Webhook event
    repo_name = context.message['resource']['repository']['name']
    project_name = context.message['resource']['repository']['project']['name']
    collection_id = context.message['resourceContainers']['collection']['id']

    # Perform a GET using the scm_service object.
    collection_lookup_resp = await scm_service.exec("GET", f"/_apis/projectcollections/{collection_id}", event_context=context)

    if not collection_lookup_resp.ok:
      return None

    collection_name = collection_lookup_resp.json()['name']
  else:
    # Kickoff event
    collection_name = context.message['collection_name']
    repo_name = context.message['repo_name']
    project_name = context.message['project_name']


  return f"{normalize_collection_name(collection_name)}_{project_name}_{repo_name}"
