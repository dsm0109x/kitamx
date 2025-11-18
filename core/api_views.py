"""
API endpoints for address autocomplete system.

Provides AJAX endpoints for:
- Postal code lookup (Copomex)
- Street suggestions (Nominatim)
- Reverse geocoding (GPS coordinates)
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit
import json
import logging

from .services.address_autocomplete import AddressAutocompleteService

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
@ratelimit(key='ip', rate='60/m', method='POST')
def api_lookup_postal_code(request):
    """
    Lookup postal code data from Copomex (official SAT source).

    Rate limit: 60 requests per minute per IP

    Request body:
        {"codigo_postal": "06600"}

    Response:
        {
            "success": true,
            "colonias": ["Juárez", "Doctores", ...],
            "municipio": "Cuauhtémoc",
            "estado": "Ciudad de México"
        }
    """
    try:
        data = json.loads(request.body)
        codigo_postal = data.get('codigo_postal', '').strip()

        result = AddressAutocompleteService.lookup_by_postal_code(codigo_postal)

        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Postal code lookup error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error al consultar código postal'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@ratelimit(key='ip', rate='30/m', method='POST')
def api_suggest_streets(request):
    """
    Suggest street names using OpenStreetMap Nominatim.

    Rate limit: 30 requests per minute (OSM fair use)

    Request body:
        {
            "query": "Paseo de la",
            "codigo_postal": "06600",
            "colonia": "Juárez"
        }

    Response:
        {
            "suggestions": [
                {
                    "calle": "Paseo de la Reforma",
                    "numero": "250",
                    "display_name": "..."
                },
                ...
            ]
        }
    """
    try:
        data = json.loads(request.body)
        query = data.get('query', '').strip()
        codigo_postal = data.get('codigo_postal')
        colonia = data.get('colonia')

        suggestions = AddressAutocompleteService.suggest_streets(
            query,
            codigo_postal,
            colonia
        )

        return JsonResponse({
            'success': True,
            'suggestions': suggestions
        })

    except Exception as e:
        logger.error(f"Street suggestions error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error al buscar calles'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@ratelimit(key='ip', rate='10/m', method='POST')
def api_reverse_geocode(request):
    """
    Reverse geocode GPS coordinates to address.

    Rate limit: 10 requests per minute (to prevent abuse)

    Request body:
        {
            "lat": 19.4326,
            "lon": -99.1332
        }

    Response:
        {
            "success": true,
            "address": {
                "calle": "Paseo de la Reforma",
                "numero": "250",
                "colonia": "Juárez",
                "municipio": "Cuauhtémoc",
                "estado": "Ciudad de México",
                "codigo_postal": "06600"
            }
        }
    """
    try:
        data = json.loads(request.body)
        lat = float(data.get('lat'))
        lon = float(data.get('lon'))

        address_data = AddressAutocompleteService.reverse_from_coords(lat, lon)

        if address_data:
            # Validar y normalizar con Copomex
            if address_data.get('codigo_postal'):
                validation = AddressAutocompleteService.validate_and_normalize(address_data)

                if validation.get('valid'):
                    return JsonResponse({
                        'success': True,
                        'address': validation['normalized']
                    })

            # Si no se pudo validar, devolver datos de OSM as-is
            return JsonResponse({
                'success': True,
                'address': address_data,
                'warning': 'Datos de ubicación - verifica que sean correctos'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'No se pudo obtener dirección de esas coordenadas'
            }, status=404)

    except ValueError:
        return JsonResponse({
            'success': False,
            'error': 'Coordenadas inválidas'
        }, status=400)

    except Exception as e:
        logger.error(f"Reverse geocode error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error al obtener dirección'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@ratelimit(key='ip', rate='60/m', method='POST')
def api_lookup_recipient(request):
    """
    Lookup recipient by RFC and Email in FiscalAPI.
    
    If RFC exists AND email matches, return recipient data for autofill.
    If RFC exists but email doesn't match, return empty (privacy/security).
    If RFC doesn't exist, return empty (will be created on invoice).
    
    Request body:
        {"rfc": "XAXX010101000", "email": "customer@example.com"}
    
    Response:
        {
            "found": true,
            "data": {
                "business_name": "...",
                "postal_code": "...",
                "fiscal_regime": "612",
                "cfdi_use": "G03"
            }
        }
    """
    try:
        data = json.loads(request.body)
        rfc = data.get('rfc', '').strip().upper()
        email = data.get('email', '').strip().lower()
        
        if not rfc or not email:
            return JsonResponse({'found': False})
        
        # Use FiscalAPI to lookup recipient
        from invoicing.fiscalapi_service import fiscalapi_service
        
        try:
            # Search in FiscalAPI
            response = fiscalapi_service._make_request(
                'GET',
                '/api/v4/people',
                params={'tin': rfc, 'limit': 1}
            )
            
            items = response.get('data', {}).get('items', [])
            
            if items and len(items) > 0:
                person = items[0]
                person_email = person.get('email', '').strip().lower()
                
                # Verify email match (security check)
                if person_email == email:
                    # Email matches - return data for autofill
                    logger.info(f"Recipient found and email matches for RFC {rfc}")
                    
                    return JsonResponse({
                        'found': True,
                        'match': True,
                        'data': {
                            'business_name': person.get('legalName', ''),
                            'postal_code': person.get('zipCode', ''),
                            'fiscal_regime': person.get('satTaxRegimeId', ''),
                            'cfdi_use': person.get('satCfdiUseId', 'G03'),
                        }
                    })
                else:
                    # RFC exists but email doesn't match - don't autofill (privacy)
                    logger.info(f"Recipient found but email doesn't match for RFC {rfc}")
                    return JsonResponse({
                        'found': True,
                        'match': False,
                        'message': 'RFC registrado pero email no coincide'
                    })
            else:
                # RFC not found - will be created on invoice
                logger.info(f"Recipient not found for RFC {rfc}")
                return JsonResponse({'found': False})
                
        except Exception as e:
            logger.error(f"Error looking up recipient: {str(e)}")
            return JsonResponse({'found': False, 'error': str(e)})
            
    except Exception as e:
        logger.error(f"Error in api_lookup_recipient: {str(e)}")
        return JsonResponse({'found': False, 'error': 'Error interno'}, status=500)
