"""Experimenter API client."""

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

EXPERIMENTER_API_URL = "https://experimenter.services.mozilla.com/api/v8/experiments/"
MAX_RETRIES = 3


def retry_get(url: str, max_retries: int = MAX_RETRIES) -> Any:
    """Fetch JSON from URL with retry logic."""
    session = requests.Session()
    session.headers.update({"User-Agent": "metric-hub-mcp"})

    for attempt in range(max_retries):
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.info(f"Attempt {attempt + 1}/{max_retries} failed for {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
            else:
                raise Exception(f"Failed to fetch {url} after {max_retries} retries") from e


def fetch_experiments() -> list[dict[str, Any]]:
    """Fetch all experiments from Experimenter API."""
    try:
        return retry_get(EXPERIMENTER_API_URL)
    except Exception as e:
        logger.error(f"Error fetching experiments from Experimenter: {e}")
        return []
