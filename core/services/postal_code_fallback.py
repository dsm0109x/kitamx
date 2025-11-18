"""
Fallback data for postal codes when Copomex API is not available.

Contains common postal codes for Mexico City and major cities.
To be used when API token is not configured or API is down.
"""

# Códigos postales comunes de CDMX
CDMX_POSTAL_CODES = {
    '14240': {
        'colonias': ['Pedregal de San Nicolás', 'Ampliación Tepepan', 'San Nicolás Totolapan'],
        'municipio': 'Tlalpan',
        'estado': 'Ciudad de México',
        'ciudad': 'Ciudad de México'
    },
    '06600': {
        'colonias': ['Juárez', 'Doctores', 'Centro'],
        'municipio': 'Cuauhtémoc',
        'estado': 'Ciudad de México',
        'ciudad': 'Ciudad de México'
    },
    '03100': {
        'colonias': ['Del Valle Centro', 'Del Valle Norte', 'Del Valle Sur'],
        'municipio': 'Benito Juárez',
        'estado': 'Ciudad de México',
        'ciudad': 'Ciudad de México'
    },
    '11000': {
        'colonias': ['Polanco', 'Granada', 'Ampliación Granada'],
        'municipio': 'Miguel Hidalgo',
        'estado': 'Ciudad de México',
        'ciudad': 'Ciudad de México'
    },
    '01000': {
        'colonias': ['San Ángel', 'Tizapán', 'Guadalupe Inn'],
        'municipio': 'Álvaro Obregón',
        'estado': 'Ciudad de México',
        'ciudad': 'Ciudad de México'
    },
    '04000': {
        'colonias': ['Coyoacán Centro', 'Villa Coyoacán', 'Del Carmen'],
        'municipio': 'Coyoacán',
        'estado': 'Ciudad de México',
        'ciudad': 'Ciudad de México'
    },
    '15000': {
        'colonias': ['Romero Rubio', 'Moctezuma 1a Sección', 'Moctezuma 2a Sección'],
        'municipio': 'Venustiano Carranza',
        'estado': 'Ciudad de México',
        'ciudad': 'Ciudad de México'
    },
    '07000': {
        'colonias': ['Lindavista', 'Magdalena de las Salinas', 'Nueva Atzacoalco'],
        'municipio': 'Gustavo A. Madero',
        'estado': 'Ciudad de México',
        'ciudad': 'Ciudad de México'
    },
}


def lookup_postal_code_fallback(codigo_postal: str) -> dict:
    """
    Lookup postal code in fallback data.

    Args:
        codigo_postal: 5-digit postal code

    Returns:
        dict with postal code data or error
    """
    data = CDMX_POSTAL_CODES.get(codigo_postal)

    if data:
        return {
            'success': True,
            'colonias': data['colonias'],
            'municipio': data['municipio'],
            'estado': data['estado'],
            'ciudad': data.get('ciudad', ''),
            'pais': 'México',
            'source': 'fallback'
        }

    # Si no está en fallback, aceptarlo pero sin autocompletar
    return {
        'success': True,
        'colonias': ['Nombre de tu colonia'],  # User will type manually
        'municipio': '',
        'estado': '',
        'ciudad': '',
        'pais': 'México',
        'source': 'manual',
        'warning': f'CP {codigo_postal} no encontrado en base de datos. Llena manualmente.'
    }
