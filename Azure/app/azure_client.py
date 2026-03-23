"""Azure REST API client with pagination and rate-limit handling."""

import time
import logging
from typing import Optional

import requests

from auth import AzureAuthenticator
from constants import (
    AZURE_GOV_ARM_ENDPOINT,
    AZURE_COM_ARM_ENDPOINT,
    CLOUD_ENV_GOV,
)

logger = logging.getLogger(__name__)


class AzureClient:
    """REST client for Azure Resource Manager APIs with automatic pagination
    and rate-limit/retry handling."""

    def __init__(self, authenticator: AzureAuthenticator,
                 cloud_environment: str = CLOUD_ENV_GOV):
        self.authenticator = authenticator
        self.session = requests.Session()

        if cloud_environment == CLOUD_ENV_GOV:
            self.arm_endpoint = AZURE_GOV_ARM_ENDPOINT
        else:
            self.arm_endpoint = AZURE_COM_ARM_ENDPOINT

    def _get_headers(self) -> dict:
        token = self.authenticator.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def get(self, path: str, api_version: str,
            params: Optional[dict] = None) -> dict:
        """Make a GET request to an ARM API path.

        Args:
            path: API path (e.g., /subscriptions/{id}/providers/...)
            api_version: Azure API version string
            params: Additional query parameters

        Returns:
            Parsed JSON response body
        """
        url = f"{self.arm_endpoint}{path}"
        query = {"api-version": api_version}
        if params:
            query.update(params)

        return self._request_with_retry("GET", url, query)

    def get_all(self, path: str, api_version: str,
                params: Optional[dict] = None) -> list:
        """Make a paginated GET request, following nextLink until exhausted.

        Returns:
            Combined list of all items from the 'value' arrays across pages.
        """
        url = f"{self.arm_endpoint}{path}"
        query = {"api-version": api_version}
        if params:
            query.update(params)

        all_items = []

        while url:
            response = self._request_with_retry("GET", url, query)
            items = response.get("value", [])
            all_items.extend(items)

            # nextLink is a full URL — use it directly, no extra query params
            next_link = response.get("nextLink")
            if next_link:
                url = next_link
                query = {}  # nextLink includes all params
            else:
                url = None

        return all_items

    def _request_with_retry(self, method: str, url: str,
                            params: Optional[dict] = None,
                            max_retries: int = 3) -> dict:
        """Execute a request with retry on 429 (rate limit) and 5xx errors."""
        for attempt in range(max_retries + 1):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    headers=self._get_headers(),
                    params=params,
                    timeout=60,
                )

                # Log remaining rate limit
                remaining = response.headers.get(
                    "x-ms-ratelimit-remaining-subscription-reads"
                )
                if remaining:
                    logger.debug("Rate limit remaining: %s", remaining)

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 30))
                    logger.warning(
                        "Rate limited (429). Waiting %s seconds (attempt %d/%d)",
                        retry_after, attempt + 1, max_retries
                    )
                    if attempt < max_retries:
                        time.sleep(retry_after)
                        continue
                    response.raise_for_status()

                # Retry on server errors
                if response.status_code >= 500:
                    logger.warning(
                        "Server error %d (attempt %d/%d)",
                        response.status_code, attempt + 1, max_retries
                    )
                    if attempt < max_retries:
                        time.sleep(2 ** attempt)
                        continue
                    response.raise_for_status()

                response.raise_for_status()
                return response.json()

            except requests.exceptions.ConnectionError as e:
                logger.warning(
                    "Connection error (attempt %d/%d): %s",
                    attempt + 1, max_retries, e
                )
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise

        return {}  # Should not reach here
