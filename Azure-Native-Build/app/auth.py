"""OAuth2 client credentials authentication for Azure Government Cloud."""

import time
import logging
import requests

from constants import (
    AZURE_GOV_AUTH_ENDPOINT,
    AZURE_GOV_TOKEN_SCOPE,
    AZURE_COM_AUTH_ENDPOINT,
    AZURE_COM_TOKEN_SCOPE,
    CLOUD_ENV_GOV,
)

logger = logging.getLogger(__name__)


class AzureAuthenticator:
    """Handles OAuth2 client credentials flow for Azure Gov and Commercial."""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str,
                 cloud_environment: str = CLOUD_ENV_GOV):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.cloud_environment = cloud_environment

        if cloud_environment == CLOUD_ENV_GOV:
            self.auth_endpoint = AZURE_GOV_AUTH_ENDPOINT
            self.token_scope = AZURE_GOV_TOKEN_SCOPE
        else:
            self.auth_endpoint = AZURE_COM_AUTH_ENDPOINT
            self.token_scope = AZURE_COM_TOKEN_SCOPE

        self._access_token = None
        self._token_expiry = 0

    @property
    def token_url(self) -> str:
        return f"{self.auth_endpoint}/{self.tenant_id}/oauth2/v2.0/token"

    def get_token(self) -> str:
        """Get a valid access token, refreshing if expired or near expiry."""
        # Refresh if token expires within 5 minutes
        if self._access_token and time.time() < (self._token_expiry - 300):
            return self._access_token

        return self._acquire_token()

    def _acquire_token(self) -> str:
        """Acquire a new access token via client credentials flow."""
        logger.info("Acquiring new access token from %s", self.token_url)

        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.token_scope,
        }

        response = requests.post(
            self.token_url,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        response.raise_for_status()

        token_data = response.json()
        self._access_token = token_data["access_token"]
        self._token_expiry = time.time() + token_data.get("expires_in", 3599)

        logger.info("Access token acquired, expires in %s seconds",
                     token_data.get("expires_in", "unknown"))
        return self._access_token

    def test_connection(self) -> bool:
        """Test that credentials are valid by acquiring a token."""
        try:
            self._acquire_token()
            return True
        except requests.exceptions.HTTPError as e:
            logger.error("Authentication failed: %s", e)
            raise
