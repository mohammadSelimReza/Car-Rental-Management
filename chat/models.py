from django.db import models
from django.contrib.auth import get_user_model
from customers.models import RentalRequest 

User = get_user_model()


class ChatRoom(models.Model):
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='customer_chats')
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='agent_chats')
    rental_request = models.ForeignKey(RentalRequest, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['customer', 'agent', 'rental_request']

    def __str__(self):
        return f"Chat {self.customer} ↔ {self.agent}"


class ChatMessage(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender}: {self.content[:50]}"