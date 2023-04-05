import re

from publicip import PublicIpSource

_dyn_dns_org_re = re.compile(
    "(?iam)Current IP Address: (?P<ip>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
)

PUBLIC_IP_SOURCES = [
    # AWS
    PublicIpSource(
        name="AWS",
        api_url="https://checkip.amazonaws.com",
        ttl_sec=60,
        get_ip_routine=lambda response: response.strip(),
    ),
    # DynDNS
    # Policies: https://help.dyn.com/remote-access-api/checkip-tool/
    PublicIpSource(
        name="DynDNS",
        api_url="http://checkip.dyndns.org",
        ttl_sec=600,
        get_ip_routine=lambda response_payload: _get_ip_with_re(
            response_payload, _dyn_dns_org_re
        ),
    ),
    # WtfIsMyIP
    # Policy: https://www.wtfismyip.com/automation
    PublicIpSource(
        name="WtfIsMyIP",
        api_url="https://ipv4.wtfismyip.com/text",
        ttl_sec=60,
        get_ip_routine=lambda response: response.strip(),
    ),
    # ICanHazIP (Cloudflare at this point)
    PublicIpSource(
        name="ICanHazIP",
        api_url="https://ipv4.icanhazip.com",
        ttl_sec=60,
        get_ip_routine=lambda response: response.strip(),
    ),
    # My-IP.io
    PublicIpSource(
        name="My-IP.io",
        api_url="https://api4.my-ip.io/ip",
        ttl_sec=60,
        get_ip_routine=lambda response: response.strip(),
    ),
]


def _get_ip_with_re(self, response_payload: str, exp: re.Pattern) -> str:
    match = exp.search(response_payload)
    if match is None:
        return None
    return match.groupdict().get("ip", None)
