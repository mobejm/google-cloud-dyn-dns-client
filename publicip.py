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

class MyPublicIP:

    _dyn_dns_org_re = re.compile('(?iam)Current IP Address: (?P<ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')
    _cloudflare_re = re.compile('(?iam)^ip=(?P<ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$')

    class PublicIpSource:
        def __init__(
            self,
            name: str,
            api_url: str,
            ttl_sec: int,
            get_ip_routine: Callable[[str], str]
        ):
            self.name = name
            self.api_url = api_url
            self.ttl_sec = ttl_sec
            self.get_ip_routine = get_ip_routine
            self._last_poll = None
            self._last_successful_poll = None
            self._error_event_count = 0
            self._throttle_event_count = 0
            self._epoch_timestamp = datetime.datetime.utcnow().timestamp()

        def get_my_public_ip(self) -> str:
            now = datetime.datetime.utcnow().timestamp()
            if (self._last_poll and now < (self._last_poll + self.ttl_sec)):
                logger.error("Tried to obtain the Public IP using an API with an unexpired TTL")
                return None

            self._last_poll = now

            try:
                response = requests.get(self.api_url)
                response.raise_for_status()
            except requests.exceptions.RequestException as re:
                logger.exception(re)
                # Was the last successful call was over 30 days ago?
                if self._expired_source(now):
                    # We've been getting errors for too long. We give up! ┻━┻ ︵ヽ(`Д´)ﾉ︵﻿ ┻━┻
                    logger.error(f"Removing Public API {self.name} from the list of sources. Last successful call was on {self._last_successful_poll}")
                    self._last_poll = sys.maxsize
                elif (response.status_code == 429):
                    # We've been throttled! (╯°□°）╯︵ ┻━┻
                    self._throttle_event_count += 1
                    # Exponential backoff
                    self._last_poll = now + self.ttl_sec + (1.0 / pow(2, self._throttle_event_count))
                    logger.warn(f"Got a HTTP 429. Backing off for {self._last_poll} seconds.")
                else:
                    self._error_event_count += 1
                    logger.warn(f"The request failed with a {type(re)} error: {re.strerror}")
                return None

            encoded_payload = "\\n".join(line for line in response.text.splitlines())
            logger.info(f"Response payload: {encoded_payload}")

            try:
                ip_address = self.get_ip_routine(response.text)
                logger.info(f"Obtained IP address {ip_address} from {self.name}", extra={"ip_address": ip_address, "source": self.api_url})
            except Exception as e:
                logger.error("Failed to obtain Public IP address from response payload.")
                logger.exception(e)
                self._error_event_count += 1
                return None

            self._last_successful_poll = now
            self._throttle_event_count = 0
            self._error_event_count = 0

            return ip_address

        def next_poll_timestamp(self) -> float:
            if self._last_poll is None:
                return 0
            return self._last_poll + self.ttl_sec

        def _expired_source(self, now: float) -> bool:
            start_time = self._last_successful_poll or self._epoch_timestamp
            # Was the last successful call was over 30 days ago?
            return ((now - start_time) > datetime.timedelta(days=30).total_seconds())
                


    def __init__(self):
        self._public_ip_api_sources = [
                # AWS
                self.PublicIpSource(
                    name="AWS",
                    api_url="https://checkip.amazonaws.com",
                    ttl_sec=60,
                    get_ip_routine=lambda response : response.strip()),
                # DynDNS
                # Policies: https://help.dyn.com/remote-access-api/checkip-tool/
                self.PublicIpSource(
                    name="DynDNS", 
                    api_url="http://checkip.dyndns.org",
                    ttl_sec=600,
                    get_ip_routine=lambda response_payload : self._get_ip_with_re(response_payload, self._dyn_dns_org_re)),
                # WtfIsMyIP
                # Policy: https://www.wtfismyip.com/automation
                self.PublicIpSource(
                    name="WtfIsMyIP",
                    api_url="https://ipv4.wtfismyip.com/text",
                    ttl_sec=60,
                    get_ip_routine=lambda response : response.strip()),
                # ICanHazIP (Cloudflare at this point)
                self.PublicIpSource(
                    name="ICanHazIP",
                    api_url="https://ipv4.icanhazip.com",
                    ttl_sec=60,
                    get_ip_routine=lambda response : response.strip()),
                # My-IP.io
                self.PublicIpSource(
                    name="My-IP.io",
                    api_url="https://api4.my-ip.io/ip",
                    ttl_sec=60,
                    get_ip_routine=lambda response : response.strip()),
        ]
        self._next_api_index = random.randint(0, len(self._public_ip_api_sources) - 1)

    def get_my_public_ip(self) -> IPv4Address:
        while True:
            logger.info(f"Obtaining the next Public IP API to use.")
            next_ip_source = self._get_next_ip_source()
            if next_ip_source is None:
                logger.error("Could not find a Public IP API with an expired TTL.")
                return None
            else:
                logger.info(f"Getting public IP address from {next_ip_source.name}: {next_ip_source.api_url}")
                ip_str = next_ip_source.get_my_public_ip()
                if ip_str is None:
                    logger.warn(f"Could not obtain the Public IP address from {next_ip_source.name}")
                    continue
                try:
                    ip = ip_address(ip_str)
                    if not ip.is_global or type(ip) is not IPv4Address:
                        raise ValueError
                    return ip
                except ValueError:
                    logger.error("The IP address obtained is not a valid public IPv4 address.")
                    return None


    def _get_next_ip_source(self) -> PublicIpSource:
        now = datetime.datetime.utcnow().timestamp()
        
        for cnt in range(0, len(self._public_ip_api_sources)):
            index = (self._next_api_index + cnt) % len(self._public_ip_api_sources)
            ip_source = self._public_ip_api_sources[index]
            if (ip_source.next_poll_timestamp() <= now):
                self._next_api_index = (self._next_api_index + 1) % len(self._public_ip_api_sources)
                return ip_source

    def _get_ip_with_re(self, response_payload: str, exp: re.Pattern) -> str:
        match = exp.search(response_payload)
        if (match is None):
            return None
        return match.groupdict().get('ip', None)
