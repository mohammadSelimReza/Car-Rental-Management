from django.urls import path
from . import views

urlpatterns = [
    path('room/<int:booking_id>/', views.get_chat_room, name='get_chat_room'),
    path('my-chats/', views.get_user_chats, name='get_user_chats'),
]