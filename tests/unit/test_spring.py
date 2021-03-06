"""Test spring module."""
from unittest.mock import PropertyMock

import pytest
import requests

import conftest
from config.auth import OAuth2
from config.exceptions import RequestFailedException
from config.spring import ConfigClient, config_client, create_config_client


class TestConfigClient:
    DATA = "my-secret"
    ENCRYPTED_DATA = "AQC4HPhv2tHW3irTDlFUQ7nBEuPiRiK/RNp0JOHfoS0MrgOxqUAYYnKo5YEu+lDOVm+8EKeRhuw8o+rPmSxDCiNZ7FrriFRAde4ZTJ45FTVzW6COFFEkuXJQktZ2dCqGKLeRrTwWQ98g0X7ee9nEsQXK40yKQRhPCXPFgLY9J0BEukn8i1omFtxSFJ0MGILt5n/Sen9/MOGp+yJXGw7FMLejBpVMc4m9rFDyTskyk8OiobbFfG/osAaNRc2R/cTDEHAXVJVw9QwMWp3EJKpOwnx1YVmL3+4msGLYtRpB0XSrGo2AbUNa+5xTwdXIehmIAbn/TckOJE4sBc6vTSjxmtkNcE9cLDC+nlH0ANR9r/9uPqNFErXWrUlbEMJQ9SU4XdU="

    @pytest.fixture
    def client(self, monkeypatch, scope="module"):
        return ConfigClient(app_name="test_app")

    @pytest.fixture
    def client_with_auth(self, monkeypatch, mocker):
        monkeypatch.setattr(requests, "post", conftest.response_mock_success)
        mocker.patch.object(requests, "get")
        requests.get.return_value = conftest.ResponseMock()
        return ConfigClient(
            app_name="test_app",
            oauth2=OAuth2(
                access_token_uri="https://p-spring-cloud-services.uaa.sys.example.com/oauth/token",
                client_id="p-config-server-example-client-id",
                client_secret="EXAMPLE_SECRET",
            ),
        )

    def test_get_config(self, client, monkeypatch):
        monkeypatch.setattr(requests, "get", conftest.response_mock_success)
        client.get_config()
        assert isinstance(client.config, dict)

    def test_get_config_failed(self, client, monkeypatch):
        monkeypatch.setattr(requests, "get", conftest.response_mock_http_error)
        with pytest.raises(SystemExit):
            client.get_config()

    def test_get_config_with_request_timeout(self, client, mocker):
        TIMEOUT = 5.0
        mocker.patch.object(requests, "get")
        requests.get.return_value = conftest.ResponseMock()
        client.get_config(timeout=TIMEOUT, headers={"Accept": "application/json"})
        requests.get.assert_called_with(
            client.url, timeout=TIMEOUT, headers={"Accept": "application/json"}
        )

    def test_get_config_response_failed(self, client, monkeypatch):
        monkeypatch.setattr(requests, "get", conftest.response_mock_system_error)
        with pytest.raises(SystemExit):
            client.get_config()

    def test_config_property(self, client):
        assert isinstance(client.config, dict)

    def test_default_url_property(self, client):
        assert isinstance(client.url, str)
        assert client.url == "http://localhost:8888/master/test_app-development.json"

    def test_custom_url_property(self):
        client = ConfigClient(
            app_name="test_app",
            url="{address}/{branch}/{profile}-{app_name}.yaml",
        )
        assert client.url == "http://localhost:8888/master/development-test_app.json"

    def test_decorator_failed(self, client, monkeypatch):
        monkeypatch.setattr(requests, "get", Exception)

        @config_client(app_name="myapp")
        def inner(c=None):
            assert isinstance(c, ConfigClient)

        with pytest.raises(SystemExit):
            inner()

    def test_decorator(self, client, monkeypatch):
        monkeypatch.setattr(requests, "get", conftest.response_mock_success)

        @config_client(app_name="myapp")
        def inner(c=None):
            assert isinstance(c, ConfigClient)

        inner()

    def test_decorator_wraps(self, client, monkeypatch):
        monkeypatch.setattr(requests, "get", conftest.response_mock_success)

        @config_client(app_name="myapp")
        def inner(c=None):
            return c

        assert inner.__name__ == "inner"

    def test_decorator_pass_kwargs(self, client, mocker):
        mocker.patch.object(requests, "get")

        @config_client(app_name="test_app", timeout=5)
        def inner(c):
            assert isinstance(c, ConfigClient)

        inner()

        requests.get.assert_called_with(
            f"{client.address}/{client.branch}/{client.app_name}-{client.profile}.json",
            timeout=5,
        )

    def test_fail_fast_disabled(self, monkeypatch):
        monkeypatch.setattr(requests, "get", Exception)
        client = ConfigClient(app_name="test_app", fail_fast=False)
        with pytest.raises(ConnectionError):
            client.get_config()

    def test_create_config_client_with_singleton(self, monkeypatch):
        monkeypatch.setattr(requests, "get", conftest.response_mock_success)
        client1 = create_config_client(app_name="app1")
        client2 = create_config_client(app_name="app2")
        assert id(client1) == id(client2)

    def test_get_keys(self, client):
        type(client)._config = PropertyMock(return_value=conftest.CONFIG)
        assert client.get_keys() == conftest.CONFIG.keys()

    def test_keys(self, client):
        type(client)._config = PropertyMock(return_value=conftest.CONFIG)
        assert client.keys() == conftest.CONFIG.keys()

    def test_get_attribute(self, client):
        type(client)._config = PropertyMock(return_value=conftest.CONFIG)
        response = client.get_attribute("spring.cloud.consul.host")
        assert response is not None
        assert response == "discovery"

    def test_getitem(self, client):
        type(client)._config = PropertyMock(return_value=conftest.CONFIG)
        response = client.get("spring.cloud.consul.host")
        assert response is not None
        assert response == "discovery"

    def test_fix_valid_url_extension(self, client):
        client.url == "http://localhost:8888/master/test-app-development.json"

    def test_fix_url_extension_without_profile(self):
        client = ConfigClient(
            app_name="simpleweb000", url="{address}/{branch}/{app_name}"
        )
        client.url == "http://localhost:8888/master/simpleweb000.json"

    def test_get_file(self, client, mocker):
        mocker.patch.object(requests, "get")
        requests.get.return_value = conftest.ResponseMock(text="some text")
        content = client.get_file("nginx.conf")
        requests.get.assert_called_with(
            f"{client.address}/{client.app_name}/{client.profile}/{client.branch}/nginx.conf"
        )
        assert content == "some text"

    def test_get_file_error(self, client, monkeypatch):
        monkeypatch.setattr(requests, "get", conftest.response_mock_http_error)
        with pytest.raises(RequestFailedException):
            client.get_file("nginx.conf")

    def test_encrypt_failed(self, client, monkeypatch):
        monkeypatch.setattr(requests, "post", conftest.response_mock_http_error)
        with pytest.raises(RequestFailedException):
            client.encrypt(self.DATA)

    def test_decrypt_failed(self, client, monkeypatch):
        monkeypatch.setattr(requests, "post", conftest.response_mock_http_error)
        with pytest.raises(RequestFailedException):
            client.decrypt(self.ENCRYPTED_DATA)

    def test_encrypt(self, client, mocker):
        mocker.patch.object(requests, "post")
        requests.post.return_value = conftest.ResponseMock(text=self.ENCRYPTED_DATA)
        response = client.encrypt(self.DATA)
        requests.post.assert_called_with(
            f"{client.address}/encrypt",
            data=self.DATA,
            headers={"Content-Type": "text/plain"},
        )
        assert response == self.ENCRYPTED_DATA

    def test_encrypt_with_custom_path(self, client, mocker):
        mocker.patch.object(requests, "post")
        requests.post.return_value = conftest.ResponseMock(text=self.ENCRYPTED_DATA)
        response = client.encrypt(self.DATA, path="/configuration/encrypt")
        requests.post.assert_called_with(
            f"{client.address}/configuration/encrypt",
            data=self.DATA,
            headers={"Content-Type": "text/plain"},
        )
        assert response == self.ENCRYPTED_DATA

    def test_decrypt(self, client, mocker):
        mocker.patch.object(requests, "post")
        requests.post.return_value = conftest.ResponseMock(text=self.DATA)
        response = client.decrypt(self.ENCRYPTED_DATA)
        requests.post.assert_called_with(
            f"{client.address}/decrypt",
            data=self.ENCRYPTED_DATA,
            headers={"Content-Type": "text/plain"},
        )
        assert response == self.DATA

    def test_decrypt_with_custom_path(self, client, mocker):
        mocker.patch.object(requests, "post")
        requests.post.return_value = conftest.ResponseMock(text=self.DATA)
        response = client.decrypt(self.ENCRYPTED_DATA, path="/configuration/decrypt")
        requests.post.assert_called_with(
            f"{client.address}/configuration/decrypt",
            data=self.ENCRYPTED_DATA,
            headers={"Content-Type": "text/plain"},
        )
        assert response == self.DATA

    def test_client_with_auth(self, client_with_auth):
        client_with_auth.get_config()
        requests.get.assert_called_with(
            client_with_auth.url, headers={"Authorization": "Bearer eyJz93a...k4laUWw"}
        )

    def test_client_with_auth_and_headers(self, client_with_auth):
        client_with_auth.get_config(
            headers={"X-Client-ID": "test-client"}, verify=False
        )
        requests.get.assert_called_with(
            client_with_auth.url,
            headers={
                "X-Client-ID": "test-client",
                "Authorization": "Bearer eyJz93a...k4laUWw",
            },
            verify=False,
        )
