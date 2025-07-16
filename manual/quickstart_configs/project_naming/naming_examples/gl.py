from api_utils.auth_factories import EventContext
from scm_services import BasicSCMService
import logging

#############################################
#### Project Naming Code Example: Gitlab ####
#############################################


async def event_project_name_factory(context: EventContext, scm_service: BasicSCMService) -> str:
    # Get an instance of the logger
    log = logging.getLogger(__name__)

    # Output the event context to the debug log
    log.debug(context)

    if "project" in context.message.keys():
        project_name = context.message["project"]["name"]

        # Get the full proper name of the repository from the project configuration.
        resp = await scm_service.exec("GET", f"/projects/{context.message['project']['id']}")
        if resp.ok:
            full_name = resp.json()["name_with_namespace"]

            path_components = full_name.split("/")

            # Use all components except the last one which is the name of the project.
            revised_components = []
            for component in path_components[:-1]:
                revised_components.append("".join(c for c in component if c.isupper()))
            
            revised_components.append(project_name)

            return "/".join(revised_components)


    # Failure causes the default project name to be used
    return None

