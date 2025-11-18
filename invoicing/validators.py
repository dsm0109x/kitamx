"""
Validadores y utilidades de cifrado para el módulo de facturación.

Este módulo centraliza las validaciones comunes de certificados CSD,
llaves privadas y formateo de errores para evitar duplicación de código.
"""
from __future__ import annotations
import logging
from typing import Dict, Any, Tuple

from cryptography import x509
from cryptography.hazmat.primitives import serialization

logger = logging.getLogger(__name__)


class CSDValidationError(Exception):
    """Excepción personalizada para errores de validación de CSD."""
    pass


class PrivateKeyHandler:
    """Manejador centralizado para validación de llaves privadas."""

    @staticmethod
    def load_private_key(key_content: bytes | str, password: str | bytes) -> Any:
        """
        Carga una llave privada desde contenido PEM o DER.

        Args:
            key_content: Contenido de la llave (PEM string o DER bytes)
            password: Contraseña de la llave

        Returns:
            Objeto de llave privada cargada

        Raises:
            CSDValidationError: Si no se puede cargar la llave
        """
        password_bytes = password.encode() if isinstance(password, str) else password

        # Debug info
        logger.info(f"Attempting to load private key, password length: {len(password) if password else 0}")

        try:
            if isinstance(key_content, str):
                # PEM format
                return PrivateKeyHandler._load_pem_key(key_content, password_bytes)
            else:
                # DER format (binary)
                return PrivateKeyHandler._load_der_key(key_content, password_bytes)

        except Exception as e:
            error_msg = PrivateKeyHandler._format_key_error(e)
            logger.error(f"Failed to load private key: {error_msg}")
            raise CSDValidationError(error_msg)

    @staticmethod
    def _load_pem_key(key_content: str, password_bytes: bytes) -> Any:
        """Cargar llave PEM con manejo de errores."""
        try:
            return serialization.load_pem_private_key(
                key_content.encode(),
                password=password_bytes
            )
        except Exception as e:
            # Try without password for unprotected keys
            try:
                return serialization.load_pem_private_key(
                    key_content.encode(),
                    password=None
                )
            except Exception:
                raise e  # Re-raise original error

    @staticmethod
    def _load_der_key(key_content: bytes, password_bytes: bytes) -> Any:
        """Cargar llave DER con manejo de errores."""
        try:
            return serialization.load_der_private_key(
                key_content,
                password=password_bytes
            )
        except Exception as e:
            # Try without password for unprotected keys
            try:
                return serialization.load_der_private_key(
                    key_content,
                    password=None
                )
            except Exception:
                raise e  # Re-raise original error

    @staticmethod
    def _format_key_error(exception: Exception) -> str:
        """
        Formatea errores de carga de llaves para mensajes user-friendly.

        Args:
            exception: Excepción capturada

        Returns:
            Mensaje de error formateado para el usuario
        """
        error_str = str(exception).lower()

        if "bad decrypt" in error_str or "incorrect" in error_str:
            return "La contraseña de la llave privada es incorrecta"
        elif "unsupported" in error_str:
            return "Formato de llave privada no soportado"
        elif "could not deserialize" in error_str:
            return "El archivo de llave privada está corrupto o es inválido"
        else:
            return "Error al cargar la llave privada. Verifica el archivo y la contraseña"


class CertificateHandler:
    """Manejador centralizado para validación de certificados."""

    @staticmethod
    def load_certificate(cert_content: bytes | str) -> x509.Certificate:
        """
        Carga un certificado desde contenido PEM o DER.

        Args:
            cert_content: Contenido del certificado

        Returns:
            Objeto certificado cargado

        Raises:
            CSDValidationError: Si no se puede cargar el certificado
        """
        try:
            if isinstance(cert_content, str):
                # String content - try PEM format
                return x509.load_pem_x509_certificate(cert_content.encode())
            else:
                # Binary content - try DER format
                return x509.load_der_x509_certificate(cert_content)

        except Exception as e:
            logger.error(f"Failed to load certificate: {str(e)}")
            raise CSDValidationError(
                "El archivo de certificado no es válido. Verifica que sea un archivo .cer del SAT"
            )

    @staticmethod
    def extract_certificate_info(certificate: x509.Certificate) -> Dict[str, Any]:
        """
        Extrae información relevante del certificado.

        Args:
            certificate: Objeto certificado

        Returns:
            Diccionario con información del certificado
        """
        subject = certificate.subject
        issuer = certificate.issuer

        # Get subject name (CN)
        subject_name = ''
        for attribute in subject:
            if attribute.oid._name == 'commonName':
                subject_name = attribute.value
                break

        # Get issuer name (CN)
        issuer_name = ''
        for attribute in issuer:
            if attribute.oid._name == 'commonName':
                issuer_name = attribute.value
                break

        # Extract RFC from certificate
        # SAT stores RFC in serialNumber (OID 2.5.4.5) or x500UniqueIdentifier (OID 2.5.4.45)
        rfc_from_cert = None
        for attribute in subject:
            if attribute.oid.dotted_string == "2.5.4.5":  # serialNumber
                rfc_from_cert = attribute.value
                logger.info(f"RFC found in serialNumber: {rfc_from_cert}")
                break
            elif attribute.oid.dotted_string == "2.5.4.45":  # x500UniqueIdentifier
                rfc_from_cert = attribute.value
                logger.info(f"RFC found in x500UniqueIdentifier: {rfc_from_cert}")
                break

        return {
            'serial_number': str(certificate.serial_number),
            'subject_name': subject_name,
            'issuer_name': issuer_name,
            'valid_from': certificate.not_valid_before,
            'valid_to': certificate.not_valid_after,
            'subject': subject,
            'issuer': issuer,
            'rfc': rfc_from_cert  # RFC extraído del certificado
        }


class SWResponseHandler:
    """Manejador centralizado para respuestas del servicio SW."""

    @staticmethod
    def format_success_response(result: Dict[str, Any],
                              include_pdf: bool = False) -> Dict[str, Any]:
        """
        Formatea respuesta exitosa del servicio SW.

        Args:
            result: Respuesta cruda del servicio SW
            include_pdf: Si incluir datos de PDF en la respuesta

        Returns:
            Respuesta formateada
        """
        import base64
        from django.utils import timezone

        response_data = {
            'success': True,
            'uuid': result['data'].get('uuid'),
            'fecha_timbrado': timezone.now(),
            'sw_response': result.get('sw_response', {})
        }

        # Handle XML content
        stamped_xml_b64 = result['data'].get('cfdi', '')
        if stamped_xml_b64:
            try:
                response_data['xml'] = base64.b64decode(stamped_xml_b64).decode()
            except Exception:
                response_data['xml'] = stamped_xml_b64  # Return as-is if decode fails

        # Handle PDF content if requested
        if include_pdf and 'pdf' in result['data']:
            response_data['pdf'] = result['data']['pdf']

        return response_data

    @staticmethod
    def format_error_response(result: Dict[str, Any],
                            operation: str = 'timbrado') -> Dict[str, Any]:
        """
        Formatea respuesta de error del servicio SW.

        Args:
            result: Respuesta cruda del servicio SW
            operation: Tipo de operación (para logging)

        Returns:
            Respuesta de error formateada
        """
        error_message = result.get('messageDetail',
                                 result.get('message', f'Error de {operation}'))

        return {
            'success': False,
            'error': error_message,
            'sw_response': result.get('sw_response', {})
        }

    @staticmethod
    def format_exception_response(exception: Exception,
                                operation: str = 'operation') -> Dict[str, Any]:
        """
        Formatea respuesta para excepciones capturadas.

        Args:
            exception: Excepción capturada
            operation: Tipo de operación (para logging)

        Returns:
            Respuesta de error formateada
        """
        logger.error(f"SW: {operation} error: {str(exception)}")

        return {
            'success': False,
            'error': str(exception),
            'sw_response': {}
        }


def validate_csd_files(cert_content: bytes | str,
                      key_content: bytes | str,
                      password: str) -> Tuple[x509.Certificate, Any]:
    """
    Valida archivos de certificado y llave CSD de forma integrada.

    Args:
        cert_content: Contenido del certificado
        key_content: Contenido de la llave privada
        password: Contraseña de la llave

    Returns:
        Tupla con (certificado, llave_privada) cargados

    Raises:
        CSDValidationError: Si la validación falla
    """
    # Cargar certificado
    certificate = CertificateHandler.load_certificate(cert_content)

    # Cargar llave privada
    private_key = PrivateKeyHandler.load_private_key(key_content, password)

    # Validar que la llave corresponde al certificado
    # (Opcional: agregar validación de correspondencia aquí)

    return certificate, private_key


__all__ = [
    'CSDValidationError',
    'PrivateKeyHandler',
    'CertificateHandler',
    'SWResponseHandler',
    'validate_csd_files',
]