import dns.rdatatype
import dns.resolver
import datetime
import google.auth.transport.requests
import google.oauth2.id_token
import google.oauth2.service_account
import json
import logging
import requests

from abc import ABC, abstractclassmethod
from ipaddress import ip_address, IPv4Address
from typing import Dict

logger = logging.getLogger(__name__)


class DnsResolver(ABC):
    @abstractclassmethod
    def resolve(dns_name: str) -> IPv4Address:
        pass


class AuthHelper(ABC):
    @abstractclassmethod
    def authenticate(headers: Dict[str, str]) -> None:
        pass


class DynDnsClient:
    class PythonDnsResolverWrapper(DnsResolver):
        def __init__(self) -> None:
            super().__init__()
            dns_resolver = dns.resolver.Resolver()
            dns_resolver.nameservers = ["1.1.1.1", "8.8.8.8"]
            self._dns_resolver = dns_resolver

        def resolve(self, dns_name: str) -> IPv4Address:
            answer = self._dns_resolver.resolve(
                qname=dns_name, rdtype=dns.rdatatype.A, raise_on_no_answer=True
            )
            rrset = [record.to_text() for record in answer.rrset]

            if len(rrset) > 1:
                raise ValueError(
                    f"DNS A record for {dns_name} has more than one IP address. This is not supported."
                )
            if len(rrset) < 1:
                return None

            logger.info(f"Obtained IP address {rrset[0]} for {dns_name}")

            try:
                ip = ip_address(rrset[0])
                if not isinstance(ip, IPv4Address):
                    logger.error(
                        f"Obtained IP address ({rrset[0]}) is not a valid IPv4 address"
                    )
                else:
                    return ip
            except:
                logger.error(f"Failed to obtain IPv4 address from rrset: {rrset[0]}")

            return None

    class GoogleAuthHelper(AuthHelper):
        def __init__(self, dyn_dns_api_url: str) -> None:
            super().__init__()
            self._id_token = None
            self._dyn_dns_api_url = dyn_dns_api_url

        def authenticate(self, headers: Dict[str, str]) -> None:
            if self._id_token is None or self._id_token.expired:
                logger.info(
                    "An Id Token needs to be generated to call the DynDNS Function."
                )
                self._id_token = self._get_id_token()
            self._id_token.apply(headers=headers)

        def _get_id_token(self) -> google.oauth2.service_account.IDTokenCredentials:
            logger.info(f"Obtaining new Id Token for {self._dyn_dns_api_url}")

            id_token = google.oauth2.id_token.fetch_id_token_credentials(
                audience=self._dyn_dns_api_url
            )
            auth_req = google.auth.transport.requests.Request()

            id_token.refresh(request=auth_req)
            if id_token.expired or not id_token.valid:
                logger.error("Failed to obtain a valid Id Token.")
                return None

            logger.info(f"Obtained a new token with expiry date: {id_token.expiry}")
            return id_token

    def __init__(
        self,
        zone_name: str,
        zone_dns_name: str,
        dyn_dns_api_url: str,
        hostname: str,
        dns_cache_ttl_sec: int,
        dns_resolver: DnsResolver = None,
        auth_helper: AuthHelper = None,
    ) -> None:
        self._zone_name = zone_name
        self._zone_dns_name = zone_dns_name
        self._dyn_dns_api_url = dyn_dns_api_url
        self._hostname = hostname
        self._dns_cache_ttl_sec = dns_cache_ttl_sec
        self._current_ip = None
        self._last_dns_query_timestamp = 0

        if dns_resolver is None:
            dns_resolver = self.PythonDnsResolverWrapper()

        if auth_helper is None:
            auth_helper = self.GoogleAuthHelper(dyn_dns_api_url=dyn_dns_api_url)

        self._dns_resolver = dns_resolver
        self._auth_helper = auth_helper

    def update_dns_record(self, ipv4: IPv4Address) -> None:
        now = datetime.datetime.utcnow().timestamp()
        if (now - self._last_dns_query_timestamp) >= self._dns_cache_ttl_sec:
            logger.info(f"Local DNS cache for {self._hostname} has expired.")
            self._current_ip = self._query_dns(dns_name=self._hostname)
            self._last_dns_query_timestamp = now

        if self._current_ip == ipv4:
            logger.info(f"The Public IP has not changed.", extra={"ip_change": 0})
            return

        logger.info(
            f"The Public IP has changed from {self._current_ip} to {ipv4}",
            extra={"ip_change": 1},
        )

        success = self._update_dns_record(ipv4=ipv4.exploded)

        if success:
            self._current_ip = ipv4

    def _query_dns(self, dns_name: str) -> IPv4Address:
        logger.info(
            f"Performing a DNS query for {dns_name} to obtain the current IP address.",
            extra={"dns_query": 1},
        )
        ipv4 = self._dns_resolver.resolve(dns_name=dns_name)
        logger.info(
            f"Obtained IP address: {ipv4.exploded}.",
            extra={"dns_response": 1, "ip": ipv4.exploded},
        )
        return ipv4

    def _update_dns_record(self, ipv4: str):
        headers = {
            "Content-Type": "application/json",
        }
        self._auth_helper.authenticate(headers=headers)

        data = {
            "zone_name": self._zone_name,
            "zone_dns_name": self._zone_dns_name,
            "hostname": self._hostname,
            "ip_address": ipv4,
        }

        try:
            response = requests.post(
                url=self._dyn_dns_api_url, headers=headers, data=json.dumps(data)
            )
            response.raise_for_status()
            logger.info(f"DynDNS API response payload: {response.content}")
            logger.info(
                f"Successfully updated the {self._hostname} DNS A record with IP {ipv4}",
                extra={"status_code": response.status_code},
            )
            return True
        except requests.exceptions.RequestException as re:
            logger.error("Failed to call DynDNS function.")
            logger.exception(re)

        return False

    def _get_id_token(self) -> google.oauth2.service_account.IDTokenCredentials:
        logger.info(f"Obtaining new Id Token for {self._dyn_dns_api_url}")

        id_token = google.oauth2.id_token.fetch_id_token_credentials(
            audience=self._dyn_dns_api_url
        )
        auth_req = google.auth.transport.requests.Request()

        id_token.refresh(request=auth_req)
        if id_token.expired or not id_token.valid:
            logger.error("Failed to obtain a valid Id Token.")
            return None

        logger.info(f"Obtained a new token with expiry date: {id_token.expiry}")
        return id_token
