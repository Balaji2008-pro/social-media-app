import json
import os
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from .models import FriendRequest, Profilemodel

User = get_user_model()
BASE = os.environ.get('DJANGO_BASE_URL', 'http://10.0.2.2:8000')


class FriendConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.room    = f'friend_{self.user_id}'

        # ✅ Auth check
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close()
            return

        await self.channel_layer.group_add(self.room, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room, self.channel_name)

    async def receive(self, text_data):
        try:
            data   = json.loads(text_data)
            action = data.get('action')
            if action == 'send_request':
                await self.handle_send(data)
            elif action == 'accept_request':
                await self.handle_accept(data)
            elif action == 'reject_request':
                await self.handle_reject(data)
        except Exception as e:
            await self.send(text_data=json.dumps({
                'action': 'error', 'message': str(e)
            }))

    # =========================================
    # SEND REQUEST
    # =========================================

    async def handle_send(self, data):
        sender_id   = data.get('sender_id')
        receiver_id = data.get('receiver_id')
        result      = await self.db_send(sender_id, receiver_id)

        if result['success']:
            await self.channel_layer.group_send(
                f'friend_{receiver_id}',
                {
                    'type':            'friend_notification',
                    'action':          'new_request',
                    'request_id':      result['request_id'],
                    'sender_id':       sender_id,
                    'sender_username': result['sender_username'],
                    'sender_profile':  result['sender_profile'],
                    'message':         f"{result['sender_username']} sent you a friend request!"
                }
            )
            await self.send(text_data=json.dumps({
                'action':      'request_sent',
                'receiver_id': receiver_id
            }))
        else:
            await self.send(text_data=json.dumps({
                'action': 'error', 'message': result['message']
            }))

    # =========================================
    # ACCEPT REQUEST
    # =========================================

    async def handle_accept(self, data):
        request_id = data.get('request_id')
        result     = await self.db_accept(request_id)

        if result['success']:
            await self.channel_layer.group_send(
                f'friend_{result["sender_id"]}',
                {
                    'type':              'friend_notification',
                    'action':            'request_accepted',
                    'request_id':        request_id,
                    'acceptor_username': result['acceptor_username'],
                    'acceptor_profile':  result['acceptor_profile'],
                    'message':           f"{result['acceptor_username']} accepted your friend request! 🎉"
                }
            )
            await self.send(text_data=json.dumps({
                'action': 'accepted_done', 'request_id': request_id
            }))
        else:
            await self.send(text_data=json.dumps({
                'action': 'error', 'message': result['message']
            }))

    # =========================================
    # REJECT REQUEST
    # =========================================

    async def handle_reject(self, data):
        request_id = data.get('request_id')
        result     = await self.db_reject(request_id)

        if result['success']:
            await self.send(text_data=json.dumps({
                'action': 'rejected_done', 'request_id': request_id
            }))
        else:
            await self.send(text_data=json.dumps({
                'action': 'error', 'message': result['message']
            }))

    async def friend_notification(self, event):
        await self.send(text_data=json.dumps(event))

    # =========================================
    # DB OPERATIONS
    # =========================================

    @database_sync_to_async
    def db_send(self, sender_id, receiver_id):
        try:
            sender   = User.objects.get(id=sender_id)
            receiver = User.objects.get(id=receiver_id)

            if str(sender_id) == str(receiver_id):
                return {'success': False, 'message': 'Cannot add yourself'}

            existing = FriendRequest.objects.filter(
                sender=sender, receiver=receiver
            ).first()
            if existing:
                return {'success': False, 'message': f'Already {existing.status}'}

            reverse = FriendRequest.objects.filter(
                sender=receiver, receiver=sender
            ).first()
            if reverse and reverse.status == 'accepted':
                return {'success': False, 'message': 'Already friends'}

            req     = FriendRequest.objects.create(
                sender=sender, receiver=receiver, status='pending'
            )
            profile = Profilemodel.objects.filter(user=sender).first()
            # ✅ Absolute URL
            profile_url = f"{BASE}{profile.profile.url}" if profile and profile.profile else None

            return {
                'success':         True,
                'request_id':      req.id,
                'sender_username': sender.username,
                'sender_profile':  profile_url
            }
        except Exception as e:
            return {'success': False, 'message': str(e)}

    @database_sync_to_async
    def db_accept(self, request_id):
        try:
            req        = FriendRequest.objects.get(id=request_id)
            req.status = 'accepted'
            req.save()
            profile = Profilemodel.objects.filter(user=req.receiver).first()
            # ✅ Absolute URL
            profile_url = f"{BASE}{profile.profile.url}" if profile and profile.profile else None
            return {
                'success':           True,
                'sender_id':         req.sender.id,
                'acceptor_username': req.receiver.username,
                'acceptor_profile':  profile_url
            }
        except Exception as e:
            return {'success': False, 'message': str(e)}

    @database_sync_to_async
    def db_reject(self, request_id):
        try:
            req = FriendRequest.objects.get(id=request_id)
            req.delete()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'message': str(e)}