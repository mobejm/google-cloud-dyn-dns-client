import dyndnsclient
import logger
import logging
import logging.config
import os
import platform
import publicip
import time

from config import Config
from publicipsources import PUBLIC_IP_SOURCES

logger = logging.getLogger(__name__)


def dyn_dns_client() -> None:
    app_config = Config()
    public_ip_provider = publicip.MyPublicIP(public_ip_sources=PUBLIC_IP_SOURCES)
    dyn_dns_client = dyndnsclient.DynDnsClient(
        zone_name=app_config.zone_name,
        zone_dns_name=app_config.zone_dns_name,
        dyn_dns_api_url=app_config.api_url,
        hostname=app_config.hostname,
        dns_cache_ttl_sec=app_config.dns_record_ttl_sec,
    )

    if app_config.pid_file_path is not None:
        with open(app_config.pid_file_path, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))

    while True:

        success = True
        logger.info(f"Checking for Public IP changes.", extra={"metric": "dyndns.count", "value": 1})

        try:
            public_ip = public_ip_provider.get_my_public_ip()
            if public_ip:
                success = dyn_dns_client.update_dns_record(ipv4=public_ip)
            else:
                success = False
        except Exception as e:
            success = False
            logger.exception(e)

        if success:
            logger.info(f"Successfully checked for Public IP changes and made DNS updates if needed.", extra={"metric": "dyndns.success", "value": 1})
        else:
            logger.error(f"Failed to chceck for Public IP changes and/or perform corresponding DNS updates.", extra={"metric": "dyndns.error", "value": 1})

        logger.info(f"Sleeping for {app_config.interval_sec} seconds.")
        time.sleep(app_config.interval_sec)


if __name__ == "__main__":
    dyn_dns_client()
