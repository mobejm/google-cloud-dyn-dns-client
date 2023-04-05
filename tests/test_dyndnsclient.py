import dyndnsclient
import json
import logging
import unittest

import tests.test_logger

from ipaddress import IPv4Address
from logging.handlers import MemoryHandler
from tests.test_httpserver import (
    TestHttpRequestHandler,
    TestHttpServer,
    TestHttpServerHandler,
)
from tests.test_logger import LogAssertions
from typing import Dict

logger = logging.getLogger(__name__)


class DynDnsClientTest(unittest.TestCase):
    def setUp(self):
        self._get_handler = TestHttpRequestHandler(
            status_code=404,
            headers={"Content-type": "application/json"},
            response_payload=json.dumps({"msg": "Not Found"}),
        )
        self._post_handler = TestHttpRequestHandler(
            status_code=200,
            headers={"Content-type": "application/json"},
            response_payload="",
        )
        self._server_handler = TestHttpServerHandler(
            get_handler=self._get_handler, post_handler=self._post_handler
        )
        self._dyn_dns_api_server = TestHttpServer(server_handler=self._server_handler)
        self._dns_resolver = TestDnsResolver()
        self._auth_helper = TestAuthHelper()

        api_url = (
            f"http://{self._dyn_dns_api_server.address}:{self._dyn_dns_api_server.port}"
        )
        self._zone_name = "domain-com"
        self._zone_dns_name = "domain.com."
        self._domain_name = "test.domain.com"
        self._dyn_dns_client = dyndnsclient.DynDnsClient(
            zone_name=self._zone_name,
            zone_dns_name=self._zone_dns_name,
            dyn_dns_api_url=api_url,
            hostname=self._domain_name,
            dns_cache_ttl_sec=0,
            dns_resolver=self._dns_resolver,
            auth_helper=self._auth_helper,
        )

        for handler in logger.root.handlers:
            if type(handler) is MemoryHandler:
                handler.flush()

    def tearDown(self):
        self._dyn_dns_api_server.stop()

    #####
    # DynDnsClient Tests
    #####

    def test_GIVEN_sameIp_WHEN_updateDnsRecord_THEN_succeed(self):
        ipv4 = IPv4Address("127.0.0.1")
        self._dns_resolver.ipv4 = ipv4
        self._dyn_dns_client.update_dns_record(ipv4)
        self.assertEqual(self._dns_resolver.get_history(), [ipv4])
        LogAssertions.assert_last_info_log().has_message_containing(
            "The Public IP has not changed"
        )

    def test_GIVEN_differentIp_WHEN_updateDnsRecord_THEN_succeed(self):
        with self._dyn_dns_api_server:
            old_ipv4 = IPv4Address("127.0.0.1")
            new_ipv4 = IPv4Address("127.0.0.2")
            self._dns_resolver.ipv4 = old_ipv4
            self._dyn_dns_client.update_dns_record(new_ipv4)
            self.assertEqual(self._dns_resolver.get_history(), [old_ipv4])
            LogAssertions.assert_last_info_log().has_message_containing(
                f"Successfully updated the {self._domain_name} DNS A record with IP {new_ipv4}"
            )


class TestDnsResolver(dyndnsclient.DnsResolver):
    def __init__(self, ipv4: IPv4Address = IPv4Address("127.0.0.1")) -> None:
        super().__init__()
        self._ipv4 = ipv4
        self._resolve_log: list[IPv4Address] = list()

    def resolve(self, dns_name: str) -> IPv4Address:
        self._resolve_log.append(self._ipv4)
        return self._ipv4

    @property
    def ipv4(self) -> IPv4Address:
        return self._ipv4

    @ipv4.setter
    def ipv4(self, ip: IPv4Address) -> None:
        self._ipv4 = ip

    def get_history(self) -> list[IPv4Address]:
        return self._resolve_log


class TestAuthHelper(dyndnsclient.AuthHelper):
    def __init__(self):
        super().__init__()

    def authenticate(self, headers: Dict[str, str]) -> None:
        pass
