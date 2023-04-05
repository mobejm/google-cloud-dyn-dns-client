import dyndnsclient
import logger
import logging
import logging.config
import publicip
import time

from config import Config
from publicipsources import PUBLIC_IP_SOURCES

logger = logging.getLogger(__name__)


def dyn_dns_client() -> None:
    app_config = Config()
    public_ip_provider = publicip.MyPublicIP(public_ip_sources=PUBLIC_IP_SOURCES)
    dyn_dns_client = dyndnsclient.DynDnsClient(
        dyn_dns_api_url=app_config.api_url,
        hostname=app_config.hostname,
        dns_cache_ttl_sec=app_config.dns_record_ttl_sec,
    )

    while True:
        try:
            public_ip = public_ip_provider.get_my_public_ip()
            if public_ip:
                dyn_dns_client.update_dns_record(ipv4=public_ip)
        except Exception as e:
            logger.exception(e)
        logger.info(f"Sleeping for {app_config.interval_sec} seconds.")
        time.sleep(app_config.interval_sec)


if __name__ == "__main__":
    dyn_dns_client()
