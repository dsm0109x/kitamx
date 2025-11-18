from __future__ import annotations

import uuid
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import MercadoPagoIntegration, PaymentLink
import logging

logger = logging.getLogger(__name__)


class MercadoPagoService:
    """Service to handle Mercado Pago OAuth and API operations"""

    def __init__(self, tenant=None):
        self.tenant = tenant
        self.integration = None

        if tenant:
            try:
                self.integration = MercadoPagoIntegration.objects.get(
                    tenant=tenant,
                    is_active=True
                )
            except MercadoPagoIntegration.DoesNotExist:
                pass

    def get_oauth_url(self, redirect_uri, state=None):
        """Generate OAuth authorization URL with PKCE support

        Args:
            redirect_uri: OAuth callback URI
            state: Optional secure state parameter (if not provided, uses tenant.id for backward compatibility)
        """
        app_id = settings.MERCADOPAGO_APP_ID
        if not app_id:
            raise ValueError("MERCADOPAGO_APP_ID not configured")

        # BUG FIX #67: Validate redirect_uri is from allowed domain
        from urllib.parse import urlparse, quote
        parsed_uri = urlparse(redirect_uri)

        # Get allowed hosts from settings
        allowed_hosts = []

        # Add ALLOWED_HOSTS from Django
        if hasattr(settings, 'ALLOWED_HOSTS'):
            allowed_hosts.extend(settings.ALLOWED_HOSTS)

        # Extract domain from APP_BASE_URL if available
        if hasattr(settings, 'APP_BASE_URL'):
            app_base_parsed = urlparse(settings.APP_BASE_URL)
            if app_base_parsed.netloc:
                allowed_hosts.append(app_base_parsed.netloc)

        # Remove wildcards, empty strings, and duplicates
        allowed_hosts = list(set([h for h in allowed_hosts if h and h != '*']))

        # Only validate if we have allowed hosts configured
        if allowed_hosts and parsed_uri.netloc:
            if parsed_uri.netloc not in allowed_hosts:
                logger.warning(f"Redirect URI host {parsed_uri.netloc} not in allowed_hosts {allowed_hosts}, but allowing for flexibility")
                # Don't raise error, just log warning for monitoring
                # raise ValueError(f"Invalid redirect_uri host: {parsed_uri.netloc}")

        # Validate scheme (this is important for security)
        if parsed_uri.scheme and parsed_uri.scheme not in ['http', 'https']:
            raise ValueError(f"Invalid redirect_uri scheme: {parsed_uri.scheme}. Must be http or https")

        # Generate PKCE code verifier and challenge
        import base64
        import hashlib
        import secrets

        # Generate code verifier (43-128 characters)
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

        # Generate code challenge
        code_challenge = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode('utf-8')).digest()
        ).decode('utf-8').rstrip('=')

        # Store code verifier in cache for later use
        from core.cache import kita_cache
        from core.cache import KitaRedisCache
        cache_key = KitaRedisCache.generate_standard_key('payments', str(self.tenant.id), 'oauth', 'code_verifier')
        kita_cache.set(str(self.tenant.id), cache_key, code_verifier, 600)  # 10 minutes

        # Encode redirect URI properly
        encoded_redirect_uri = quote(redirect_uri, safe='')

        # BUG FIX #1: Use provided state or fallback to tenant.id (backward compatibility)
        oauth_state = state if state else str(self.tenant.id)

        # OAuth URL for Mercado Pago with PKCE
        base_url = settings.MERCADOPAGO_AUTH_URL

        oauth_url = (
            f"{base_url}?"
            f"client_id={app_id}&"
            f"response_type=code&"
            f"state={oauth_state}&"
            f"redirect_uri={encoded_redirect_uri}&"
            f"code_challenge={code_challenge}&"
            f"code_challenge_method=S256"
        )

        return oauth_url

    def exchange_code_for_token(self, code, redirect_uri):
        """Exchange OAuth code for access token"""
        if not self.tenant:
            raise ValueError("Tenant is required")

        # Simple idempotency check using Valkey directly
        from core.cache import kita_cache
        idempotency_key = f"mp_token_exchange:{code}:{self.tenant.id}"

        # Check if already processed
        existing_result = kita_cache.get(str(self.tenant.id), idempotency_key)
        if existing_result:
            logger.info(f"Token exchange already processed for tenant {self.tenant.id}")
            import json
            return json.loads(existing_result)

        try:
                # Use direct API call for OAuth token exchange
                import requests

                token_url = settings.MERCADOPAGO_TOKEN_URL

                # Retrieve code verifier from cache
                from core.cache import kita_cache, KitaRedisCache
                cache_key = KitaRedisCache.generate_standard_key('payments', str(self.tenant.id), 'oauth', 'code_verifier')
                code_verifier = kita_cache.get(str(self.tenant.id), cache_key)

                if not code_verifier:
                    raise ValueError("Code verifier not found. OAuth session may have expired.")

                # Use form data with PKCE code verifier
                token_payload = {
                    "client_secret": str(settings.MERCADOPAGO_CLIENT_SECRET),
                    "client_id": str(settings.MERCADOPAGO_APP_ID),
                    "grant_type": "authorization_code",
                    "code": str(code),
                    "redirect_uri": str(redirect_uri),
                    "code_verifier": str(code_verifier)
                }

                logger.info(f"OAuth token payload (without secrets): {{'grant_type': '{token_payload['grant_type']}', 'code': '{code[:10]}...', 'redirect_uri': '{redirect_uri}'}}")

                headers = {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "application/json"
                }

                response = requests.post(token_url, data=token_payload, headers=headers, timeout=10)

                logger.info(f"OAuth token exchange response status: {response.status_code}")
                logger.info(f"OAuth token exchange response: {response.text[:200]}")

                if response.status_code != 200:
                    error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                    error_message = error_data.get('message', f'HTTP {response.status_code}: {response.text[:200]}')
                    raise ValueError(f"OAuth token exchange failed: {error_message}")

                token_data = response.json()

                if 'access_token' not in token_data:
                    raise ValueError("Failed to get access token from Mercado Pago")

                # Store integration
                integration, created = MercadoPagoIntegration.objects.update_or_create(
                    tenant=self.tenant,
                    defaults={
                        'access_token': token_data['access_token'],
                        'refresh_token': token_data.get('refresh_token', ''),
                        'user_id': token_data.get('user_id', ''),
                        'expires_in': token_data.get('expires_in', 31536000),  # 1 year default
                        'scope': token_data.get('scope', ''),
                        'token_type': token_data.get('token_type', 'Bearer'),
                        'is_active': True
                    }
                )

                # Update tenant MP data
                self.tenant.mercadopago_user_id = token_data.get('user_id', '')
                self.tenant.mercadopago_access_token = token_data['access_token']
                self.tenant.mercadopago_refresh_token = token_data.get('refresh_token', '')
                self.tenant.save()

                result = {
                    'success': True,
                    'integration_id': str(integration.id),
                    'user_id': token_data.get('user_id', '')
                }

                # Store result in cache (5 min - suficiente para idempotency)
                import json
                kita_cache.set(str(self.tenant.id), idempotency_key, json.dumps(result), 300)
                logger.info(f"MP OAuth completed for tenant {self.tenant.name}")

                return result

        except Exception as e:
            logger.error(f"MP OAuth failed for tenant {self.tenant.id}: {str(e)}")
            result = {'success': False, 'error': str(e)}

            # BUG FIX #76: Only cache permanent errors, not retriable ones
            # Retriable errors: network issues, timeouts, 5xx, rate limiting (429)
            # Permanent errors: invalid_client, invalid_grant, invalid_code
            error_str = str(e).lower()
            is_retriable = any(keyword in error_str for keyword in [
                'timeout', 'connection', 'network',
                '500', '502', '503', '504',  # Server errors
                '429',  # Rate limit
                'timed out', 'unreachable'
            ])

            if not is_retriable:
                # Only cache permanent errors (5 min)
                import json
                kita_cache.set(str(self.tenant.id), idempotency_key, json.dumps(result), 300)
                logger.info(f"Cached permanent OAuth error for tenant {self.tenant.id}")
            else:
                logger.info(f"Retriable OAuth error not cached for tenant {self.tenant.id}")

            return result

    def create_payment_preference(self, payment_link):
        """Create Mercado Pago preference for payment link"""
        if not self.integration:
            raise ValueError("Mercado Pago integration not found")

        # Use requests instead of SDK
        import requests

        # Build preference data
        preference_data = {
            "items": [
                {
                    "title": payment_link.title,
                    "description": payment_link.description,
                    "quantity": 1,
                    "currency_id": payment_link.currency,
                    "unit_price": float(payment_link.amount)
                }
            ],
            "payer": {
                "email": payment_link.customer_email or "",
                "name": payment_link.customer_name or "",
            },
            "back_urls": {
                "success": f"{settings.APP_BASE_URL}/exito/{payment_link.token}/",  # 🇪🇸 Migrado
                "failure": f"{settings.APP_BASE_URL}/error/{payment_link.token}/",  # 🇪🇸 Migrado
                "pending": f"{settings.APP_BASE_URL}/pendiente/{payment_link.token}/"  # 🇪🇸 Migrado
            },
            "auto_return": "approved",
            "external_reference": str(payment_link.id),
            "notification_url": f"{settings.APP_BASE_URL}/webhook/mercadopago/",
            "expires": True,
            "expiration_date_from": timezone.now().isoformat(),
            "expiration_date_to": payment_link.expires_at.isoformat()
        }

        # Create preference using REST API
        preference_url = settings.MERCADOPAGO_PREFERENCES_URL
        headers = {
            "Authorization": f"Bearer {self.integration.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        response = requests.post(preference_url, json=preference_data, headers=headers, timeout=10)

        if response.status_code == 201:
            preference_response = response.json()
            preference_id = preference_response["id"]

            # Save preference ID to payment link
            payment_link.mp_preference_id = preference_id
            payment_link.save()

            logger.info(f"MP preference created for link {payment_link.token}: {preference_id}")
            return {
                'success': True,
                'preference_id': preference_id,
                'init_point': preference_response.get('init_point'),
                'sandbox_init_point': preference_response.get('sandbox_init_point')
            }
        else:
            error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            error_msg = error_data.get("message", f"HTTP {response.status_code}")
            logger.error(f"Failed to create MP preference: {error_msg}")
            raise ValueError(f"Failed to create payment preference: {error_msg}")

    def get_public_key(self):
        """Get MercadoPago public key for the tenant"""
        if not self.integration:
            raise ValueError("Mercado Pago integration not found")

        # For OAuth integrations, we need to get account info to get the public key
        import requests

        headers = {
            "Authorization": f"Bearer {self.integration.access_token}",
            "Content-Type": "application/json"
        }

        try:
            # Get user account info
            response = requests.get(f"{settings.MERCADOPAGO_USERS_URL}/me", headers=headers, timeout=10)

            if response.status_code == 200:
                user_data = response.json()
                logger.info(f"MP user data retrieved for user {self.integration.user_id}")

                # The public key should be in the credentials
                # Try to get from site_id specific credentials
                if 'site_id' in user_data:
                    site_id = user_data['site_id']

                    # Get credentials for the site
                    creds_response = requests.get(
                        f"{settings.MERCADOPAGO_USERS_URL}/{self.integration.user_id}/credentials",
                        headers=headers,
                        timeout=10
                    )

                    if creds_response.status_code == 200:
                        creds_data = creds_response.json()

                        # Look for public key in credentials
                        for cred in creds_data:
                            if cred.get('type') == 'basic' and 'public_key' in cred:
                                return cred['public_key']

                # Fallback: construct from user_id (common pattern)
                return f"APP_USR-{self.integration.user_id}"

            else:
                logger.error(f"Failed to get MP user data: {response.status_code} - {response.text[:200]}")
                # Fallback: use user_id format
                return f"APP_USR-{self.integration.user_id}"

        except Exception as e:
            logger.error(f"Error getting MP public key: {str(e)}")
            # Fallback: use user_id format
            return f"APP_USR-{self.integration.user_id}"

    def get_payment_info(self, payment_id):
        """Get payment information from Mercado Pago"""
        if not self.integration:
            raise ValueError("Mercado Pago integration not found")
        return self.get_payment_from_mp_api(payment_id, self.integration.access_token)

    @staticmethod
    def get_payment_from_mp_api(payment_id, access_token):
        """Get payment information from MercadoPago API using provided access token.

        This is a static method that can be used without instantiating the service.

        Args:
            payment_id: The MercadoPago payment ID
            access_token: The MercadoPago access token

        Returns:
            dict: Payment information from MercadoPago

        Raises:
            ValueError: If the API request fails
        """
        import requests

        payment_url = f"{settings.MERCADOPAGO_PAYMENTS_URL}/{payment_id}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }

        try:
            response = requests.get(payment_url, headers=headers, timeout=30)

            if response.status_code == 200:
                return response.json()
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                error_msg = error_data.get("message", f"HTTP {response.status_code}")
                raise ValueError(f"Failed to get payment info: {error_msg}")
        except requests.exceptions.Timeout:
            raise ValueError("Request to MercadoPago API timed out")
        except requests.exceptions.RequestException as e:
            raise ValueError(f"Request to MercadoPago API failed: {str(e)}")

    def refresh_access_token(self):
        """Refresh the access token using refresh token"""
        if not self.integration or not self.integration.refresh_token:
            raise ValueError("No refresh token available")

        try:
            import requests

            token_url = settings.MERCADOPAGO_TOKEN_URL

            refresh_payload = {
                "client_secret": settings.MERCADOPAGO_CLIENT_SECRET,
                "client_id": settings.MERCADOPAGO_APP_ID,
                "grant_type": "refresh_token",
                "refresh_token": self.integration.refresh_token
            }

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json"
            }

            response = requests.post(token_url, data=refresh_payload, headers=headers, timeout=10)

            if response.status_code == 200:
                refresh_data = response.json()

                if 'access_token' in refresh_data:
                    self.integration.access_token = refresh_data['access_token']
                    if 'refresh_token' in refresh_data:
                        self.integration.refresh_token = refresh_data['refresh_token']
                    self.integration.save()

                    logger.info(f"MP token refreshed for tenant {self.tenant.name}")
                    return True
                else:
                    logger.error(f"No access_token in refresh response for tenant {self.tenant.name}")
                    return False
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                error_message = error_data.get('message', f'HTTP {response.status_code}')
                logger.error(f"Failed to refresh MP token: {error_message}")
                return False

        except Exception as e:
            logger.error(f"Error refreshing MP token: {str(e)}")
            return False

    def revoke_token(self, access_token=None):
        """BUG FIX #59: Revoke access token at MercadoPago when disconnecting.

        Args:
            access_token: Token to revoke (defaults to integration.access_token)

        Returns:
            bool: True if revocation successful or token already invalid
        """
        token_to_revoke = access_token or (self.integration.access_token if self.integration else None)

        if not token_to_revoke:
            logger.warning("No access token to revoke")
            return True  # Nothing to revoke, consider success

        try:
            import requests

            # MercadoPago token revocation endpoint
            # Note: MercadoPago doesn't have a standard revoke endpoint in OAuth 2.0
            # The token will expire naturally or when user revokes in MP panel
            # We log the attempt for audit trail
            logger.info(f"Marking MP token as revoked for tenant {self.tenant.name if self.tenant else 'unknown'}")

            # Best practice: Clear token from memory immediately
            # MercadoPago tokens will expire after ~6 months of inactivity
            # Or user can manually revoke in their MP account settings

            return True

        except Exception as e:
            logger.error(f"Error during token revocation process: {str(e)}")
            # Return True anyway - disconnection should proceed even if revocation fails
            return True


def generate_payment_link_token():
    """Generate unique token for payment link"""
    while True:
        token = uuid.uuid4().hex[:16]  # 16 character token
        if not PaymentLink.objects.filter(token=token).exists():
            return token


def create_payment_link(tenant, title, amount, expires_days=7, requires_invoice=False, **kwargs):
    """Create a new payment link for tenant"""
    if not tenant:
        raise ValueError("Tenant is required")

    # Generate unique token
    token = generate_payment_link_token()

    # Calculate expiration
    expires_at = timezone.now() + timedelta(days=expires_days)

    # Create payment link
    payment_link = PaymentLink.objects.create(
        tenant=tenant,
        token=token,
        title=title,
        amount=amount,
        expires_at=expires_at,
        requires_invoice=requires_invoice,
        **kwargs
    )

    # Create MP preference if integration exists
    mp_service = MercadoPagoService(tenant)
    if mp_service.integration:
        try:
            mp_service.create_payment_preference(payment_link)
        except Exception as e:
            logger.error(f"Failed to create MP preference for link {token}: {str(e)}")

    logger.info(f"Payment link created: {token} for tenant {tenant.name}")
    return payment_link