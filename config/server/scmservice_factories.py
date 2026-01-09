from password_strength import PasswordPolicy
from pathlib import Path
from scm_services import *
from scm_services.cloner import Cloner
from api_utils.apisession import APISession
from api_utils.auth_factories import AuthFactory
from config import CommonConfig, ConfigurationException, ConfigDictionaryReader
from typing import Dict, Callable


class AbstractSCMServiceFactory(ConfigDictionaryReader):

    class RepoConfigProps(CommonConfig):

        __shared_secret_policy = PasswordPolicy.from_names(
            length=20, uppercase=3, numbers=3, special=2
        )


        def __init__(self, repo_config : Dict, config_path : str):
            self.__cfg_dict = repo_config
            self.__base_path = config_path
            self.__con_cfg_dict = self._get_value_for_key_or_fail(self.__base_path, "connection", self.__cfg_dict)
            self.__con_cfg_path = f"{self.__base_path}/connection"
            self.__api_auth_cfg_dict = self._get_value_for_key_or_fail(self.__con_cfg_path, "api-auth", self.__con_cfg_dict)

            self.__scm_shared_secret = self._get_secret_from_value_of_key_or_fail(
                self.__con_cfg_path,
                "shared-secret",
                self.__con_cfg_dict)
            
            secret_test_result = self.__shared_secret_policy.test(self.__scm_shared_secret)

            if not len(secret_test_result) == 0:
              raise ConfigurationException(f"{self.__base_path}/connection/shared-secret fails some complexity requirements: {secret_test_result}")
            
            self.__clone_auth_dict = self._get_value_for_key_or_default("clone-auth", self.__con_cfg_dict, None)
            self.__clone_config_path = f"{self.__base_path}/connection/clone-auth"
            if self.__clone_auth_dict is None:
                self.__clone_auth_dict = self.__api_auth_cfg_dict
                self.__clone_config_path = f"{self.__base_path}/connection/api-auth"


        @property
        def scm_shared_secret(self) -> str:
            return self.__scm_shared_secret
        
        @property
        def service_moniker(self) -> str:
            return self._get_value_for_key_or_fail(self.__base_path, "service-name", self.__cfg_dict)
        
        @property
        def api_base_url(self) -> str:
            return self._get_value_for_key_or_fail(f"{self.__base_path}/connection", "base-url", self.__con_cfg_dict)

        @property
        def api_url(self) -> str:
            return APISession.form_api_endpoint(self.api_base_url, self._get_value_for_key_or_default("api-url-suffix", self.__con_cfg_dict, None))

        @property
        def display_url(self) -> str:
            return self._get_value_for_key_or_default("base-display-url", self.__con_cfg_dict, self.api_base_url)
        
        @property
        def ssl_verify(self) -> bool:
          return bool(self._get_value_for_key_or_default("ssl-verify", self.__con_cfg_dict, self.get_default_ssl_verify_value()))

        @property
        def ssl_no_verify_git(self) -> bool:
          return not self.ssl_verify
        
        @property
        def clone_config_path(self) -> str:
            return self.__clone_config_path

        @property
        def clone_auth_config_dict(self) -> Dict:
            return self.__clone_auth_dict
        
        @property
        def connection_auth_config_path(self) -> str:
            return self.__con_cfg_path

        @property
        def connection_config_dict(self) -> Dict:
            return self.__con_cfg_dict

        @property
        def api_auth_config_dict(self) -> Dict:
            return self._get_value_for_key_or_fail(self.connection_auth_config_path, "api-auth", self.__con_cfg_dict)
        
        @property
        def timeout_seconds(self) -> int:
            return self._get_value_for_key_or_default("timeout-seconds", self.__con_cfg_dict, 60)
        
        @property
        def retries(self) -> int:
            return self._get_value_for_key_or_default("retries", self.__con_cfg_dict, 3)
        
        @property
        def proxies(self) -> Dict:
            return self._get_value_for_key_or_default("proxies", self.__con_cfg_dict, None)



    @staticmethod
    def APISession_factory(api_auth_factory : Callable[[str, str, Dict], AuthFactory], config_props : RepoConfigProps) -> APISession:
        return APISession(
            config_props.api_url,
            api_auth_factory(config_props.api_url, config_props.connection_auth_config_path, config_props.api_auth_config_dict),
            config_props.timeout_seconds,
            config_props.retries,
            config_props.proxies,
            config_props.ssl_verify)

    @staticmethod
    def Cloner_factory(
        api_session: APISession,
        scm_cloner_factory : Callable[[APISession, str, Dict, bool], Cloner],
        clone_auth_dict : Dict,
        config_path : str,
        ssl_no_verify: bool,
    ):

        retval = scm_cloner_factory(
            api_session,
            Path(CommonConfig._secret_root),
            clone_auth_dict,
            ssl_no_verify,
        )

        if retval is None:
            raise ConfigurationException(
                f"{config_path} SCM clone authorization configuration is invalid!"
            )

        return retval


    @staticmethod
    def __create_inst(props : RepoConfigProps, clazz : type[SCMService]) -> SCMService:
        pass

    @staticmethod
    def get_pr_config_dict(repo_config : Dict) -> Dict:
        feedback_dict = AbstractSCMServiceFactory._get_value_for_key_or_default("feedback", repo_config, None)
        if feedback_dict is not None:
            return AbstractSCMServiceFactory._get_value_for_key_or_default("pull-request", feedback_dict, None)

        return None
    
    @staticmethod
    def get_scm_pr_config(repo_config : Dict, scm_specific_key : str) -> Dict:
        pr_dict = AbstractSCMServiceFactory.get_pr_config_dict(repo_config)
        if pr_dict is not None:
            return AbstractSCMServiceFactory._get_value_for_key_or_default(scm_specific_key, pr_dict, False)

    @staticmethod
    def use_policies(repo_config : Dict) -> bool:
        pr_dict = AbstractSCMServiceFactory.get_pr_config_dict(repo_config)
        if pr_dict is not None:
            return AbstractSCMServiceFactory._get_value_for_key_or_default("use-policies", pr_dict, False)
        return False

    @staticmethod
    def factory(repo_config : Dict, 
                config_path : str, 
                cloner_factory : Callable[[APISession, str, Dict, bool], Cloner],
                api_auth_factory : Callable[[str, str, Dict], AuthFactory]) -> SCMService:
        raise NotImplementedError("factory")


class GHSCMServiceFactory(AbstractSCMServiceFactory):
    @staticmethod
    def factory(repo_config : Dict, 
                config_path : str, 
                cloner_factory : Callable[[APISession, str, Dict, bool], Cloner],
                api_auth_factory : Callable[[str, str, Dict], AuthFactory]) -> SCMService:


        props = AbstractSCMServiceFactory.RepoConfigProps(repo_config, config_path)
        api_sess = AbstractSCMServiceFactory.APISession_factory(api_auth_factory, props)

        if not GHSCMServiceFactory.use_policies(repo_config):
            service_clazz = GHServiceBasic
        else:
            if "app-private-key" in GHSCMServiceFactory._get_value_for_key_or_fail(config_path, 
                                                                                   "api-auth", props.connection_config_dict).keys():
                # Github app, so use Checks
                service_clazz = GHServiceChecks
            else:
                # Not a Github app, so use Commit Statuses
                service_clazz = GHServiceCommitStatus
            
        return service_clazz(props.display_url, 
                            props.service_moniker, 
                            api_sess, 
                            props.scm_shared_secret, 
                            AbstractSCMServiceFactory.Cloner_factory(api_sess,
                                                                        cloner_factory, 
                                                                        props.clone_auth_config_dict, 
                                                                        props.clone_config_path, 
                                                                        props.ssl_no_verify_git))


class BBDCServiceFactory(AbstractSCMServiceFactory):
    @staticmethod
    def factory(repo_config : Dict, 
                config_path : str, 
                cloner_factory : Callable[[APISession, str, Dict, bool], Cloner],
                api_auth_factory : Callable[[str, str, Dict], AuthFactory]) -> SCMService:
        
        props = AbstractSCMServiceFactory.RepoConfigProps(repo_config, config_path)
        api_sess = AbstractSCMServiceFactory.APISession_factory(api_auth_factory, props)

        return BBDCService(props.display_url, 
                           props.service_moniker, 
                           api_sess, 
                           props.scm_shared_secret, 
                           AbstractSCMServiceFactory.Cloner_factory(api_sess,
                                                                    cloner_factory, 
                                                                    props.clone_auth_config_dict, 
                                                                    props.clone_config_path, 
                                                                    props.ssl_no_verify_git))


class GLServiceFactory(AbstractSCMServiceFactory):
    @staticmethod
    def factory(repo_config : Dict, 
                config_path : str, 
                cloner_factory : Callable[[APISession, str, Dict, bool], Cloner],
                api_auth_factory : Callable[[str, str, Dict], AuthFactory]) -> SCMService:

        props = AbstractSCMServiceFactory.RepoConfigProps(repo_config, config_path)
        api_sess = AbstractSCMServiceFactory.APISession_factory(api_auth_factory, props)

        return GLService(props.display_url, 
                           props.service_moniker, 
                           api_sess, 
                           props.scm_shared_secret, 
                           AbstractSCMServiceFactory.Cloner_factory(api_sess,
                                                                    cloner_factory, 
                                                                    props.clone_auth_config_dict, 
                                                                    props.clone_config_path, 
                                                                    props.ssl_no_verify_git))

class ADOEServiceFactory(AbstractSCMServiceFactory):    
    @staticmethod
    def factory(repo_config : Dict, 
                config_path : str, 
                cloner_factory : Callable[[APISession, str, Dict, bool], Cloner],
                api_auth_factory : Callable[[str, str, Dict], AuthFactory]) -> SCMService:
        props = AbstractSCMServiceFactory.RepoConfigProps(repo_config, config_path)
        api_sess = AbstractSCMServiceFactory.APISession_factory(api_auth_factory, props)

        return ADOEService(props.display_url, 
                           props.service_moniker, 
                           api_sess, 
                           props.scm_shared_secret, 
                           AbstractSCMServiceFactory.Cloner_factory(api_sess,
                                                                    cloner_factory, 
                                                                    props.clone_auth_config_dict, 
                                                                    props.clone_config_path, 
                                                                    props.ssl_no_verify_git))

# def bbdc_scm_service_factory(repo_config : Dict, config_path : str) -> SCMService:

#   display_url : str, moniker : str, api_session : APISession, shared_secret : str, cloner : Cloner


#         api_session = APISession(
#             api_url,
#             CxOneFlowConfig.__scm_api_auth_factory(
#                 api_url,
#                 api_auth_factory,
#                 api_auth_dict,
#                 f"{config_path}/connection/api-auth",
#             ),
#             CxOneFlowConfig._get_value_for_key_or_default(
#                 "timeout-seconds", connection_config_dict, 60
#             ),
#             CxOneFlowConfig._get_value_for_key_or_default(
#                 "retries", connection_config_dict, 3
#             ),
#             CxOneFlowConfig._get_value_for_key_or_default(
#                 "proxies", connection_config_dict, None
#             ),
#             ssl_verify,
#         )


#         # scm_service = scm_service(
#         #     display_url,
#         #     service_moniker,
#         #     api_session,
#         #     scm_shared_secret,
#         #     CxOneFlowConfig.__cloner_factory(
#         #         api_session,
#         #         cloner_factory,
#         #         clone_auth_dict,
#         #         clone_config_path,
#         #         ssl_no_verify_git,
#         #     ),
#         # )


#   pass

