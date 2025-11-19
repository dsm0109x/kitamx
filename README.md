# Kita - Plataforma de Facturación Electrónica 🚀
*v1.0.4*

Plataforma SaaS multi-tenant para generación y gestión de facturas electrónicas CFDI (Comprobante Fiscal Digital por Internet) en México.

[![CircleCI](https://circleci.com/gh/dsm0109x/kita.svg?style=shield)](https://circleci.com/gh/dsm0109x/kita)
[![Django](https://img.shields.io/badge/Django-5.2.6-green.svg)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)

## Características principales

- **Multi-tenant**: Gestión de múltiples empresas con datos aislados
- **Facturación CFDI 4.0**: Integración con PAC (FiscalAPI)
- **Gestión de Certificados**: Almacenamiento seguro de CSD con cifrado envelope
- **Pagos en línea**: Integración con Mercado Pago
- **Notificaciones**: WhatsApp Cloud API y Email (Postmark)
- **Tareas asíncronas**: Celery + Redis/Valkey para procesamiento en background
- **Analytics**: Dashboard con métricas de facturación y pagos
- **Suscripciones**: Sistema de planes mensuales con período de prueba

## Stack Tecnológico

### Backend
- **Framework**: Django 5.2.6 (Python 3.12+)
- **Base de datos**: PostgreSQL 14+ (DigitalOcean Managed Database)
- **Cache/Queue**: Redis/Valkey (SSL enabled)
- **Task Queue**: Celery 5.4 + Flower 2.0
- **Storage**: DigitalOcean Spaces (S3-compatible, boto3)

### Integraciones
- **PAC**: FiscalAPI (timbrado CFDI 4.0)
- **Pagos**: Mercado Pago (OAuth + Webhooks)
- **Email**: Postmark (con tracking de eventos)
- **WhatsApp**: Meta Cloud API
- **Monitoreo**: Sentry
- **Auth**: Google OAuth 2.0

### Seguridad
- **Autenticación**: Django Allauth + Google OAuth
- **Anti-bot**: Cloudflare Turnstile
- **CSP**: Content Security Policy headers
- **Rate limiting**: django-ratelimit (5 intentos/5min)
- **Cifrado**: Envelope encryption AES-256-GCM para certificados CSD
- **Auditoría**: Logs inmutables de acciones críticas

## Estructura del proyecto

```
kita/
├── accounts/          # Gestión de usuarios y autenticación
├── audit/            # Sistema de auditoría
├── billing/          # Suscripciones y planes
├── config/           # Configuraciones compartidas
├── core/             # Funcionalidad core (multi-tenancy, middleware)
├── dashboard/        # Dashboard principal
├── invoicing/        # Módulo de facturación CFDI
├── kita/             # Configuración principal de Django
├── kita_ia/          # Funcionalidades de IA
├── legal/            # Páginas legales (términos, privacidad)
├── links/            # Enlaces de pago
├── onboarding/       # Proceso de registro inicial
├── payments/         # Procesamiento de pagos
├── webhooks/         # Manejo de webhooks externos
├── static/           # Archivos estáticos (CSS, JS, imágenes)
├── templates/        # Templates Django
└── media/            # Archivos subidos por usuarios
```

## Instalación y Configuración

### Requisitos previos

- Python 3.12+
- PostgreSQL 14+
- Redis/Valkey
- pip y virtualenv

### Setup local

1. **Clonar el repositorio**
   ```bash
   git clone git@github.com:dsm0109x/kita.git
   cd kita
   ```

2. **Crear y activar entorno virtual**
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```

3. **Instalar dependencias**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variables de entorno**
   ```bash
   cp .env.example .env
   # Editar .env con tus credenciales
   ```

5. **Configurar base de datos**
   ```bash
   python manage.py migrate
   ```

6. **Crear superusuario**
   ```bash
   python manage.py createsuperuser
   ```

7. **Recolectar archivos estáticos**
   ```bash
   python manage.py collectstatic --noinput
   ```

8. **Ejecutar servidor de desarrollo**
   ```bash
   python manage.py runserver
   ```

9. **Ejecutar Celery worker (en otra terminal)**
   ```bash
   celery -A kita worker -l info
   ```

10. **Ejecutar Celery beat (en otra terminal)**
    ```bash
    celery -A kita beat -l info
    ```

### Acceder a la aplicación

- **Frontend**: http://127.0.0.1:8000
- **Admin**: http://127.0.0.1:8000/admin
- **Flower** (monitoring Celery): http://127.0.0.1:5555

## Deployment en Producción

### Requisitos del servidor

- Ubuntu 22.04+ / Debian 11+
- Python 3.12+
- Nginx (reverse proxy)
- Systemd (para servicios)
- PostgreSQL 14+ o Managed Database
- Redis/Valkey para cache y queues
- Acceso SSH con clave pública

### Proceso de deployment

1. **SSH al servidor**
   ```bash
   ssh root@tu-servidor
   ```

2. **Clonar repositorio en /opt/kita**
   ```bash
   cd /opt
   git clone git@github.com:dsm0109x/kita.git
   cd kita
   ```

3. **Crear entorno virtual e instalar dependencias**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt gunicorn
   ```

4. **Configurar variables de entorno**
   ```bash
   cp .env.example .env
   nano .env  # Configurar con valores de producción
   ```

5. **Ejecutar migraciones**
   ```bash
   python manage.py migrate
   ```

6. **Recolectar archivos estáticos**
   ```bash
   python manage.py collectstatic --noinput
   ```

7. **Configurar servicios systemd**

   Crear `/etc/systemd/system/kita.service`:
   ```ini
   [Unit]
   Description=Kita Django Application
   After=network.target

   [Service]
   Type=notify
   User=root
   WorkingDirectory=/opt/kita
   ExecStart=/opt/kita/venv/bin/gunicorn --workers 4 --bind 0.0.0.0:8000 kita.wsgi:application
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

   Crear `/etc/systemd/system/kita-celery.service`:
   ```ini
   [Unit]
   Description=Kita Celery Worker
   After=network.target

   [Service]
   Type=forking
   User=root
   WorkingDirectory=/opt/kita
   ExecStart=/opt/kita/venv/bin/celery -A kita worker -l info
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

   Crear `/etc/systemd/system/kita-celery-beat.service`:
   ```ini
   [Unit]
   Description=Kita Celery Beat
   After=network.target

   [Service]
   Type=simple
   User=root
   WorkingDirectory=/opt/kita
   ExecStart=/opt/kita/venv/bin/celery -A kita beat -l info
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

8. **Habilitar e iniciar servicios**
   ```bash
   systemctl daemon-reload
   systemctl enable kita kita-celery kita-celery-beat
   systemctl start kita kita-celery kita-celery-beat
   ```

9. **Configurar Nginx** (ejemplo básico)
   ```nginx
   server {
       listen 80;
       server_name kita.mx;

       location /static/ {
           alias /opt/kita/staticfiles/;
       }

       location /media/ {
           alias /opt/kita/media/;
       }

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }
   }
   ```

10. **Configurar SSL con Let's Encrypt**
    ```bash
    apt install certbot python3-certbot-nginx
    certbot --nginx -d kita.mx
    ```

### Actualizaciones

Para actualizar el código en producción:

```bash
cd /opt/kita
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
systemctl restart kita kita-celery kita-celery-beat
systemctl reload nginx
```

## Testing

```bash
# Ejecutar todos los tests
python manage.py test

# Con coverage
coverage run --source='.' manage.py test
coverage report

# Test específico de una app
python manage.py test accounts
python manage.py test core

# Con verbose output
python manage.py test --verbosity=2
```

## Variables de entorno importantes

Ver `.env.example` para la lista completa. Las más críticas:

### Core Django
- `DJANGO_SECRET_KEY`: Clave secreta de Django (generar nueva en producción)
- `DATABASE_URL`: Conexión a PostgreSQL
- `VALKEY_URL`: Conexión a Redis/Valkey
- `DEBUG`: Debe ser `False` en producción
- `ALLOWED_HOSTS`: Dominios permitidos separados por comas

### Servicios Externos
- `FISCALAPI_API_KEY`: API key para timbrado CFDI
- `MERCADOPAGO_APP_ID`: App ID de Mercado Pago
- `POSTMARK_TOKEN`: Token de servidor Postmark
- `GOOGLE_OAUTH_CLIENT_ID`: Cliente OAuth de Google
- `TURNSTILE_SITE_KEY`: Site key de Cloudflare Turnstile

## Monitoreo y Observabilidad

- **Sentry**: Captura de errores y performance monitoring en producción
- **Flower**: Monitoring de tareas Celery en tiempo real
- **Django Debug Toolbar**: Profiling y debugging (solo desarrollo)
- **Logs**: Sistema centralizado con rotación automática
- **Health Checks**: Endpoint `/health/` para monitoreo de uptime

## Seguridad

- Todas las variables sensibles deben estar en `.env` (NUNCA en el código)
- `.env` está en `.gitignore` y NO debe subirse a GitHub
- Los certificados CSD se almacenan cifrados en DigitalOcean Spaces
- HTTPS obligatorio en producción (configurado en settings.py)
- Rate limiting en endpoints críticos
- CSP headers configurados
- CSRF protection habilitado

## Contribuir

Este es un proyecto privado. Para contribuir:

1. Crear un branch desde `main`
2. Hacer cambios y commits descriptivos en español
3. Seguir convenciones de commit: `feat:`, `fix:`, `docs:`, `chore:`
4. Crear Pull Request con descripción clara
5. Esperar revisión y aprobación del equipo
6. CI/CD automático via CircleCI al merge a `production`

## Soporte

Para reportar bugs o solicitar features:
- **Issues**: Crear issue en el repositorio privado
- **Email**: Contactar al equipo de desarrollo
- **Documentación**: Ver archivos en `/docs` para detalles técnicos

## Licencia

Propiedad de Kita. Todos los derechos reservados.

---

**Desarrollado con ❤️ en México 🇲🇽**
