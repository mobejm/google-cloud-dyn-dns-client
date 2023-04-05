import datetime
import logging
import logging.config
import random
import re
import requests
import sys

from ipaddress import ip_address, IPv4Address
from typing import Callable

logger = logging.getLogger(__name__)


class PublicIpSource:
    _backoff_factor = 1.5

    def __init__(
        self,
        name: str,
        api_url: str,
        ttl_sec: int,
        get_ip_routine: Callable[[str], str],
        max_inactive_secs: int = datetime.timedelta(days=30).total_seconds(),
    ):
        now = datetime.datetime.utcnow().timestamp()
        self._enabled = True
        self._name = name
        self._api_url = api_url
        self._ttl_sec = ttl_sec
        self._max_inactive_secs = max_inactive_secs
        self._get_ip_routine = get_ip_routine
        self._last_poll_timestamp = None
        self._next_poll_timestamp = 0
        self._last_successful_poll = None
        self._consecutive_http_error_count = 0
        self._consecutive_http_429_count = 0
        self._consecutive_error_count = 0
        self._epoch_timestamp = now

    @property
    def enabled(self):
        return self._enabled

    @property
    def name(self) -> str:
        return self._name

    @property
    def api_url(self) -> str:
        return self._api_url

    @property
    def ttl_sec(self) -> int:
        return self._ttl_sec

    @property
    def get_ip_routine(self) -> Callable[[str], str]:
        return self._get_ip_routine

    @property
    def last_poll_timestamp(self):
        return self._last_poll_timestamp

    @property
    def next_poll_timestamp(self):
        return self._next_poll_timestamp

    @property
    def last_successful_poll_timestamp(self):
        return self._last_successful_poll

    @property
    def consecutive_http_error_count(self):
        return self._consecutive_http_error_count

    @property
    def consecutive_http_429_count(self):
        return self._consecutive_http_429_count

    @property
    def consecutive_error_count(self):
        return self._consecutive_error_count

    def get_my_public_ip(self) -> IPv4Address:
        now = datetime.datetime.utcnow().timestamp()

        if not self.enabled:
            logger.error("Tried to obtain the Public IP using a disabled API")
            return None

        if now < self._next_poll_timestamp:
            logger.error(
                "Tried to obtain the Public IP using an API with an unexpired TTL"
            )
            return None

        self._last_poll_timestamp = now
        self._next_poll_timestamp = now + self._ttl_sec

        try:
            response = requests.get(self._api_url, timeout=5)
            response.raise_for_status()
        except requests.exceptions.RequestException as re:
            self._consecutive_error_count += 1
            logger.exception(re)
            if response.status_code == 429:
                # We've been throttled! (╯°□°）╯︵ ┻━┻
                self._consecutive_http_429_count += 1
                self._consecutive_http_error_count = 0
                # Exponential backoff
                back_off_time = pow(
                    self._backoff_factor, self._consecutive_http_429_count
                )
                self._next_poll_timestamp = now + self._ttl_sec + back_off_time
                logger.warning(
                    f"Got a HTTP 429. Backing off for {back_off_time} seconds."
                )
            else:
                self._consecutive_http_429_count = 0
                self._consecutive_http_error_count += 1
                logger.warning(
                    f"The request failed with a {type(re).__name__} exception. Error message: {re.strerror}"
                )
            self._check_for_expiration(now)
            return None

        self._consecutive_http_429_count = 0
        self._consecutive_http_error_count = 0

        encoded_payload = "\\n".join(line for line in response.text.splitlines())
        logger.info(f"Response payload: {encoded_payload}")

        try:
            ip_address_str = self._get_ip_routine(response.text)
            logger.info(
                f"Obtained IP address {ip_address_str} from {self._name}",
                extra={"ip_address": ip_address_str, "source": self._api_url},
            )
        except Exception as e:
            self._consecutive_error_count += 1
            logger.exception(e)
            logger.error("Failed to obtain Public IP address from response payload.")
            self._check_for_expiration(now)
            return None

        try:
            ip = ip_address(ip_address_str)
            if not ip.is_global or type(ip) is not IPv4Address:
                raise ValueError
        except ValueError as e:
            self._consecutive_error_count += 1
            logger.exception(e)
            logger.error("The IP address obtained is not a valid public IPv4 address.")
            self._check_for_expiration(now)
            return None

        self._last_successful_poll = now
        self._consecutive_error_count = 0

        return ip

    def _check_for_expiration(self, now: float) -> None:
        start_time = self._last_successful_poll or self._epoch_timestamp
        # Was the last successful call was over _max_inactive_sec seconds ago?
        if (now - start_time) > self._max_inactive_secs:
            # We've been getting errors for too long. We give up! ┻━┻ ︵ヽ(`Д´)ﾉ︵﻿ ┻━┻
            logger.error(
                f"Disabling Public API {self._name} from the list of sources. Last successful call was on {self._last_successful_poll}"
            )
            self._next_poll_timestamp = None
            self._enabled = False


class MyPublicIP:
    def __init__(self, public_ip_sources: list[PublicIpSource]):
        self._public_ip_api_sources = public_ip_sources
        self._next_api_index = None

    def get_my_public_ip(self) -> IPv4Address:
        while True:
            logger.info(f"Obtaining the next Public IP API to use.")
            next_ip_source = self._get_next_ip_source()
            if next_ip_source is None:
                logger.error("Could not find a Public IP API with an expired TTL.")
                return None
            else:
                logger.info(
                    f"Getting public IP address from {next_ip_source._name}: {next_ip_source._api_url}"
                )
                ip_address = next_ip_source.get_my_public_ip()
                if ip_address is None:
                    logger.warning(
                        f"Could not obtain the Public IP address from {next_ip_source._name}"
                    )
                    continue
                return ip_address

    def _get_next_ip_source(self) -> PublicIpSource:
        if len(self._public_ip_api_sources) < 1:
            logger.error("The list of Public IPv4 sources is empty.")
            return None

        if self._next_api_index is None:
            self._next_api_index = random.randint(
                0, len(self._public_ip_api_sources) - 1
            )

        now = datetime.datetime.utcnow().timestamp()
        for cnt in range(0, len(self._public_ip_api_sources)):
            index = (self._next_api_index + cnt) % len(self._public_ip_api_sources)
            ip_source = self._public_ip_api_sources[index]
            if ip_source.next_poll_timestamp <= now and ip_source.enabled:
                self._next_api_index = (self._next_api_index + 1) % len(
                    self._public_ip_api_sources
                )
                return ip_source
        return None
