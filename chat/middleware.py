# chat/middleware.py
import traceback
from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from channels.middleware import BaseMiddleware
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

User = get_user_model()


@database_sync_to_async
def get_user(user_id):
    try:
        user = User.objects.get(id=user_id)
        print(f"--- get_user: Found user {user.id} ({user.username})")
        return user
    except User.DoesNotExist:
        print(f"--- get_user: User {user_id} not found")
        return AnonymousUser()


class TokenAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        scope['user'] = AnonymousUser()
        print("--- TokenAuthMiddleware: Starting...")

        try:
            query_string = scope.get('query_string', b'').decode()
            print(f"--- Query string: {query_string}")

            query_params = parse_qs(query_string)
            token = query_params.get('token', [None])[0]

            if token:
                print(f"--- Token found (first 20 chars): {token[:20]}...")
                try:
                    access_token = AccessToken(token)
                    user_id = access_token['user_id']
                    print(f"--- Token valid. User ID: {user_id}")

                    user = await get_user(user_id)
                    if user.is_authenticated:
                        scope['user'] = user
                        print(f"--- SUCCESS: User {user.id} ({user.username}) authenticated")
                    else:
                        print("--- User inactive or not found")
                except (InvalidToken, TokenError) as e:
                    print(f"--- Token invalid/error: {str(e)}")
                except Exception as e:
                    print(f"--- Token processing exception: {str(e)}")
                    traceback.print_exc()
            else:
                print("--- No token in query string")
        except Exception as e:
            print(f"--- Middleware outer exception: {str(e)}")
            traceback.print_exc()

        return await super().__call__(scope, receive, send)