from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Count, Exists, OuterRef
from django.core.paginator import Paginator  # ✅ PAGINATION

import os

from api.models import User
from .models import (
    Profilemodel,
    Post,
    Likes,
    Follow,
    Comment,
    FriendRequest,
    Reel,
    ReelLike,
    ReelComment,
)

from .serializers import (
    UserSerializer,
    Profileserializer,
    Postserializer,
    Commentserializer
)

# =========================================
# LOGIN / AUTO REGISTER
# =========================================

@api_view(['POST'])
def userlogin(request):

    username = request.data.get("username")
    password = request.data.get("password")
    email    = request.data.get("email")
    district = request.data.get("district")

    if not username or not password:
        return Response({"error": "Username and password required"}, status=400)

    user = authenticate(username=username, password=password)

    if user is None:
        existing = User.objects.filter(username=username).first()
        if existing:
            return Response({"error": "Wrong password"}, status=400)
        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            district=district
        )

    refresh = RefreshToken.for_user(user)

    return Response({
        "access":   str(refresh.access_token),
        "refresh":  str(refresh),
        "username": user.username,
        "email":    user.email,
        "district": user.district,
    })

# =========================================
# PROFILE
# =========================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def profilehandle(request):

    if request.method == "GET":
        profile = Profilemodel.objects.filter(user=request.user).first()
        return Response({
            "profile": request.build_absolute_uri(profile.profile.url)
            if profile else None
        })

    image_file = request.FILES.get('profile')
    if not image_file:
        return Response({"error": "No image provided"}, status=400)

    profile, created = Profilemodel.objects.get_or_create(user=request.user)

    if not created and profile.profile:
        try:
            if os.path.isfile(profile.profile.path):
                os.remove(profile.profile.path)
        except Exception:
            pass

    profile.profile = image_file
    profile.save()

    return Response({
        "profile": request.build_absolute_uri(profile.profile.url)
    })

# =========================================
# POSTS  ✅ PAGINATION ADDED
# =========================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def posthandler(request):

    if request.method == "GET":

        # ?page=1&page_size=10
        page_number = int(request.query_params.get('page', 1))
        page_size   = int(request.query_params.get('page_size', 10))

        posts     = Post.objects.all().order_by('-created_at')
        paginator = Paginator(posts, page_size)
        page_obj  = paginator.get_page(page_number)

        data = []

        for p in page_obj.object_list:

            profile      = Profilemodel.objects.filter(user=p.user).first()
            likes_count  = Likes.objects.filter(post=p).count()
            follow_count = Follow.objects.filter(following=p.user).count()

            liked_users = []
            for like in Likes.objects.filter(post=p):
                liked_profile = Profilemodel.objects.filter(user=like.user).first()
                liked_users.append({
                    "username": like.user.username,
                    "profile":  request.build_absolute_uri(
                        liked_profile.profile.url
                    ) if liked_profile else None
                })

            is_following = Follow.objects.filter(
                follower=request.user, following=p.user
            ).exists()

            data.append({
                "id":          p.id,
                "title":       p.title,
                "post":        request.build_absolute_uri(p.post.url),
                "user_id":     p.user.id,
                "username":    p.user.username,
                "likes":       likes_count,
                "followcount": follow_count,
                "likedusers":  liked_users,
                "created_at":  p.created_at.isoformat(),
                "is_following": is_following,
                "profile":     request.build_absolute_uri(
                    profile.profile.url
                ) if profile else None
            })

        return Response({
            "results": data,
            "pagination": {
                "current_page": page_number,
                "total_pages":  paginator.num_pages,
                "total_posts":  paginator.count,
                "has_next":     page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
            }
        })

    # POST
    serializer = Postserializer(data=request.data)
    if serializer.is_valid():
        obj     = serializer.save(user=request.user)
        profile = Profilemodel.objects.filter(user=request.user).first()
        return Response({
            "id":          obj.id,
            "title":       obj.title,
            "post":        request.build_absolute_uri(obj.post.url),
            "user_id":     obj.user.id,
            "username":    obj.user.username,
            "likes":       0,
            "followcount": Follow.objects.filter(following=request.user).count(),
            "likedusers":  [],
            "created_at":  obj.created_at.isoformat(),
            "is_following": False,
            "profile":     request.build_absolute_uri(
                profile.profile.url
            ) if profile else None
        })

    return Response(serializer.errors, status=400)

# =========================================
# USERNAME
# =========================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def takeusername(request):
    return Response({
        "username": request.user.username,
        "district": request.user.district
    })

# =========================================
# LIKE / UNLIKE POST
# =========================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def likeshandler(request, post_id):

    post = get_object_or_404(Post, id=post_id)
    like = Likes.objects.filter(user=request.user, post=post)

    if like.exists():
        like.delete()
    else:
        Likes.objects.create(user=request.user, post=post)

    likes_count = Likes.objects.filter(post=post).count()

    liked_users = []
    for like in Likes.objects.filter(post=post):
        profile = Profilemodel.objects.filter(user=like.user).first()
        liked_users.append({
            "username": like.user.username,
            "profile":  request.build_absolute_uri(
                profile.profile.url
            ) if profile else None
        })

    return Response({"likes": likes_count, "likedusers": liked_users})

# =========================================
# FOLLOW / UNFOLLOW
# =========================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def followhandle(request, user_id):

    target = get_object_or_404(User, id=user_id)

    if target.id == request.user.id:
        return Response({"error": "Cannot follow yourself"}, status=400)

    obj = Follow.objects.filter(follower=request.user, following=target)

    if obj.exists():
        obj.delete()
    else:
        Follow.objects.create(follower=request.user, following=target)

    count = Follow.objects.filter(following=target).count()

    return Response({
        "count":        count,
        "is_following": Follow.objects.filter(
            follower=request.user, following=target
        ).exists()
    })

# =========================================
# POST COMMENTS
# =========================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def commenthandler(request, post_id):

    post = get_object_or_404(Post, id=post_id)

    if request.method == "GET":
        comments = Comment.objects.filter(post=post).order_by('-id')
        data = []
        for c in comments:
            profile = Profilemodel.objects.filter(user=c.user).first()
            data.append({
                "id":         c.id,
                "text":       c.text,
                "username":   c.user.username,
                "created_at": c.created_at.isoformat(),
                "profile":    request.build_absolute_uri(
                    profile.profile.url
                ) if profile else None
            })
        return Response(data)

    text = request.data.get("text")
    if not text:
        return Response({"error": "Text required"}, status=400)

    comment = Comment.objects.create(user=request.user, post=post, text=text)
    profile = Profilemodel.objects.filter(user=request.user).first()

    return Response({
        "id":         comment.id,
        "text":       comment.text,
        "username":   request.user.username,
        "created_at": comment.created_at.isoformat(),
        "profile":    request.build_absolute_uri(
            profile.profile.url
        ) if profile else None
    })

# =========================================
# DELETE COMMENT
# =========================================

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletecomment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, user=request.user)
    comment.delete()
    return Response({"message": "Comment deleted successfully"})

# =========================================
# DELETE POST
# =========================================

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def deletepost(request, post_id):
    post = get_object_or_404(Post, id=post_id, user=request.user)
    if post.post and os.path.isfile(post.post.path):
        os.remove(post.post.path)
    post.delete()
    return Response({"message": "Post deleted successfully"})

# =========================================
# SORT USERS  ✅ PAGINATION ADDED
# =========================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sorthandler(request):

    # ?page=1&page_size=20
    page_number = int(request.query_params.get('page', 1))
    page_size   = int(request.query_params.get('page_size', 20))

    # ✅ DB-level annotation — Python loop இல்லாமல் fast
    users = User.objects.annotate(
        followers=Count('following_set', distinct=True)
    ).order_by('-followers')

    paginator = Paginator(users, page_size)
    page_obj  = paginator.get_page(page_number)

    data = []
    for u in page_obj.object_list:
        profile = Profilemodel.objects.filter(user=u).first()
        data.append({
            "user_id":  u.id,
            "username": u.username,
            "district": u.district,
            "followers": u.followers,
            "profile":  request.build_absolute_uri(
                profile.profile.url
            ) if profile else None
        })

    return Response({
        "results": data,
        "pagination": {
            "current_page": page_number,
            "total_pages":  paginator.num_pages,
            "total_users":  paginator.count,
            "has_next":     page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
        }
    })

# =========================================
# USER PROFILE PAGE
# =========================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def You(request):
    user    = request.user
    profile = Profilemodel.objects.filter(user=user).first()
    posts   = Post.objects.filter(user=user)

    return Response({
        "username":  user.username,
        "district":  user.district,
        "followers": Follow.objects.filter(following=user).count(),
        "following": Follow.objects.filter(follower=user).count(),
        "profile":   request.build_absolute_uri(
            profile.profile.url
        ) if profile else None,
        "posts": [
            request.build_absolute_uri(p.post.url) for p in posts
        ]
    })

# =========================================
# SORTED WITH DISTRICT  ✅ PAGINATION ADDED
# =========================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sortedwithdistrict(request):

    # ?page=1&page_size=20
    page_number = int(request.query_params.get('page', 1))
    page_size   = int(request.query_params.get('page_size', 20))

    users = User.objects.annotate(
        follow_count=Count('following_set', distinct=True)
    ).order_by('-follow_count')

    paginator = Paginator(users, page_size)
    page_obj  = paginator.get_page(page_number)

    data = []
    for u in page_obj.object_list:
        profile = Profilemodel.objects.filter(user=u).first()
        data.append({
            "username":     u.username,
            "district":     u.district or "Unknown",
            "follow_count": u.follow_count,
            "profile":      request.build_absolute_uri(
                profile.profile.url
            ) if profile else None
        })

    return Response({
        "results": data,
        "pagination": {
            "current_page": page_number,
            "total_pages":  paginator.num_pages,
            "total_users":  paginator.count,
            "has_next":     page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
        }
    })

# =========================================
# FRIEND REQUEST VIEWS
# =========================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_id(request):
    return Response({'user_id': request.user.id})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_friend_requests(request):
    reqs = FriendRequest.objects.filter(
        receiver=request.user, status='pending'
    ).select_related('sender').order_by('-created_at')

    data = []
    for req in reqs:
        profile = Profilemodel.objects.filter(user=req.sender).first()
        data.append({
            'request_id':      req.id,
            'sender_id':       req.sender.id,
            'sender_username': req.sender.username,
            'sender_profile':  request.build_absolute_uri(
                profile.profile.url
            ) if profile and profile.profile else None,
            'created_at': req.created_at.isoformat()
        })
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_friends(request):
    sent     = FriendRequest.objects.filter(sender=request.user,   status='accepted').select_related('receiver')
    received = FriendRequest.objects.filter(receiver=request.user, status='accepted').select_related('sender')

    data = []
    seen = set()

    for req in sent:
        friend = req.receiver
        if friend.id not in seen:
            seen.add(friend.id)
            profile = Profilemodel.objects.filter(user=friend).first()
            data.append({
                'friend_id': friend.id,
                'username':  friend.username,
                'district':  friend.district,
                'profile':   request.build_absolute_uri(
                    profile.profile.url
                ) if profile and profile.profile else None
            })

    for req in received:
        friend = req.sender
        if friend.id not in seen:
            seen.add(friend.id)
            profile = Profilemodel.objects.filter(user=friend).first()
            data.append({
                'friend_id': friend.id,
                'username':  friend.username,
                'district':  friend.district,
                'profile':   request.build_absolute_uri(
                    profile.profile.url
                ) if profile and profile.profile else None
            })

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_friend_status(request, user_id):
    target   = get_object_or_404(User, id=user_id)
    sent     = FriendRequest.objects.filter(sender=request.user, receiver=target).first()
    received = FriendRequest.objects.filter(sender=target, receiver=request.user).first()

    if sent:
        return Response({'status': sent.status,     'direction': 'sent',     'request_id': sent.id})
    if received:
        return Response({'status': received.status, 'direction': 'received', 'request_id': received.id})

    return Response({'status': 'none'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def friend_accept(request, request_id):
    req = get_object_or_404(FriendRequest, id=request_id, receiver=request.user)
    req.status = 'accepted'
    req.save()
    return Response({'status': 'accepted'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def friend_reject(request, request_id):
    req = get_object_or_404(FriendRequest, id=request_id, receiver=request.user)
    req.delete()
    return Response({'status': 'rejected'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_sent_requests(request):
    sent = FriendRequest.objects.filter(sender=request.user).select_related('receiver')
    data = []
    for req in sent:
        data.append({
            'request_id':       req.id,
            'receiver_id':      req.receiver.id,
            'receiver_username': req.receiver.username,
            'status':           req.status
        })
    return Response(data)

# =========================================
# REELS  ✅ PAGINATION ADDED
# =========================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def reelhandler(request):

    if request.method == 'GET':

        # ?page=1&page_size=5
        page_number = int(request.query_params.get('page', 1))
        page_size   = int(request.query_params.get('page_size', 5))

        user_like = ReelLike.objects.filter(reel=OuterRef('pk'), user=request.user)

        reels_qs = Reel.objects.select_related('user').annotate(
            likes_count=Count('likes', distinct=True),
            comments_count=Count('comments', distinct=True),
            is_liked=Exists(user_like),
        ).order_by('-created_at')

        paginator = Paginator(reels_qs, page_size)
        page_obj  = paginator.get_page(page_number)

        data = []
        for r in page_obj.object_list:
            profile         = getattr(r.user, 'profilemodel', None)
            followers_count = Follow.objects.filter(following=r.user).count()

            data.append({
                'id':       r.id,
                'title':    r.title,
                'media':    request.build_absolute_uri(r.media.url),
                'username': r.user.username,
                'user_id':  r.user.id,
                'profile':  request.build_absolute_uri(
                    profile.profile.url
                ) if profile and profile.profile else None,
                'followers':  followers_count,
                'likes':      r.likes_count,
                'comments':   r.comments_count,
                'is_liked':   r.is_liked,
                'created_at': r.created_at.isoformat(),
            })

        return Response({
            "results": data,
            "pagination": {
                "current_page": page_number,
                "total_pages":  paginator.num_pages,
                "total_reels":  paginator.count,
                "has_next":     page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
            }
        })

    # POST REEL
    title = request.data.get('title')
    media = request.FILES.get('media')

    if not title or not media:
        return Response({'error': 'Title and media required'}, status=400)

    reel    = Reel.objects.create(user=request.user, title=title, media=media)
    profile = getattr(request.user, 'profilemodel', None)

    return Response({
        'id':       reel.id,
        'title':    reel.title,
        'media':    request.build_absolute_uri(reel.media.url),
        'username': request.user.username,
        'user_id':  request.user.id,
        'profile':  request.build_absolute_uri(
            profile.profile.url
        ) if profile and profile.profile else None,
        'followers': Follow.objects.filter(following=request.user).count(),
        'likes':     0,
        'comments':  0,
        'is_liked':  False,
        'created_at': reel.created_at.isoformat(),
    }, status=201)

# =========================================
# LIKE / UNLIKE A REEL
# =========================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reel_like(request, reel_id):

    reel     = get_object_or_404(Reel, id=reel_id)
    existing = ReelLike.objects.filter(user=request.user, reel=reel)

    if existing.exists():
        existing.delete()
        liked = False
    else:
        ReelLike.objects.create(user=request.user, reel=reel)
        liked = True

    return Response({
        'liked': liked,
        'likes': ReelLike.objects.filter(reel=reel).count(),
    })

# =========================================
# REEL COMMENTS  ✅ PAGINATION ADDED
# =========================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def reel_comment(request, reel_id):

    reel = get_object_or_404(Reel, id=reel_id)

    # -----------------------------------------
    # GET — list comments (newest first)  ✅ PAGINATED
    # -----------------------------------------
    if request.method == 'GET':

        # ?page=1&page_size=20
        page_number = int(request.query_params.get('page', 1))
        page_size   = int(request.query_params.get('page_size', 20))

        comments  = ReelComment.objects.filter(reel=reel).order_by('-id')
        paginator = Paginator(comments, page_size)
        page_obj  = paginator.get_page(page_number)

        data = []
        for c in page_obj.object_list:
            profile = Profilemodel.objects.filter(user=c.user).first()
            data.append({
                'id':         c.id,
                'username':   c.user.username,
                'text':       c.text,
                'created_at': c.created_at.isoformat(),
                'profile':    request.build_absolute_uri(
                    profile.profile.url
                ) if profile and profile.profile else None,
            })

        return Response({
            "results": data,
            "pagination": {
                "current_page":   page_number,
                "total_pages":    paginator.num_pages,
                "total_comments": paginator.count,
                "has_next":       page_obj.has_next(),
                "has_previous":   page_obj.has_previous(),
            }
        })

    # -----------------------------------------
    # POST — add a comment
    # -----------------------------------------
    text = request.data.get('text', '').strip()

    if not text:
        return Response({'error': 'Comment text is required'}, status=400)

    comment = ReelComment.objects.create(reel=reel, user=request.user, text=text)
    profile = Profilemodel.objects.filter(user=request.user).first()

    return Response({
        'id':         comment.id,
        'username':   request.user.username,
        'text':       comment.text,
        'created_at': comment.created_at.isoformat(),
        'profile':    request.build_absolute_uri(
            profile.profile.url
        ) if profile and profile.profile else None,
    }, status=201)