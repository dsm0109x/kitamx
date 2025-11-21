"""
PAC Service - facturapi.io as provider
Migrated from FiscalAPI to facturapi.io
"""
import logging

logger = logging.getLogger(__name__)


def get_pac_service():
    """
    Get facturapi.io service instance.

    Returns:
        FacturapiService: Singleton instance
    """
    from .facturapi_service import facturapi_service
    return facturapi_service


# Global instance - facturapi.io singleton
pac_service = get_pac_service()
