from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/friend/(?P<user_id>\d+)/$', consumers.FriendConsumer.as_asgi()),
]
