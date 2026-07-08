import redis
from django.conf import settings
from rest_framework.response import Response

r = redis.Redis.from_url(settings.REDIS_URL) if settings.REDIS_URL else None

def check_login_limit():
    if r is None:
        return None   # Redis இல்லாட்டா, rate limit skip பண்ணி login proceed பண்ணும்
    try:
        count = r.incr("login_requests")
        if count == 1:
            r.expire("login_requests", 60)
        if count > 100:
            return Response(
                {"message": "Hypeza is experiencing high traffic. Please try again in a minute."},
                status=429
            )
    except redis.exceptions.RedisError:
        print("Redis rate limit check failed — allowing login as fallback")
        return None
    return None