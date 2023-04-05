import datetime
import logging
import unittest
import publicip
import time

import tests.test_logger

from enum import Enum, auto
from ipaddress import ip_address, IPv4Address
from logging.handlers import MemoryHandler
from tests.test_httpserver import (
    TestHttpRequestHandler,
    TestHttpServer,
    TestHttpServerHandler,
)
from tests.test_logger import LogAssertions
from typing import Callable, Dict

logger = logging.getLogger(__name__)


class PublicIpTest(unittest.TestCase):
    def setUp(self):
        self._get_handler = PublicIpApiHttpHandler()
        self._post_handler = TestHttpRequestHandler()
        self._server_handler = TestHttpServerHandler(
            get_handler=self._get_handler, post_handler=self._post_handler
        )
        self._server = TestHttpServer(server_handler=self._server_handler)

        for handler in logger.root.handlers:
            if type(handler) is MemoryHandler:
                handler.flush()

    def tearDown(self):
        self._server.stop()

    #####
    # PublicIpSource Tests
    #####

    class PublicIpSourceOutcome(Enum):
        DISABLED = auto()
        UNEXPIRED_TTL = auto()
        IP_SOURCE_DISABLE_EVENT = auto()
        HTTP_429_EVENT = auto()
        HTTP_ERROR_EVENT = auto()
        PAYLOAD_ERROR = auto()
        INVALID_IP_ERROR = auto()
        SUCCESS = auto()

    def _test_ip_source_get_my_public_ip(
        self,
        public_ip_source: publicip.PublicIpSource,
        expected_outcome: PublicIpSourceOutcome,
        expected_ip: IPv4Address = None,
    ):
        with self._server:
            request_count = self._get_handler.request_count
            last_poll_timestamp = public_ip_source.last_poll_timestamp
            next_poll_timestamp = public_ip_source.next_poll_timestamp
            last_successful_poll_timestamp = (
                public_ip_source.last_successful_poll_timestamp
            )
            consecutive_http_error_count = public_ip_source.consecutive_http_error_count
            consecutive_http_429_count = public_ip_source.consecutive_http_429_count
            consecutive_error_count = public_ip_source.consecutive_error_count
            enabled = public_ip_source.enabled

            now = datetime.datetime.utcnow().timestamp()
            ip = public_ip_source.get_my_public_ip()
            self.assertEqual(ip, expected_ip)

            if expected_outcome in [
                self.PublicIpSourceOutcome.DISABLED,
                self.PublicIpSourceOutcome.UNEXPIRED_TTL,
            ]:
                self.assertEqual(self._get_handler.request_count, request_count)
                self.assertEqual(
                    public_ip_source.last_poll_timestamp, last_poll_timestamp
                )
                self.assertEqual(
                    public_ip_source.next_poll_timestamp, next_poll_timestamp
                )
                self.assertEqual(
                    public_ip_source.last_successful_poll_timestamp,
                    last_successful_poll_timestamp,
                )
                self.assertEqual(
                    public_ip_source.consecutive_http_error_count,
                    consecutive_http_error_count,
                )
                self.assertEqual(
                    public_ip_source.consecutive_http_429_count,
                    consecutive_http_429_count,
                )
                self.assertEqual(
                    public_ip_source.consecutive_error_count,
                    consecutive_error_count,
                )
                self.assertEqual(public_ip_source.enabled, enabled)
                if expected_outcome == self.PublicIpSourceOutcome.DISABLED:
                    self.assert_last_log().is_error().has_message_containing(
                        "Tried to obtain the Public IP using a disabled API"
                    )
                elif expected_outcome == self.PublicIpSourceOutcome.UNEXPIRED_TTL:
                    self.assert_last_log().is_error().has_message_containing(
                        "Tried to obtain the Public IP using an API with an unexpired TTL"
                    )
                return

            self.assertEqual(self._get_handler.request_count, request_count + 1)
            self.assertGreater(public_ip_source.last_poll_timestamp, now)
            if last_poll_timestamp is not None:
                self.assertGreater(
                    public_ip_source.last_poll_timestamp, last_poll_timestamp
                )

            if expected_outcome != self.PublicIpSourceOutcome.SUCCESS:
                self.assertEqual(
                    public_ip_source.last_successful_poll_timestamp,
                    last_successful_poll_timestamp,
                )
                self.assertEqual(
                    public_ip_source.consecutive_error_count,
                    consecutive_error_count + 1,
                )

            if expected_outcome == self.PublicIpSourceOutcome.IP_SOURCE_DISABLE_EVENT:
                self.assertEqual(public_ip_source.enabled, False)
                self.assert_last_error_log().has_message_containing(
                    f"Disabling Public API {public_ip_source._name} from the list of sources. Last successful call was on {public_ip_source._last_successful_poll}"
                )
                return

            self.assertEqual(public_ip_source.enabled, True)

            if expected_outcome == self.PublicIpSourceOutcome.HTTP_429_EVENT:
                back_off_time = pow(
                    publicip.PublicIpSource._backoff_factor,
                    public_ip_source.consecutive_http_429_count,
                )
                self.assertEqual(
                    public_ip_source.next_poll_timestamp,
                    public_ip_source.last_poll_timestamp
                    + public_ip_source.ttl_sec
                    + back_off_time,
                )
                self.assertEqual(
                    public_ip_source.consecutive_http_error_count,
                    consecutive_http_error_count,
                )
                self.assertEqual(
                    public_ip_source.consecutive_http_429_count,
                    consecutive_http_429_count + 1,
                )
                self.assert_last_warn_log().has_message_containing(
                    f"Got a HTTP 429. Backing off for {back_off_time} seconds."
                )
                return

            self.assertEqual(
                public_ip_source.next_poll_timestamp,
                public_ip_source.last_poll_timestamp + public_ip_source.ttl_sec,
            )
            self.assertEqual(public_ip_source.consecutive_http_429_count, 0)

            if expected_outcome == self.PublicIpSourceOutcome.HTTP_ERROR_EVENT:
                self.assertEqual(
                    public_ip_source.consecutive_http_error_count,
                    consecutive_http_error_count + 1,
                )
                self.assert_last_warn_log().has_message_containing(
                    f"The request failed with a HttpError exception. Error message:"
                )
                return

            self.assertEqual(public_ip_source.consecutive_http_error_count, 0)
            self.assertEqual(public_ip_source.consecutive_http_429_count, 0)

            if expected_outcome == self.PublicIpSourceOutcome.PAYLOAD_ERROR:
                self.assert_last_log().is_error().has_message_containing(
                    "Failed to obtain Public IP address from response payload"
                )
                return

            if expected_outcome == self.PublicIpSourceOutcome.INVALID_IP_ERROR:
                self.assert_last_log().is_error().has_message_containing(
                    "The IP address obtained is not a valid public IPv4 address"
                )
                return

            if expected_outcome == self.PublicIpSourceOutcome.SUCCESS:
                self.assertEqual(
                    public_ip_source.last_successful_poll_timestamp,
                    public_ip_source.last_poll_timestamp,
                )
                self.assertEqual(public_ip_source.consecutive_error_count, 0)
                self.assert_last_log().is_info().has_message_containing(
                    f"Obtained IP address {self._get_handler.ipv4} from {public_ip_source.name}"
                )

    def test_GIVEN_validResponse_WHEN_getMyPublicIp_THEN_succeed(self):
        public_ip_source = self._create_public_ip_source()
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.SUCCESS,
            expected_ip=self._get_handler.ipv4,
        )

    def test_GIVEN_privateIpResponse_WHEN_getMyPublicIp_THEN_returnNone(self):
        public_ip_source = self._create_public_ip_source()
        self._get_handler.ipv4 = ip_address("127.0.0.1")
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.INVALID_IP_ERROR,
            expected_ip=None,
        )

    def test_GIVEN_ipRoutineFails_WHEN_getMyPublicIp_THEN_returnNone(self):
        def bad_ip_routine(input: str) -> None:
            raise ValueError()

        public_ip_source = self._create_public_ip_source(get_ip_routine=bad_ip_routine)
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.PAYLOAD_ERROR,
            expected_ip=None,
        )

    def test_GIVEN_ipv6Response_WHEN_getMyPublicIp_THEN_returnNone(self):
        self._get_handler.response = "2ff8:fe54:2ea9:f21b:530f:c230:b4b8:d952"
        public_ip_source = self._create_public_ip_source()
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.INVALID_IP_ERROR,
            expected_ip=None,
        )

    def test_GIVEN_invalidResponse_WHEN_getMyPublicIp_THEN_returnNone(self):
        self._get_handler.response = "Random text"
        public_ip_source = self._create_public_ip_source()
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.INVALID_IP_ERROR,
            expected_ip=None,
        )

    def test_GIVEN_invalidIPv4Response_WHEN_getMyPublicIp_THEN_returnNone(self):
        self._get_handler.response = "31.16.441.203"
        public_ip_source = self._create_public_ip_source()
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.INVALID_IP_ERROR,
            expected_ip=None,
        )

    def test_GIVEN_sourceWithTtlZero_WHEN_getMyPublicIp_THEN_succeed(self):
        public_ip_source = self._create_public_ip_source(ttl=0)
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.SUCCESS,
            expected_ip=self._get_handler.ipv4,
        )
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.SUCCESS,
            expected_ip=self._get_handler.ipv4,
        )

    def test_GIVEN_sourceWithUnexpiredTtl_WHEN_getMyPublicIp_THEN_returnNone(
        self,
    ):
        public_ip_source = self._create_public_ip_source()
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.SUCCESS,
            expected_ip=self._get_handler.ipv4,
        )
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.UNEXPIRED_TTL,
            expected_ip=None,
        )

    def test_GIVEN_http500_WHEN_getMyPublicIp_THEN_returnNone(self):
        self._get_handler.status_code = 500
        public_ip_source = self._create_public_ip_source(ttl=0)
        for cnt in range(0, 10):
            self._test_ip_source_get_my_public_ip(
                public_ip_source=public_ip_source,
                expected_outcome=self.PublicIpSourceOutcome.HTTP_ERROR_EVENT,
                expected_ip=None,
            )

    def test_GIVEN_successAfterHttp500_WHEN_getMyPublicIp_THEN_resetErrorState(self):
        public_ip_source = self._create_public_ip_source(ttl=0)
        self._get_handler.status_code = 500
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.HTTP_ERROR_EVENT,
            expected_ip=None,
        )
        self._get_handler.status_code = 200
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.SUCCESS,
            expected_ip=self._get_handler.ipv4,
        )

    def test_GIVEN_http429_WHEN_getMyPublicIp_THEN_returnNone_AND_backOff(self):
        self._get_handler.status_code = 429
        public_ip_source = self._create_public_ip_source(ttl=0)
        for cnt in range(0, 10):
            public_ip_source._next_poll_timestamp = 0
            self._test_ip_source_get_my_public_ip(
                public_ip_source=public_ip_source,
                expected_outcome=self.PublicIpSourceOutcome.HTTP_429_EVENT,
                expected_ip=None,
            )

    def test_GIVEN_successAfterHttp429_WHEN_getMyPublicIp_THEN_resetErrorState(self):
        public_ip_source = self._create_public_ip_source(ttl=0)
        self._get_handler.status_code = 429
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.HTTP_429_EVENT,
            expected_ip=None,
        )
        public_ip_source._next_poll_timestamp = 0
        self._get_handler.status_code = 200
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.SUCCESS,
            expected_ip=self._get_handler.ipv4,
        )

    def test_GIVEN_noSuccess_WHEN_getMyPublicIp_THEN_disableSource(self):
        max_inactive_secs = 1
        public_ip_source = self._create_public_ip_source(
            ttl=0, max_inactive_secs=max_inactive_secs
        )
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.SUCCESS,
            expected_ip=self._get_handler.ipv4,
        )

        self._get_handler.status_code = 500
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.HTTP_ERROR_EVENT,
            expected_ip=None,
        )

        time.sleep(max_inactive_secs + 1)
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.IP_SOURCE_DISABLE_EVENT,
            expected_ip=None,
        )

    def test_GIVEN_disabledSource_WHEN_getMyPublicIp_THEN_None(self):
        public_ip_source = self._create_public_ip_source()
        public_ip_source._enabled = False
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.DISABLED,
            expected_ip=None,
        )

    def test_all(self):
        public_ip_source = self._create_public_ip_source(ttl=0)

        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.SUCCESS,
            expected_ip=self._get_handler.ipv4,
        )

        self._get_handler.status_code = 500
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.HTTP_ERROR_EVENT,
            expected_ip=None,
        )

        self._get_handler.status_code = 200
        self._get_handler.response = "X.X.X.X"
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.INVALID_IP_ERROR,
            expected_ip=None,
        )

        self._get_handler.response = "31.26.44.254"
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.SUCCESS,
            expected_ip=self._get_handler.ipv4,
        )

        self._get_handler.status_code = 429
        self._test_ip_source_get_my_public_ip(
            public_ip_source=public_ip_source,
            expected_outcome=self.PublicIpSourceOutcome.HTTP_429_EVENT,
            expected_ip=None,
        )

    #####
    # MyPublicIP Tests
    #####

    def test_GIVEN_publicIpSourceReady_WHEN_getMyPublicIp_THEN_returnIpv4(self):
        with self._server:
            my_public_ip_source = self._create_public_ip_source()
            my_public_ip = publicip.MyPublicIP(public_ip_sources=[my_public_ip_source])
            self.assertEqual(my_public_ip.get_my_public_ip(), self._get_handler.ipv4)

    def test_GIVEN_publicIpSourceNotReady_WHEN_getMyPublicIp_THEN_None(self):
        with self._server:
            my_public_ip_source = self._create_public_ip_source()
            my_public_ip = publicip.MyPublicIP(public_ip_sources=[my_public_ip_source])
            self.assertEqual(my_public_ip.get_my_public_ip(), self._get_handler.ipv4)
            self.assertEqual(my_public_ip.get_my_public_ip(), None)
            self.assert_last_log().is_error().has_message_containing(
                "Could not find a Public IP API with an expired TTL"
            )

    def test_GIVEN_onePublicIpSourceHttp500_WHEN_getMyPublicIp_THEN_None(self):
        with self._server:
            self._get_handler.status_code = 500
            my_public_ip_source = self._create_public_ip_source()
            my_public_ip = publicip.MyPublicIP(public_ip_sources=[my_public_ip_source])

            now = datetime.datetime.utcnow().timestamp()
            self.assertEqual(my_public_ip.get_my_public_ip(), None)
            self.assert_last_error_log().is_newer_than(now).has_message_containing(
                "Could not find a Public IP API with an expired TTL"
            )
            self.assert_last_warn_log().is_newer_than(now).has_message_containing(
                f"Could not obtain the Public IP address from {my_public_ip_source._name}"
            )

    def test_GIVEN_zeroPublicIpSources_WHEN_getMyPublicIp_THEN_None(self):
        with self._server:
            now = datetime.datetime.utcnow().timestamp()
            my_public_ip = publicip.MyPublicIP(public_ip_sources=[])
            self.assertEqual(my_public_ip.get_my_public_ip(), None)
            self.assert_nth_to_last_log(1).is_error().is_newer_than(
                now
            ).has_message_containing(
                "Could not find a Public IP API with an expired TTL"
            )
            self.assert_nth_to_last_log(2).is_error().is_newer_than(
                now
            ).has_message_containing("The list of Public IPv4 sources is empty")

    def test_GIVEN_multiplePublicIpSources_WHEN_getMyPublicIp_THEN_roundRobin(self):
        public_ip_sources = [
            self._create_public_ip_source(name="Source[0]"),
            self._create_public_ip_source(name="Source[1]"),
            self._create_public_ip_source(name="Source[2]"),
            self._create_public_ip_source(name="Source[3]"),
            self._create_public_ip_source(name="Source[4]"),
        ]
        first_ip_source_index = 2
        my_public_ip = publicip.MyPublicIP(public_ip_sources=public_ip_sources)
        my_public_ip._next_api_index = first_ip_source_index
        with self._server:
            for cnt in range(0, len(public_ip_sources)):
                next_ip_source_index = (first_ip_source_index + cnt) % len(
                    public_ip_sources
                )
                self.assertEqual(
                    my_public_ip.get_my_public_ip(), self._get_handler.ipv4
                )
                self.assert_last_log().is_info().has_message_containing(
                    f"Obtained IP address {self._get_handler.ipv4} from {public_ip_sources[next_ip_source_index].name}"
                )

    def assert_last_error_log(self) -> LogAssertions:
        return LogAssertions.assert_last_error_log()

    def assert_last_warn_log(self) -> LogAssertions:
        return LogAssertions.assert_last_warn_log()

    def assert_last_log(self) -> LogAssertions:
        return LogAssertions.assert_last_log()

    def assert_nth_to_last_log(self, n: int) -> LogAssertions:
        return LogAssertions.assert_nth_to_last_log(n)

    def _create_public_ip_source(
        self,
        name: str = "Test-Source",
        ttl: int = 60,
        get_ip_routine: Callable[[str], str] = lambda response: response.strip(),
        max_inactive_secs: int = datetime.timedelta(days=30).total_seconds(),
    ) -> publicip.PublicIpSource:
        return publicip.PublicIpSource(
            name="Test_Source",
            api_url=f"http://{self._server.address}:{self._server.port}",
            ttl_sec=ttl,
            get_ip_routine=get_ip_routine,
            max_inactive_secs=max_inactive_secs,
        )


class PublicIpApiHttpHandler(TestHttpRequestHandler):
    def __init__(
        self,
        status_code: int = 200,
        headers: Dict[str, str] = {"Content-type": "text/plain"},
        response_payload: str = "31.16.44.203",
    ) -> None:
        super().__init__(status_code=status_code, response_payload=response_payload)

    @property
    def ipv4(self) -> IPv4Address:
        try:
            ipv4 = ip_address(self._response_payload)
            if type(ipv4) is not IPv4Address:
                raise None
            return ipv4
        except ValueError:
            return None

    @ipv4.setter
    def ipv4(self, ipv4: IPv4Address):
        self._response_payload = ipv4.exploded
