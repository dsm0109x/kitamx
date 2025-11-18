"""
PAC Service - FiscalAPI as sole provider
Simplified version - no legacy SmartWeb support
"""
import logging

logger = logging.getLogger(__name__)


def get_pac_service():
    """
    Get FiscalAPI service instance.

    Returns:
        FiscalAPIService: Singleton instance
    """
    from .fiscalapi_service import fiscalapi_service
    return fiscalapi_service


# Global instance - FiscalAPI singleton
pac_service = get_pac_service()
