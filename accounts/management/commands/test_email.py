from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings


class Command(BaseCommand):
    help = 'Test email configuration with Postmark'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email address to send test email to')

    def handle(self, *args, **options):
        email = options['email']

        try:
            send_mail(
                subject='🚀 Kita - Test Email Configuration',
                message='Este es un email de prueba para verificar la configuración de Postmark.\n\nSi recibes este mensaje, la configuración está funcionando correctamente!',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )

            self.stdout.write(
                self.style.SUCCESS(f'✅ Email enviado exitosamente a {email}')
            )
            self.stdout.write(f'📧 Desde: {settings.DEFAULT_FROM_EMAIL}')
            self.stdout.write(f'🔑 Token configurado: {settings.EMAIL_HOST_USER[:10]}...')

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error enviando email: {str(e)}')
            )
            return