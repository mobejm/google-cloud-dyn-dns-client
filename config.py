import dotenv
import logging
import logging.config
import os
import sys

logger = logging.getLogger(__name__)

class Config():

    def __init__(self):

        logger.info("Loading the application configuration from environment.")
        if os.path.isfile('.env'):
            logger.info("An .env file was found.")
            env_path = os.Path('.') / '.env'
            dotenv.load_dotenv(dotenv_path=env_path)

        # Mandatory environment variables
        self.api_url = os.environ.get('DYN_DNS_API_URL')
        self.dns_domain = os.environ.get('DNS_DOMAIN')
        self.auth_key_file_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')

        # Optional settings
        self.dns_record_ttl_sec = os.environ.get('DNS_RECORD_DEFAULT_TTL', 300)
        self.interval_sec = os.environ.get('PUBLIC_IP_CHECK_INTERVAL_SEC', 300)

        if self.api_url is None:
            logger.error("DYN_DNS_API_URL environment variable is missing.")
            sys.exit(1)

        if self.dns_domain is None:
            logger.error("DNS_DOMAIN environment variable is missing.")
            sys.exit(1)

        if self.auth_key_file_path is None:
            logger.error("GOOGLE_APPLICATION_CREDENTIALS environment variable is missing.")
            sys.exit(1)