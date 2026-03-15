import json
import traceback
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatRoom, ChatMessage
from django.contrib.auth import get_user_model

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        print(f"--- [CONNECT] New connection attempt from {self.scope['client']}")

        user = self.scope['user']
        print(f"--- [CONNECT] Scope user: {user} (authenticated: {user.is_authenticated})")

        if user.is_anonymous:
            print("--- [CONNECT] Anonymous user → rejecting (403)")
            await self.close(code=4001) 
            return

        try:
            self.room_id = self.scope['url_route']['kwargs']['room_id']
            self.room_group_name = f'chat_{self.room_id}'
            print(f"--- [CONNECT] Requested room: {self.room_id}")
        except KeyError:
            print("--- [CONNECT] No room_id in URL route → invalid URL")
            await self.close()
            return

        room = await self.get_room()
        if not room:
            print(f"--- [CONNECT] Room {self.room_id} does not exist → closing")
            await self.close()
            return

        is_allowed = await self.is_user_in_room(room)
        if not is_allowed:
            print(f"--- [CONNECT] User {user} is NOT in room {self.room_id} → rejecting")
            await self.close(code=4003)
            return

        print(f"--- [CONNECT] User {user} authorized for room {self.room_id} → accepting")
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        print(f"--- [DISCONNECT] Connection closed with code {close_code}")
        if hasattr(self, 'room_group_name') and self.room_group_name:
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message = text_data_json.get('message', '').strip()

            if not message:
                print("--- [RECEIVE] Empty message → ignoring")
                return

            user = self.scope['user']
            print(f"--- [RECEIVE] New message from {user}: {message[:50]}...")

            saved_message = await self.save_message(message, user)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'sender_id': user.id,
                    'sender_name': user.username,
                    'timestamp': saved_message.created_at.isoformat(),
                    'message_id': saved_message.id
                }
            )

        except json.JSONDecodeError:
            print("--- [RECEIVE] Invalid JSON received")
        except Exception as e:
            print(f"--- [RECEIVE] Error: {str(e)}")
            traceback.print_exc()

    async def chat_message(self, event):
        """Receive message from room group and send to WebSocket"""
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender_id': event['sender_id'],
            'sender_name': event['sender_name'],
            'timestamp': event['timestamp'],
            'message_id': event['message_id']
        }))


    @database_sync_to_async
    def get_room(self):
        try:
            return ChatRoom.objects.select_related('customer', 'agent').get(id=self.room_id)
        except ChatRoom.DoesNotExist:
            return None

    @database_sync_to_async
    def is_user_in_room(self, room):
        if not room:
            return False
        return self.scope['user'] == room.customer or self.scope['user'] == room.agent

    @database_sync_to_async
    def save_message(self, content, sender):
        room = ChatRoom.objects.get(id=self.room_id)
        msg = ChatMessage.objects.create(
            room=room,
            sender=sender,
            content=content
        )
        return msg