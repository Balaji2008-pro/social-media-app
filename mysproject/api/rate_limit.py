import redis
from django.conf import settings
from rest_framework.response import Response

r = redis.Redis.from_url(
    settings.REDIS_URL,
    socket_connect_timeout=3,   # ✅ 3 sec-க்கு மேல connect ஆகாட்டா fail
    socket_timeout=3,           # ✅ 3 sec-க்கு மேல command run ஆகாட்டா fail
) if settings.REDIS_URL else None


def check_login_limit():
    if r is None:
        return None
    try:
        count = r.incr("login_requests")
        if count == 1:
            r.expire("login_requests", 60)
        if count > 100:
            return Response(
                {"message": "Hypeza is experiencing high traffic. Please try again in a minute."},
                status=429
            )
    except redis.exceptions.RedisError as e:
        print(f"Redis rate limit check failed — allowing login as fallback: {e}")
        return None
    return None