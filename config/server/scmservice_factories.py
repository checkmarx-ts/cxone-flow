import string
from pathlib import Path
from scm_services import *
from scm_services.cloner import Cloner
from api_utils.apisession import APISession
from api_utils.auth_factories import AuthFactory
from config import CommonConfig, ConfigurationException, ConfigDictionaryReader
from typing import Dict, Callable, Self


# replacement for unmaintained password_strength package
class PasswordStrengthValidator:

    @staticmethod
    def from_names(
        *, length: int = 0, uppercase: int = 0, numbers: int = 0, special: int = 0
    ) -> Self:
        ret = PasswordStrengthValidator()
        ret.__length = length
        ret.__uppercase = uppercase
        ret.__numbers = numbers
        ret.__special = special
        return ret

    def test(self, pw_value: str) -> bool:
        if pw_value is None:
            return False

        if len(pw_value) < self.__length:
            return False

        if len([c for c in pw_value if c in string.ascii_uppercase]) < self.__uppercase:
            return False

        if len([c for c in pw_value if c in string.digits]) < self.__numbers:
            return False

        if len([c for c in pw_value if c in string.punctuation]) < self.__special:
            return False

        return True


class AbstractSCMServiceFactory(ConfigDictionaryReader):

    class RepoConfigProps(CommonConfig):

        __shared_secret_policy = PasswordStrengthValidator.from_names(
            length=20, uppercase=3, numbers=3, special=2
        )

        def __init__(self, repo_config: Dict, config_path: str):
            self.__cfg_dict = repo_config
            self.__base_path = config_path
            self.__con_cfg_dict = self._get_value_for_key_or_fail(
                self.__base_path, "connection", self.__cfg_dict
            )
            self.__con_cfg_path = f"{self.__base_path}/connection"
            self.__api_auth_cfg_dict = self._get_value_for_key_or_fail(
                self.__con_cfg_path, "api-auth", self.__con_cfg_dict
            )

            self.__scm_shared_secret = self._get_secret_from_value_of_key_or_fail(
                self.__con_cfg_path, "shared-secret", self.__con_cfg_dict
            )

            if not self.__shared_secret_policy.test(self.__scm_shared_secret):
                raise ConfigurationException(
                    f"{self.__base_path}/connection/shared-secret fails some complexity requirements."
                )

            self.__clone_auth_dict = self._get_value_for_key_or_default(
                "clone-auth", self.__con_cfg_dict, None
            )
            self.__clone_config_path = f"{self.__base_path}/connection/clone-auth"
            if self.__clone_auth_dict is None:
                self.__clone_auth_dict = self.__api_auth_cfg_dict
                self.__clone_config_path = f"{self.__base_path}/connection/api-auth"

        @property
        def scm_shared_secret(self) -> str:
            return self.__scm_shared_secret

        @property
        def service_moniker(self) -> str:
            return self._get_value_for_key_or_fail(
                self.__base_path, "service-name", self.__cfg_dict
            )

        @property
        def api_base_url(self) -> str:
            return self._get_value_for_key_or_fail(
                f"{self.__base_path}/connection", "base-url", self.__con_cfg_dict
            )

        @property
        def api_url(self) -> str:
            return APISession.form_api_endpoint(
                self.api_base_url,
                self._get_value_for_key_or_default(
                    "api-url-suffix", self.__con_cfg_dict, None
                ),
            )

        @property
        def display_url(self) -> str:
            return self._get_value_for_key_or_default(
                "base-display-url", self.__con_cfg_dict, self.api_base_url
            )

        @property
        def ssl_verify(self) -> bool:
            return bool(
                self._get_value_for_key_or_default(
                    "ssl-verify",
                    self.__con_cfg_dict,
                    self.get_default_ssl_verify_value(),
                )
            )

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
            return self._get_value_for_key_or_fail(
                self.connection_auth_config_path, "api-auth", self.__con_cfg_dict
            )

        @property
        def timeout_seconds(self) -> int:
            return self._get_value_for_key_or_default(
                "timeout-seconds", self.__con_cfg_dict, 60
            )

        @property
        def retries(self) -> int:
            return self._get_value_for_key_or_default("retries", self.__con_cfg_dict, 3)

        @property
        def proxies(self) -> Dict:
            return self._get_value_for_key_or_default(
                "proxies", self.__con_cfg_dict, None
            )

    @staticmethod
    def APISession_factory(
        api_auth_factory: Callable[[str, str, Dict], AuthFactory],
        config_props: RepoConfigProps,
    ) -> APISession:
        return APISession(
            config_props.api_url,
            api_auth_factory(
                config_props.api_url,
                config_props.connection_auth_config_path,
                config_props.api_auth_config_dict,
            ),
            config_props.timeout_seconds,
            config_props.retries,
            config_props.proxies,
            config_props.ssl_verify,
        )

    @staticmethod
    def Cloner_factory(
        api_session: APISession,
        scm_cloner_factory: Callable[[APISession, str, Dict, bool], Cloner],
        clone_auth_dict: Dict,
        config_path: str,
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
    def __create_inst(props: RepoConfigProps, clazz: type[SCMService]) -> SCMService:
        pass

    @staticmethod
    def get_pr_config_dict(repo_config: Dict) -> Dict:
        feedback_dict = AbstractSCMServiceFactory._get_value_for_key_or_default(
            "feedback", repo_config, None
        )
        if feedback_dict is not None:
            return AbstractSCMServiceFactory._get_value_for_key_or_default(
                "pull-request", feedback_dict, None
            )

        return None

    @staticmethod
    def get_scm_pr_config(repo_config: Dict, scm_specific_key: str) -> Dict:
        pr_dict = AbstractSCMServiceFactory.get_pr_config_dict(repo_config)
        if pr_dict is not None:
            return AbstractSCMServiceFactory._get_value_for_key_or_default(
                scm_specific_key, pr_dict, False
            )

    @staticmethod
    def use_policies(repo_config: Dict) -> bool:
        pr_dict = AbstractSCMServiceFactory.get_pr_config_dict(repo_config)
        if pr_dict is not None:
            return AbstractSCMServiceFactory._get_value_for_key_or_default(
                "use-policies", pr_dict, False
            )
        return False

    @staticmethod
    def factory(
        repo_config: Dict,
        config_path: str,
        cloner_factory: Callable[[APISession, str, Dict, bool], Cloner],
        api_auth_factory: Callable[[str, str, Dict], AuthFactory],
    ) -> SCMService:
        raise NotImplementedError("factory")


class GHSCMServiceFactory(AbstractSCMServiceFactory):
    @staticmethod
    def factory(
        repo_config: Dict,
        config_path: str,
        cloner_factory: Callable[[APISession, str, Dict, bool], Cloner],
        api_auth_factory: Callable[[str, str, Dict], AuthFactory],
    ) -> SCMService:

        props = AbstractSCMServiceFactory.RepoConfigProps(repo_config, config_path)
        api_sess = AbstractSCMServiceFactory.APISession_factory(api_auth_factory, props)

        additional_args = {}

        if not GHSCMServiceFactory.use_policies(repo_config):
            service_clazz = GHServiceBasic
        else:
            pr_dict = AbstractSCMServiceFactory.get_pr_config_dict(repo_config)

            custom_check_name = None

            if pr_dict is not None:
                gh_pr_opts = AbstractSCMServiceFactory._get_value_for_key_or_default(
                    "gh-pr-opts", pr_dict, None
                )

                if gh_pr_opts is not None:
                    custom_check_name = (
                        AbstractSCMServiceFactory._get_value_for_key_or_default(
                            "check-name", gh_pr_opts, None
                        )
                    )

            additional_args = {"check_name": custom_check_name}

            if (
                "app-private-key"
                in GHSCMServiceFactory._get_value_for_key_or_fail(
                    config_path, "api-auth", props.connection_config_dict
                ).keys()
            ):
                # Github app, so use Checks
                service_clazz = GHServiceChecks
            else:
                # Not a Github app, so use Commit Statuses
                service_clazz = GHServiceCommitStatus

        return service_clazz(
            **additional_args,
            display_url=props.display_url,
            moniker=props.service_moniker,
            api_session=api_sess,
            shared_secret=props.scm_shared_secret,
            cloner=AbstractSCMServiceFactory.Cloner_factory(
                api_sess,
                cloner_factory,
                props.clone_auth_config_dict,
                props.clone_config_path,
                props.ssl_no_verify_git,
            ),
        )


class BBDCServiceFactory(AbstractSCMServiceFactory):
    @staticmethod
    def factory(
        repo_config: Dict,
        config_path: str,
        cloner_factory: Callable[[APISession, str, Dict, bool], Cloner],
        api_auth_factory: Callable[[str, str, Dict], AuthFactory],
    ) -> SCMService:

        props = AbstractSCMServiceFactory.RepoConfigProps(repo_config, config_path)
        api_sess = AbstractSCMServiceFactory.APISession_factory(api_auth_factory, props)

        return BBDCService(
            props.display_url,
            props.service_moniker,
            api_sess,
            props.scm_shared_secret,
            AbstractSCMServiceFactory.Cloner_factory(
                api_sess,
                cloner_factory,
                props.clone_auth_config_dict,
                props.clone_config_path,
                props.ssl_no_verify_git,
            ),
        )


class BBCServiceFactory(AbstractSCMServiceFactory):
    @staticmethod
    def factory(
        repo_config: Dict,
        config_path: str,
        cloner_factory: Callable[[APISession, str, Dict, bool], Cloner],
        api_auth_factory: Callable[[str, str, Dict], AuthFactory],
    ) -> SCMService:

        props = AbstractSCMServiceFactory.RepoConfigProps(repo_config, config_path)
        api_sess = AbstractSCMServiceFactory.APISession_factory(api_auth_factory, props)

        additional_args = {}

        if not AbstractSCMServiceFactory.use_policies(repo_config):
            service_clazz = BBCServiceBasic
        else:
            service_clazz = BBCServiceChecks

            pr_dict = AbstractSCMServiceFactory.get_pr_config_dict(repo_config)

            custom_check_name = None

            if pr_dict is not None:
                bb_pr_opts = AbstractSCMServiceFactory._get_value_for_key_or_default(
                    "bb-pr-opts", pr_dict, None
                )

                if bb_pr_opts is not None:
                    custom_check_name = (
                        AbstractSCMServiceFactory._get_value_for_key_or_default(
                            "check-name", bb_pr_opts, None
                        )
                    )

            additional_args = {"check_name": custom_check_name}

        return service_clazz(
            **additional_args,
            display_url=props.display_url,
            moniker=props.service_moniker,
            api_session=api_sess,
            shared_secret=props.scm_shared_secret,
            cloner=AbstractSCMServiceFactory.Cloner_factory(
                api_sess,
                cloner_factory,
                props.clone_auth_config_dict,
                props.clone_config_path,
                props.ssl_no_verify_git,
            ),
        )


class GLServiceFactory(AbstractSCMServiceFactory):
    @staticmethod
    def factory(
        repo_config: Dict,
        config_path: str,
        cloner_factory: Callable[[APISession, str, Dict, bool], Cloner],
        api_auth_factory: Callable[[str, str, Dict], AuthFactory],
    ) -> SCMService:

        props = AbstractSCMServiceFactory.RepoConfigProps(repo_config, config_path)
        api_sess = AbstractSCMServiceFactory.APISession_factory(api_auth_factory, props)

        return GLService(
            props.display_url,
            props.service_moniker,
            api_sess,
            props.scm_shared_secret,
            AbstractSCMServiceFactory.Cloner_factory(
                api_sess,
                cloner_factory,
                props.clone_auth_config_dict,
                props.clone_config_path,
                props.ssl_no_verify_git,
            ),
        )


class ADOEServiceFactory(AbstractSCMServiceFactory):
    @staticmethod
    def factory(
        repo_config: Dict,
        config_path: str,
        cloner_factory: Callable[[APISession, str, Dict, bool], Cloner],
        api_auth_factory: Callable[[str, str, Dict], AuthFactory],
    ) -> SCMService:
        props = AbstractSCMServiceFactory.RepoConfigProps(repo_config, config_path)
        api_sess = AbstractSCMServiceFactory.APISession_factory(api_auth_factory, props)

        additional_args = {}

        if not ADOEServiceFactory.use_policies(repo_config):
            service_clazz = ADOEServiceBasic
        else:
            pr_dict = AbstractSCMServiceFactory.get_pr_config_dict(repo_config)
            pr_opts = AbstractSCMServiceFactory._get_value_for_key_or_fail(
                config_path, "adoe-pr-opts", pr_dict
            )

            additional_args = {
                "check_name": AbstractSCMServiceFactory._get_value_for_key_or_fail(
                    f"{config_path}/adoe-pr-opts", "check-name", pr_opts
                ),
                "check_genre": AbstractSCMServiceFactory._get_value_for_key_or_default(
                    "check-genre", pr_opts, None
                ),
            }

            service_clazz = ADOEServiceChecks

        return service_clazz(
            display_url=props.display_url,
            moniker=props.service_moniker,
            api_session=api_sess,
            shared_secret=props.scm_shared_secret,
            cloner=AbstractSCMServiceFactory.Cloner_factory(
                api_sess,
                cloner_factory,
                props.clone_auth_config_dict,
                props.clone_config_path,
                props.ssl_no_verify_git,
            ),
            **additional_args,
        )
