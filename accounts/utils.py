"""
Utility functions for accounts app with security enhancements.

This module provides secure utility functions for common operations
like IP detection, audit logging, and data sanitization.
"""
from __future__ import annotations
import hashlib
import logging
from typing import Optional, Dict, Any, Union
from django.core.cache import cache
from django.http import HttpRequest
from django.utils import timezone

# Import centralized security utilities
from core.security import SecureIPDetector, RateLimitHelper

logger = logging.getLogger(__name__)


# SecureIPDetector is now imported from core.security
# No need to duplicate the implementation here


class AuditLogger:
    """
    Centralized audit logging with security context.
    """

    @staticmethod
    def log_action(
        request: HttpRequest,
        action: str,
        entity_type: str,
        entity_id: Optional[Union[str, int]] = None,
        entity_name: Optional[str] = None,
        old_values: Optional[Dict[str, Any]] = None,
        new_values: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None,
        tenant: Optional[Any] = None
    ) -> None:
        """
        Create audit log entry with full context.

        Args:
            request: HTTP request for context
            action: Action performed (create, update, delete, etc.)
            entity_type: Type of entity affected
            entity_id: ID of entity
            entity_name: Human-readable name of entity
            old_values: Previous values (for updates)
            new_values: New values (for updates)
            notes: Additional context
            tenant: Tenant instance if applicable
        """
        from core.models import AuditLog

        try:
            user = request.user if request.user.is_authenticated else None

            # Get secure IP
            ip_address = SecureIPDetector.get_client_ip(request)

            # Get user agent
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]  # Limit length

            # Sanitize values to prevent log injection
            action = action[:100] if action else ''
            entity_type = entity_type[:50] if entity_type else ''
            entity_name = entity_name[:255] if entity_name else ''
            notes = notes[:1000] if notes else ''

            # Remove sensitive data from values
            if old_values:
                old_values = AuditLogger._sanitize_values(old_values)
            if new_values:
                new_values = AuditLogger._sanitize_values(new_values)

            AuditLog.objects.create(
                tenant=tenant,
                user_email=user.email if user else 'anonymous',
                user_name=user.get_full_name() if user else 'Anonymous',
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id else None,
                entity_name=entity_name,
                ip_address=ip_address,
                user_agent=user_agent,
                old_values=old_values or {},
                new_values=new_values or {},
                notes=notes
            )
        except Exception as e:
            # Log but don't break the flow
            logger.error(f"Failed to create audit log: {str(e)}")

    @staticmethod
    def _sanitize_values(values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove sensitive data from logged values.

        Args:
            values: Dictionary of values

        Returns:
            Sanitized dictionary
        """
        sensitive_keys = {
            'password', 'token', 'secret', 'key', 'access_token',
            'refresh_token', 'api_key', 'private_key', 'csd_password'
        }

        sanitized = {}
        for key, value in values.items():
            # Check if key contains sensitive word
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = '***REDACTED***'
            else:
                # Truncate long values
                if isinstance(value, str) and len(value) > 500:
                    sanitized[key] = value[:500] + '...'
                else:
                    sanitized[key] = value

        return sanitized


class RateLimitHelper:
    """
    Helper for managing rate limits with caching.
    """

    @staticmethod
    def get_rate_limit_key(
        identifier: str,
        action: str,
        window: str = 'default'
    ) -> str:
        """
        Generate cache key for rate limiting.

        Args:
            identifier: User ID, IP, or email
            action: Action being rate limited
            window: Time window identifier

        Returns:
            Cache key string
        """
        # Hash the identifier for privacy
        identifier_hash = hashlib.sha256(str(identifier).encode()).hexdigest()[:16]
        return f"ratelimit:{action}:{window}:{identifier_hash}"

    @staticmethod
    def check_rate_limit(
        identifier: str,
        action: str,
        max_attempts: int,
        window_seconds: int
    ) -> tuple[bool, int]:
        """
        Check if rate limit has been exceeded.

        Args:
            identifier: User ID, IP, or email
            action: Action being rate limited
            max_attempts: Maximum attempts allowed
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_allowed, remaining_attempts)
        """
        key = RateLimitHelper.get_rate_limit_key(identifier, action)

        # Get current count
        current_count = cache.get(key, 0)

        if current_count >= max_attempts:
            remaining = 0
            is_allowed = False
        else:
            # Increment counter
            try:
                # Use incr for atomic operation
                if current_count == 0:
                    cache.set(key, 1, window_seconds)
                    current_count = 1
                else:
                    current_count = cache.incr(key)
            except Exception:
                # Fallback to non-atomic increment
                current_count += 1
                cache.set(key, current_count, window_seconds)

            remaining = max_attempts - current_count
            is_allowed = True

        return is_allowed, remaining

    @staticmethod
    def reset_rate_limit(identifier: str, action: str) -> None:
        """
        Reset rate limit for an identifier.

        Args:
            identifier: User ID, IP, or email
            action: Action being rate limited
        """
        key = RateLimitHelper.get_rate_limit_key(identifier, action)
        cache.delete(key)


class SessionSecurityHelper:
    """
    Helper for session security operations.
    """

    @staticmethod
    def validate_session_security(request: HttpRequest) -> bool:
        """
        Validate session hasn't been hijacked.

        Args:
            request: Django HTTP request

        Returns:
            True if session appears valid
        """
        if not request.user.is_authenticated:
            return True

        # Get stored session fingerprint
        stored_fingerprint = request.session.get('security_fingerprint')
        if not stored_fingerprint:
            # Create fingerprint for new session
            SessionSecurityHelper.create_session_fingerprint(request)
            return True

        # Generate current fingerprint
        current_fingerprint = SessionSecurityHelper._generate_fingerprint(request)

        # Compare fingerprints
        if stored_fingerprint != current_fingerprint:
            logger.warning(
                f"Session fingerprint mismatch for user {request.user.email} "
                f"from IP {SecureIPDetector.get_client_ip(request)}"
            )
            return False

        return True

    @staticmethod
    def create_session_fingerprint(request: HttpRequest) -> str:
        """
        Create security fingerprint for session.

        Args:
            request: Django HTTP request

        Returns:
            Fingerprint hash
        """
        fingerprint = SessionSecurityHelper._generate_fingerprint(request)
        request.session['security_fingerprint'] = fingerprint
        request.session['fingerprint_created_at'] = timezone.now().isoformat()
        return fingerprint

    @staticmethod
    def _generate_fingerprint(request: HttpRequest) -> str:
        """
        Generate fingerprint from request characteristics.

        Args:
            request: Django HTTP request

        Returns:
            SHA256 hash of fingerprint
        """
        # Use stable characteristics that don't change often
        components = [
            request.META.get('HTTP_USER_AGENT', ''),
            request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
            request.META.get('HTTP_ACCEPT_ENCODING', ''),
            # Don't use IP as it can change legitimately
        ]

        fingerprint_str = '|'.join(components)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()


class DataSanitizer:
    """
    Sanitize user input to prevent injection attacks.
    """

    @staticmethod
    def sanitize_html(text: str) -> str:
        """
        Remove HTML tags and dangerous content.

        Args:
            text: Raw text input

        Returns:
            Sanitized text
        """
        import html
        import re

        if not text:
            return ''

        # HTML escape
        text = html.escape(text)

        # Remove any remaining tags
        text = re.sub(r'<[^>]+>', '', text)

        # Remove javascript: and data: URLs
        text = re.sub(r'(javascript|data):', '', text, flags=re.IGNORECASE)

        # Limit length
        return text[:10000]

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename to prevent path traversal.

        Args:
            filename: Raw filename

        Returns:
            Safe filename
        """
        import os
        import re

        if not filename:
            return 'unnamed'

        # Get just the filename without path
        filename = os.path.basename(filename)

        # Remove dangerous characters
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)

        # Prevent double extensions
        parts = filename.split('.')
        if len(parts) > 2:
            filename = f"{parts[0]}.{parts[-1]}"

        # Limit length
        if len(filename) > 255:
            name, ext = os.path.splitext(filename)
            filename = name[:240] + ext

        return filename or 'unnamed'


# Export main functions for convenience
get_client_ip = SecureIPDetector.get_client_ip
log_audit = AuditLogger.log_action
check_rate_limit = RateLimitHelper.check_rate_limit
sanitize_html = DataSanitizer.sanitize_html
sanitize_filename = DataSanitizer.sanitize_filename


__all__ = [
    'SecureIPDetector',
    'AuditLogger',
    'RateLimitHelper',
    'SessionSecurityHelper',
    'DataSanitizer',
    'get_client_ip',
    'log_audit',
    'check_rate_limit',
    'sanitize_html',
    'sanitize_filename',
]