import os
import django
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'car_rental.settings')
django.setup()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import chat.routing
from chat.middleware import TokenAuthMiddleware  # ← your middleware


application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": TokenAuthMiddleware(          # ← your custom JWT middleware FIRST
        AuthMiddlewareStack(                   # then Django session auth as fallback
            URLRouter(chat.routing.websocket_urlpatterns)
        )
    ),
})