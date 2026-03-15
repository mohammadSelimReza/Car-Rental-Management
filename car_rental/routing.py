from channels.routing import ProtocolTypeRouter, URLRouter
from chat.middleware import TokenAuthMiddleware
import chat.routing

application = ProtocolTypeRouter({
    "websocket": TokenAuthMiddleware(
        URLRouter(chat.routing.websocket_urlpatterns)
    ),
})