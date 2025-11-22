# Kita.mx - Plataforma de Cobros y Facturación CFDI 4.0

> Plataforma mexicana para crear enlaces de pago y generar facturas electrónicas automáticamente

## 🚀 Características

- ✅ Enlaces de pago personalizados
- ✅ Integración con Mercado Pago
- ✅ Facturación CFDI 4.0 automática
- ✅ Timbrado con **facturapi.io** (PAC autorizado)
- ✅ Gestión de certificados CSD
- ✅ Dashboard analytics en tiempo real
- ✅ Multi-tenant con aislamiento completo

## 🔧 Stack Tecnológico

**Backend:**
- Python 3.12
- Django 5.2
- PostgreSQL (DigitalOcean Managed)
- Redis/Valkey (Cache + Celery)
- Celery + Beat (Background jobs)

**Integrations:**
- **facturapi.io** - Timbrado CFDI 4.0 (PAC)
- Mercado Pago - Procesamiento de pagos
- Postmark - Emails transaccionales
- DigitalOcean Spaces - Storage (S3)
- Google OAuth - Autenticación

**Frontend:**
- Alpine.js - Interactividad
- Tailwind CSS - Estilos
- Chart.js - Gráficas

## 📦 Instalación

```bash
# Clonar repositorio
git clone git@github.com:dsm0109x/kitamx.git
cd kitamx

# Crear entorno virtual
python -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales

# Migraciones
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Runserver
python manage.py runserver
```

## 🔑 Configuración de facturapi.io

### Credenciales Requeridas

```bash
# .env
FACTURAPI_URL=https://www.facturapi.io/v2
FACTURAPI_API_KEY=sk_live_XXXXX...  # Live Key
FACTURAPI_USER_KEY=sk_user_XXXXX... # User Key

# Kita como Emisor
KITA_RFC=SAHM661127B26
KITA_RAZON_SOCIAL=MARCO ANTONIO SANCHEZ HERNANDEZ
KITA_REGIMEN_FISCAL=612
KITA_CODIGO_POSTAL=14240
```

### Testing

```bash
# Test conexión con facturapi.io
python manage.py test_facturapi --test-connection

# Test creación de organización
python manage.py test_facturapi --test-organization

# Test upload de CSD
python manage.py test_facturapi --test-upload
```

## 📚 Documentación

Ver carpeta raíz para documentación detallada:
- `PLAN_MIGRACION_FACTURAPI.md` - Plan de migración
- `SECURITY_FIX_RFC_HIJACKING.md` - Fix de seguridad crítico
- `FACTURACION_SUSCRIPCION_COMPLETA.md` - Facturación de suscripciones

## 🔒 Seguridad

- ✅ Encriptación AES-256-GCM para certificados CSD
- ✅ Validación RFC + business_name
- ✅ Protección contra re-upload
- ✅ RFC hijacking prevention
- ✅ CSRF protection
- ✅ Rate limiting
- ✅ Audit logs

## 📝 Changelog

### 2025-11-20 - Migración facturapi.io
- Migrado de FiscalAPI a facturapi.io
- 10+ vulnerabilidades de seguridad corregidas
- Facturación de suscripciones implementada
- Onboarding mejorado con validaciones robustas

## 📄 Licencia

Propietario: Kita.mx
Contacto: dsm0109@ciencias.unam.mx

---

**Última actualización:** 2025-11-20 (Migración facturapi.io completada)
