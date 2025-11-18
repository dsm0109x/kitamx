from django.urls import path
from . import views

app_name = 'webhooks'

urlpatterns = [
    # Webhook endpoints
    path('mercadopago/', views.mercadopago_webhook, name='mercadopago'),
    path('kita-billing/', views.kita_billing_webhook, name='kita_billing'),

    # Postmark email webhook (both with and without trailing slash)
    path('postmark/', views.postmark_webhook, name='postmark'),
    path('postmark', views.postmark_webhook, name='postmark_no_slash'),
]