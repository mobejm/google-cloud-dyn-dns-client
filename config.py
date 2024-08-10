import dotenv
import logging
import logging.config
import os
import sys

from pathlib import Path

logger = logging.getLogger(__name__)


class Config:
    def __init__(self):
        logger.info("Loading the application configuration from environment.")
        if os.path.isfile(".env"):
            logger.info("An .env file was found.")
            env_path = os.path.join(".", ".env")
            dotenv.load_dotenv(dotenv_path=env_path)

        # Mandatory environment variables
        self.zone_name = os.environ.get("ZONE_NAME")
        self.zone_dns_name = os.environ.get("ZONE_DNS_NAME")
        self.api_url = os.environ.get("DYN_DNS_API_URL")
        self.hostname = os.environ.get("HOSTNAME")
        self.auth_key_file_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

        # Optional settings
        self.dns_record_ttl_sec = int(os.environ.get("DNS_RECORD_DEFAULT_TTL", 300))
        self.interval_sec = int(os.environ.get("PUBLIC_IP_CHECK_INTERVAL_SEC", 300))
        self.pid_file_path = os.environ.get("PID_FILE_PATH", None)

        if self.api_url is None:
            logger.error("DYN_DNS_API_URL environment variable is missing.")
            sys.exit(1)

        if self.hostname is None:
            logger.error("DNS_DOMAIN environment variable is missing.")
            sys.exit(1)

        if self.auth_key_file_path is None:
            logger.error(
                "GOOGLE_APPLICATION_CREDENTIALS environment variable is missing."
            )
            sys.exit(1)

        google_cred_path = Path(self.auth_key_file_path)
        if not google_cred_path.is_file() or not google_cred_path.exists():
            logger.error(
                f"Path to Google Cloud Credentials doesn't exist or is not readable: {self.auth_key_file_path}"
            )
            sys.exit(1)
