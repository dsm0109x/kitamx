"""
Centralized security utilities for the Kita application.

This module consolidates all security-related functions including:
- IP detection and validation
- Rate limiting helpers
- Security headers
- Anti-fraud detection
"""
from __future__ import annotations
import ipaddress
import logging
from typing import Optional, List
from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest

logger = logging.getLogger(__name__)


class SecureIPDetector:
    """
    Securely detect client IP address with anti-spoofing measures.

    This is the centralized implementation - all other modules should use this.
    """

    # Trusted proxy headers in order of preference
    TRUSTED_HEADERS = [
        'HTTP_X_REAL_IP',
        'HTTP_X_FORWARDED_FOR',
        'HTTP_CF_CONNECTING_IP',  # Cloudflare
        'HTTP_X_CLIENT_IP',
        'REMOTE_ADDR',
    ]

    # Private IP ranges (RFC 1918)
    PRIVATE_IP_RANGES = [
        ipaddress.ip_network('10.0.0.0/8'),
        ipaddress.ip_network('172.16.0.0/12'),
        ipaddress.ip_network('192.168.0.0/16'),
        ipaddress.ip_network('127.0.0.0/8'),
        ipaddress.ip_network('fc00::/7'),  # IPv6 private
        ipaddress.ip_network('::1/128'),    # IPv6 loopback
    ]

    @classmethod
    def get_client_ip(cls, request: HttpRequest) -> str:
        """
        Get client IP address with security checks.

        Args:
            request: Django HTTP request object

        Returns:
            Client IP address or empty string if cannot be determined
        """
        client_ip = ''

        # Try headers in order of trust
        for header in cls.TRUSTED_HEADERS:
            ip_string = request.META.get(header, '').strip()

            if not ip_string:
                continue

            # Handle comma-separated IPs (X-Forwarded-For)
            if ',' in ip_string:
                # Take the first public IP
                ips = [ip.strip() for ip in ip_string.split(',')]
                for ip in ips:
                    if cls._is_valid_public_ip(ip):
                        client_ip = ip
                        break
            else:
                if cls._is_valid_public_ip(ip_string):
                    client_ip = ip_string
                    break

        # Fallback to REMOTE_ADDR if no valid IP found
        if not client_ip:
            client_ip = request.META.get('REMOTE_ADDR', '')

        # Sanitize the IP
        client_ip = cls._sanitize_ip(client_ip)

        # Log suspicious patterns
        if cls._is_suspicious_ip_pattern(request):
            logger.warning(
                f"Suspicious IP headers detected - "
                f"X-Forwarded-For: {request.META.get('HTTP_X_FORWARDED_FOR')} "
                f"X-Real-IP: {request.META.get('HTTP_X_REAL_IP')} "
                f"Remote: {request.META.get('REMOTE_ADDR')}"
            )

        return client_ip

    @classmethod
    def _is_valid_public_ip(cls, ip_string: str) -> bool:
        """
        Check if IP is valid and public.

        Args:
            ip_string: IP address string

        Returns:
            True if IP is valid and public
        """
        if not ip_string:
            return False

        try:
            ip_obj = ipaddress.ip_address(ip_string)

            # Check if it's a private IP
            for private_range in cls.PRIVATE_IP_RANGES:
                if ip_obj in private_range:
                    return False

            # Check for special addresses
            if ip_obj.is_multicast or ip_obj.is_reserved or ip_obj.is_loopback:
                return False

            return True

        except ValueError:
            return False

    @classmethod
    def _sanitize_ip(cls, ip_string: str) -> str:
        """
        Sanitize IP address string.

        Args:
            ip_string: Raw IP string

        Returns:
            Sanitized IP string
        """
        if not ip_string:
            return ''

        # Remove any port information
        if ':' in ip_string and not cls._is_ipv6(ip_string):
            ip_string = ip_string.split(':')[0]

        # Validate final IP
        try:
            ipaddress.ip_address(ip_string)
            return ip_string
        except ValueError:
            return ''

    @classmethod
    def _is_ipv6(cls, ip_string: str) -> bool:
        """Check if string is IPv6 address."""
        try:
            ipaddress.IPv6Address(ip_string)
            return True
        except (ValueError, ipaddress.AddressValueError):
            return False

    @classmethod
    def _is_suspicious_ip_pattern(cls, request: HttpRequest) -> bool:
        """
        Detect suspicious IP header patterns.

        Args:
            request: Django request

        Returns:
            True if suspicious pattern detected
        """
        # Check for IP spoofing attempts
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        real_ip = request.META.get('HTTP_X_REAL_IP', '')
        remote = request.META.get('REMOTE_ADDR', '')

        # Multiple different IPs is suspicious
        ips = set()
        for ip in [forwarded, real_ip, remote]:
            if ip:
                ips.add(ip.split(',')[0].strip())

        return len(ips) > 2


class RateLimitHelper:
    """Helper class for rate limiting functionality."""

    @staticmethod
    def get_rate_limit_key(request: HttpRequest, action: str) -> str:
        """
        Generate rate limit cache key.

        Args:
            request: Django request
            action: Action being rate limited

        Returns:
            Cache key for rate limiting
        """
        ip = SecureIPDetector.get_client_ip(request)
        user_id = request.user.id if request.user.is_authenticated else 'anon'
        return f"rate_limit:{action}:{user_id}:{ip}"

    @staticmethod
    def check_rate_limit(
        request: HttpRequest,
        action: str,
        max_attempts: int = 10,
        window: int = 3600
    ) -> tuple[bool, int]:
        """
        Check if rate limit exceeded.

        Args:
            request: Django request
            action: Action being rate limited
            max_attempts: Maximum attempts allowed
            window: Time window in seconds

        Returns:
            Tuple of (is_allowed, remaining_attempts)
        """
        key = RateLimitHelper.get_rate_limit_key(request, action)

        # Get current count
        current = cache.get(key, 0)

        if current >= max_attempts:
            return False, 0

        # Increment counter
        cache.set(key, current + 1, window)

        return True, max_attempts - current - 1


class SecurityHeaders:
    """Manage security-related HTTP headers."""

    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
    }

    @classmethod
    def add_security_headers(cls, response):
        """
        Add security headers to response.

        Args:
            response: Django HTTP response

        Returns:
            Modified response with security headers
        """
        for header, value in cls.SECURITY_HEADERS.items():
            response[header] = value

        # Add CSP if configured
        if hasattr(settings, 'CSP_DEFAULT_SRC'):
            csp_parts = []
            csp_directives = [
                'default-src', 'script-src', 'style-src', 'img-src',
                'connect-src', 'font-src', 'object-src', 'media-src',
                'frame-src', 'sandbox', 'report-uri', 'child-src',
                'form-action', 'frame-ancestors', 'plugin-types'
            ]

            for directive in csp_directives:
                setting_name = f'CSP_{directive.upper().replace("-", "_")}'
                if hasattr(settings, setting_name):
                    value = getattr(settings, setting_name)
                    if isinstance(value, (list, tuple)):
                        value = ' '.join(value)
                    csp_parts.append(f"{directive} {value}")

            if csp_parts:
                response['Content-Security-Policy'] = '; '.join(csp_parts)

        return response


class FraudDetector:
    """Basic fraud detection utilities."""

    @classmethod
    def check_velocity(
        cls,
        identifier: str,
        action: str,
        threshold: int = 5,
        window: int = 60
    ) -> bool:
        """
        Check velocity of actions (e.g., rapid payment attempts).

        Args:
            identifier: Unique identifier (e.g., user_id, ip)
            action: Action to track
            threshold: Maximum actions in window
            window: Time window in seconds

        Returns:
            True if velocity check passed (not suspicious)
        """
        key = f"velocity:{action}:{identifier}"
        count = cache.get(key, 0)

        if count >= threshold:
            logger.warning(f"Velocity threshold exceeded for {identifier} on {action}")
            return False

        cache.set(key, count + 1, window)
        return True

    @classmethod
    def check_suspicious_pattern(
        cls,
        request: HttpRequest,
        amount: Optional[float] = None
    ) -> List[str]:
        """
        Check for suspicious patterns in request.

        Args:
            request: Django request
            amount: Optional transaction amount

        Returns:
            List of suspicious indicators found
        """
        indicators = []

        # Check for proxy/VPN
        ip = SecureIPDetector.get_client_ip(request)
        if cls._is_known_proxy(ip):
            indicators.append('known_proxy')

        # Check for suspicious user agent
        user_agent = request.META.get('HTTP_USER_AGENT', '')
        if cls._is_suspicious_user_agent(user_agent):
            indicators.append('suspicious_user_agent')

        # Check for missing expected headers
        if not request.META.get('HTTP_REFERER'):
            indicators.append('missing_referer')

        # Check for high-risk amount patterns
        if amount:
            if cls._is_suspicious_amount(amount):
                indicators.append('suspicious_amount')

        return indicators

    @staticmethod
    def _is_known_proxy(ip: str) -> bool:
        """Check if IP is from known proxy/VPN service."""
        # This would typically check against a database of known proxies
        # For now, return False
        return False

    @staticmethod
    def _is_suspicious_user_agent(user_agent: str) -> bool:
        """Check if user agent is suspicious."""
        suspicious_patterns = [
            'bot', 'crawler', 'spider', 'scraper',
            'curl', 'wget', 'python-requests'
        ]

        user_agent_lower = user_agent.lower()
        return any(pattern in user_agent_lower for pattern in suspicious_patterns)

    @staticmethod
    def _is_suspicious_amount(amount: float) -> bool:
        """Check if amount follows suspicious pattern."""
        # Check for testing amounts
        test_amounts = [1.00, 0.01, 0.99, 123.45, 1234.56]
        if amount in test_amounts:
            return True

        # Check for unusually high amounts
        if amount > 100000:  # Adjust based on business logic
            return True

        return False


# Convenience functions for backward compatibility
def get_client_ip(request: HttpRequest) -> str:
    """
    Get client IP address.

    This is a convenience function that delegates to SecureIPDetector.
    """
    return SecureIPDetector.get_client_ip(request)


def add_security_headers(response):
    """
    Add security headers to response.

    This is a convenience function that delegates to SecurityHeaders.
    """
    return SecurityHeaders.add_security_headers(response)


def check_rate_limit(request: HttpRequest, action: str, max_attempts: int = 10, window: int = 3600):
    """
    Check rate limit.

    This is a convenience function that delegates to RateLimitHelper.
    """
    return RateLimitHelper.check_rate_limit(request, action, max_attempts, window)