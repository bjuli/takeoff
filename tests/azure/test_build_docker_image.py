import base64
import os

import mock
import pytest

from takeoff.application_version import ApplicationVersion
from takeoff.build_docker_image import DockerImageBuilder, DockerFile, DOCKER_CONFIG_PATH
from takeoff.credentials.container_registry import DockerCredentials
from tests.azure import takeoff_config

BASE_CONF = {"task": "build_docker_image",
             "credentials": "environment_variables",
             }

CREDS = DockerCredentials("My", "Little", "pony")
ENV_VARIABLES = {"HOME": "my_home",
                 "PIP_EXTRA_INDEX_URL": "url/to/artifact/store",
                 "CI_PROJECT_NAME": "Elon"}


@pytest.fixture(autouse=True)
def victim() -> DockerImageBuilder:
    with mock.patch("takeoff.build_docker_image.DockerRegistry.credentials", return_value=CREDS), \
         mock.patch("takeoff.step.ApplicationName.get", return_value="myapp"):
        conf = {**takeoff_config(), **BASE_CONF}
        return DockerImageBuilder(ApplicationVersion('DEV', '2.1.0', 'MASTER'), conf)


@pytest.fixture(autouse=True)
def victim_release() -> DockerImageBuilder:
    with mock.patch("takeoff.build_docker_image.DockerRegistry.credentials", return_value=CREDS), \
         mock.patch("takeoff.step.ApplicationName.get", return_value="myapp"):
        conf = {**takeoff_config(), **BASE_CONF}
        return DockerImageBuilder(ApplicationVersion('PRD', '2.1.0', '2.1.0'), conf)


def assert_docker_json(mopen, mjson):
    mopen.assert_called_once_with("my_home/.docker/config.json", "w")
    auth = base64.b64encode("My:Little".encode()).decode()
    jsn = {"auths": {"pony": {"auth": auth}}}
    mjson.assert_called_once_with(jsn, mopen())


def test_construct_docker_build_config(victim: DockerImageBuilder):
    res = victim._construct_docker_build_config()
    assert res == [DockerFile("Dockerfile", None, None, True)]


def assert_docker_push(m_bash):
    m_bash.assert_called_once_with(["docker", "--config", DOCKER_CONFIG_PATH, "push", "image/stag"])


def assert_docker_build(m_bash):
    m_bash.assert_called_once_with(["docker",
                                    "build",
                                    "--build-arg",
                                    "PIP_EXTRA_INDEX_URL=url/to/artifact/store",
                                    "--config",
                                    DOCKER_CONFIG_PATH,
                                    "-t",
                                    "stag",
                                    "-f",
                                    "./Thefile",
                                    "."])


class TestDockerImageBuilder:

    @mock.patch.dict(os.environ, ENV_VARIABLES)
    @mock.patch("takeoff.build_docker_image.DockerRegistry.credentials", return_value=CREDS)
    def test_validate_minimal_schema(self, _):
        conf = {**takeoff_config(), **BASE_CONF}

        res = DockerImageBuilder(ApplicationVersion("dev", "v", "branch"), conf)
        assert res.config['dockerfiles'] == [{"file": "Dockerfile", "postfix": None, "custom_image_name": None, 'tag_release_as_latest': True}]

    @mock.patch.dict(os.environ, ENV_VARIABLES)
    @mock.patch("takeoff.build_docker_image.DockerRegistry.credentials", return_value=CREDS)
    def test_validate_full_schema(self, _):
        conf = {**takeoff_config(),
                **BASE_CONF, **{
                "dockerfiles": [{
                    "file": "Dockerfile_custom",
                    "postfix": "Dave",
                    "custom_image_name": "Mustaine"
                }]}}

        DockerImageBuilder(ApplicationVersion("dev", "v", "branch"), conf)

    @mock.patch.dict(os.environ, ENV_VARIABLES)
    @mock.patch("takeoff.build_docker_image.run_shell_command", return_value=(0, ['output_lines']))
    def test_build_image_success(self, m_bash):
        DockerImageBuilder.build_image("Thefile", "stag")
        assert_docker_build(m_bash)

    @mock.patch.dict(os.environ, ENV_VARIABLES)
    @mock.patch("takeoff.build_docker_image.run_shell_command", return_value=(1, ['output_lines']))
    def test_build_image_failure(self, m_bash):
        with pytest.raises(ChildProcessError):
            DockerImageBuilder.build_image("Thefile", "stag")
        assert_docker_build(m_bash)

    @mock.patch("takeoff.build_docker_image.run_shell_command", return_value=(0, ['output_lines']))
    def test_push_image_success(self, m_bash):
        DockerImageBuilder.push_image("image/stag")
        assert_docker_push(m_bash)

    @mock.patch("takeoff.build_docker_image.run_shell_command", return_value=(1, ['output_lines']))
    def test_push_image_failure(self, m_bash):
        with pytest.raises(ChildProcessError):
            DockerImageBuilder.push_image("image/stag")
        assert_docker_push(m_bash)

    @mock.patch.dict(os.environ, {"PIP_EXTRA_INDEX_URL": "url/to/artifact/store",
                                  "CI_PROJECT_NAME": "myapp",
                                  "CI_COMMIT_REF_SLUG": "2.1.0"})
    @mock.patch("takeoff.build_docker_image.run_shell_command", return_value=(0, ['output_lines']))
    def test_deploy_non_release(self, m_bash, victim: DockerImageBuilder):
        files = [DockerFile("Dockerfile", None, None, True), DockerFile("File2", "-foo", "mycustom/repo", False)]
        victim.deploy(files)
        build_call_1 = ["docker", "build", "--build-arg", "PIP_EXTRA_INDEX_URL=url/to/artifact/store", "--config", DOCKER_CONFIG_PATH, "-t", "pony/myapp:2.1.0", "-f", "./Dockerfile", "."]
        build_call_2 = ["docker", "build", "--build-arg", "PIP_EXTRA_INDEX_URL=url/to/artifact/store", "--config", DOCKER_CONFIG_PATH, "-t", "mycustom/repo-foo:2.1.0", "-f", "./File2", "."]

        push_call_1 = ["docker", "--config", DOCKER_CONFIG_PATH, "push", "pony/myapp:2.1.0"]
        push_call_2 = ["docker", "--config", DOCKER_CONFIG_PATH, "push", "mycustom/repo-foo:2.1.0"]
        calls = list(map(mock.call, [build_call_1, push_call_1, build_call_2, push_call_2]))
        m_bash.assert_has_calls(calls)

    @mock.patch.dict(os.environ, {"PIP_EXTRA_INDEX_URL": "url/to/artifact/store",
                                  "CI_PROJECT_NAME": "myapp",
                                  "CI_COMMIT_REF_SLUG": "2.1.0"})
    @mock.patch("takeoff.build_docker_image.run_shell_command", return_value=(0, ['output_lines']))
    @mock.patch("takeoff.application_version.get_tag", return_value="2.1.0")
    def test_deploy_release(self, m_tag, m_bash, victim_release: DockerImageBuilder):
        files = [DockerFile("Dockerfile", None, None, True), DockerFile("File2", "-foo", "mycustom/repo", False)]

        victim_release.deploy(files)
        build_call_1 = ["docker", "build", "--build-arg", "PIP_EXTRA_INDEX_URL=url/to/artifact/store", "--config", DOCKER_CONFIG_PATH, "-t", "pony/myapp:2.1.0", "-f", "./Dockerfile", "."]
        build_call_2 = ["docker", "build", "--build-arg", "PIP_EXTRA_INDEX_URL=url/to/artifact/store", "--config", DOCKER_CONFIG_PATH, "-t", "mycustom/repo-foo:2.1.0", "-f", "./File2", "."]

        push_call_1 = ["docker", "--config", DOCKER_CONFIG_PATH, "push", "pony/myapp:2.1.0"]
        push_call_1_latest = ["docker", "--config", DOCKER_CONFIG_PATH, "push", "pony/myapp:latest"]
        push_call_2 = ["docker", "--config", DOCKER_CONFIG_PATH, "push", "mycustom/repo-foo:2.1.0"]
        calls = list(map(mock.call, [build_call_1, push_call_1, push_call_1_latest, build_call_2, push_call_2]))
        m_bash.assert_has_calls(calls)
