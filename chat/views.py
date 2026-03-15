from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import ChatRoom, ChatMessage
from .serializers import ChatMessageSerializer
from customers.models import RentalRequest


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_room(request, booking_id):
    if not request.user.is_authenticated:
        return Response({"error": "Not authenticated"}, status=401)

    booking = get_object_or_404(RentalRequest, id=booking_id)

    customer = booking.customer
    agent_user = booking.car.assigned_agent.user if booking.car.assigned_agent else None

    if request.user != customer and request.user != agent_user:
        return Response({"error": "Not authorized for this booking"}, status=403)

    room, created = ChatRoom.objects.get_or_create(
        rental_request=booking,
        customer=customer,
        agent=agent_user
    )

    messages = ChatMessage.objects.filter(room=room).order_by('created_at')[:50]
    serializer = ChatMessageSerializer(messages, many=True)

    if request.user == customer:
        other_name = (
            agent_user.agent_profile.name
            if agent_user and hasattr(agent_user, 'agent_profile') and agent_user.agent_profile
            else "Unknown Agent"
        )
    else:
        other_name = (
            customer.customer_profile.name
            if hasattr(customer, 'customer_profile') and customer.customer_profile
            else "Unknown Customer"
        )

    return Response({
        "room_id": room.id,
        "messages": serializer.data,
        "other_participant": other_name.strip() or "Unnamed"
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_chats(request):
    user = request.user

    if hasattr(user, 'customer_profile'):
        rooms = ChatRoom.objects.filter(customer=user)
        is_customer = True
    elif hasattr(user, 'agent_profile'):
        rooms = ChatRoom.objects.filter(agent=user)
        is_customer = False
    else:
        return Response({"error": "Not a customer or agent"}, status=403)

    data = []
    for room in rooms:
        last_msg = room.messages.last()

        if is_customer:
            other_name = (
                room.agent.agent_profile.name
                if room.agent and hasattr(room.agent, 'agent_profile') and room.agent.agent_profile
                else "Unknown Agent"
            )
        else:
            other_name = (
                room.customer.customer_profile.name
                if room.customer and hasattr(room.customer, 'customer_profile') and room.customer.customer_profile
                else "Unknown Customer"
            )

        data.append({
            "room_id": room.id,
            "booking_id": room.rental_request.id if room.rental_request else None,
            "other_user": other_name.strip() or "Unnamed",
            "last_message": last_msg.content[:50] if last_msg else "",
            "last_message_time": last_msg.created_at.isoformat() if last_msg else None,
            "unread_count": room.messages.filter(is_read=False).exclude(sender=user).count()
        })

    return Response({"chats": data})