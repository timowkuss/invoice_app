"""
1C Integration Module (Placeholder)

This module provides the interface for 1C ERP integration.
Currently it's a stub that will be implemented when the 1C database schema is provided.

Expected operations:
- Sync product catalog from 1C
- Send confirmed invoices to 1C
- Check connection status
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from core.models.product import Product

logger = logging.getLogger(__name__)


@dataclass
class OneCConfig:
    base_url: str = ""
    username: str = ""
    password: str = ""
    odata_path: str = ""


class OneCClient:
    """Client for 1C ERP integration via OData or COM."""

    def __init__(self, config: OneCConfig):
        self._config = config

    async def test_connection(self) -> bool:
        """Test connection to 1C server."""
        logger.info("Testing 1C connection to %s", self._config.base_url)
        # TODO: Implement actual connection test
        return False

    async def sync_products(self, store_id: int) -> list[Product]:
        """Sync product catalog from 1C."""
        logger.info("Syncing products from 1C for store %d", store_id)
        # TODO: Implement OData query to fetch products
        # Example OData endpoint:
        # GET {base_url}/odata/StandardCatalog/БлокНоменклатуры?$format=json
        return []

    async def send_invoice(self, document_id: int) -> dict:
        """Send confirmed invoice to 1C."""
        logger.info("Sending document %d to 1C", document_id)
        # TODO: Implement document creation in 1C
        # Example: POST to create "ПоступлениеТоваров"
        return {"status": "not_implemented"}

    async def get_product_by_article(self, article: str) -> Product | None:
        """Get single product by article from 1C."""
        # TODO: Implement OData query
        return None

    async def get_product_by_barcode(self, barcode: str) -> Product | None:
        """Get single product by barcode from 1C."""
        # TODO: Implement OData query
        return None
