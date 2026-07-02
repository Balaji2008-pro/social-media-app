from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Count, Exists, OuterRef
from django.core.paginator import Paginator  
from django.db.models import Q
import os
from django.db.models import Count, Exists, OuterRef, Prefetch
import ffmpeg        
import tempfile      
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
    PostView
)

from .serializers import (
    UserSerializer,
    Profileserializer,
    Postserializer,
    Commentserializer
)

# views.py மேலே இந்த import சேர்க்கவும்
import uuid


# =========================================
# LOGIN / AUTO REGISTER
# =========================================
LIKED_USERS_LIMIT = 20


@api_view(['POST'])
def userlogin(request):

    username = request.data.get("username")
    password = request.data.get("password")
    email    = request.data.get("email")
    district = request.data.get("district")
    hometown = request.data.get("hometown") 


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
            district=district,
            hometown=hometown
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
            "profile": profile.profile.url if profile and profile.profile else None,
            "bio": profile.bio if profile else None
        })

    image_file = request.FILES.get('profile')
    bio = request.data.get('bio')

    if not image_file:
        return Response({"error": "No image provided"}, status=400)

    ext = image_file.name.rsplit('.', 1)[-1].lower() if '.' in image_file.name else 'jpg'
    image_file.name = f"{uuid.uuid4().hex}.{ext}"

    profile, created = Profilemodel.objects.get_or_create(user=request.user)

    if not created and profile.profile:
        try:
            profile.profile.storage.delete(profile.profile.name)
        except Exception:
            pass

    profile.profile = image_file
    if bio is not None:
        profile.bio = bio
    profile.save()

    return Response({
        "profile": profile.profile.url if profile and profile.profile else None,
        "bio": profile.bio
    })

# =========================================
# posthandler — FIXED (N+1 Query Fix)
# views.py-ல் இந்த function மட்டும் replace பண்ணவும்
#


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def posthandler(request):

    if request.method == "GET":

        page      = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 10))

        following_ids = set(
            Follow.objects.filter(
                follower=request.user
            ).values_list('following_id', flat=True)
        )

        liked_post_ids = set(
            Likes.objects.filter(
                user=request.user
            ).values_list('post_id', flat=True)
        )

        all_posts = Post.objects.select_related('user').annotate(
            likes_count=Count('likes', distinct=True),

            follow_count=Count('user__followers', distinct=True),
            views_count=Count('views', distinct=True),

            friend_count=Count(
                'user__sent_requests',
                filter=Q(user__sent_requests__status='accepted'),
                distinct=True
            ) + Count(
                'user__received_requests',
                filter=Q(user__received_requests__status='accepted'),
                distinct=True
            ),

        ).prefetch_related(

            # ✅ post owner-ன் profile
            Prefetch(
                'user__profilemodel',
                queryset=Profilemodel.objects.only('user_id', 'profile','bio'),
                to_attr='prefetched_owner_profile'
            ),

            # ✅ likedusers preview — likes + user + profile, ஒரே prefetch
            Prefetch(
                'likes_set',
                queryset=Likes.objects.select_related('user').order_by('-id').prefetch_related(
                    Prefetch(
                        'user__profilemodel',
                        queryset=Profilemodel.objects.only('user_id', 'profile'),
                        to_attr='prefetched_liker_profile'
                    )
                ),
                to_attr='prefetched_likes'
            ),
        ).order_by('-created_at')

        paginator = Paginator(all_posts, page_size)

        try:
            page_obj = paginator.page(page)
        except Exception:
            return Response({
                "results": [],
                "pagination": {
                    "current_page": page,
                    "total_pages":  paginator.num_pages,
                    "total_posts":  paginator.count,
                    "has_next":     False,
                    "has_previous": False,
                }
            })

        data = []

        for p in page_obj.object_list:

            # ✅ FIX: single object — getattr safe access
            profile = getattr(p.user, 'prefetched_owner_profile', None)

            # ✅ likedusers — top LIKED_USERS_LIMIT மட்டும்
            liked_users = []
            for like in p.prefetched_likes[:LIKED_USERS_LIMIT]:
                # ✅ FIX: single object — getattr safe access
                liker_profile = getattr(like.user, 'prefetched_liker_profile', None)
                liked_users.append({
                    "username": like.user.username,
                    "profile":  request.build_absolute_uri(
                        liker_profile.profile.url
                    ) if liker_profile and liker_profile.profile else None
                })

            is_following = p.user.id in following_ids
            is_liked      = p.id in liked_post_ids

            data.append({
                "id":           p.id,
                "title":        p.title,
                "post":         p.post.url,
                "media_type":   p.media_type,
                "user_id":      p.user.id,
                "username":     p.user.username,
                "likes":        p.likes_count,
                "is_liked":     is_liked,
                "followcount":  p.follow_count,
                "likedusers":   liked_users,
                "created_at":   p.created_at.isoformat(),
                "is_following": is_following,
                "profile":      request.build_absolute_uri(
                    profile.profile.url
                ) if profile and profile.profile else None,
                "bio":profile.bio if profile else None,
                "views": p.views_count,
                "friend_count": p.friend_count, 
 

            })

        return Response({
            "results": data,
            "pagination": {
                "current_page": page,
                "total_pages":  paginator.num_pages,
                "total_posts":  paginator.count,
                "has_next":     page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
            }
        })

    # =========================
    # POST — media_type auto detect
    # =========================
    media_file = request.FILES.get('post')
    media_type = 'image'

    if not media_file:
        return Response({'error': 'Media required'}, status=400)

    name = media_file.name.lower()
    is_video = name.endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm', '.3gp'))

    if is_video:
        media_type = 'video'

        # ✅ Step 1: Temp File-ல Save பண்ணு
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_input:
            for chunk in media_file.chunks():
                tmp_input.write(chunk)
            input_path = tmp_input.name

        output_path = input_path.replace('.mp4', '_compressed.mp4')

        try:
            # ✅ Step 2: FFmpeg Compress பண்ணு
            (
                ffmpeg
                .input(input_path)
                .output(
                    output_path,
                    vcodec='libx264',
                    crf=28,
                    preset='fast',
                    acodec='aac',
                    movflags='faststart'
                )
                .run(overwrite_output=True, quiet=True)
            )

            # ✅ Step 3: Compressed File-ஐ Django File-ஆ மாத்து
            from django.core.files import File
            unique_name = f"{uuid.uuid4().hex}.mp4"

            with open(output_path, 'rb') as f:
                compressed_file = File(f, name=unique_name)

                # ✅ Request Data-ல Replace பண்ணு
                request._files['post'] = compressed_file

                serializer = Postserializer(data=request.data)
                if serializer.is_valid():
                    obj = serializer.save(user=request.user, media_type=media_type)
                else:
                    return Response(serializer.errors, status=400)

        finally:
            # ✅ Step 4: Temp Files Delete பண்ணு
            if os.path.exists(input_path):
                os.unlink(input_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    else:
        # ✅ Image-ஆ இருந்தா Compress தேவையில்ல
        media_type = 'image'
        ext = name.rsplit('.', 1)[-1] if '.' in name else 'jpg'
        media_file.name = f"{uuid.uuid4().hex}.{ext}"

        serializer = Postserializer(data=request.data)
        if serializer.is_valid():
            obj = serializer.save(user=request.user, media_type=media_type)
        else:
            return Response(serializer.errors, status=400)

    profile = Profilemodel.objects.filter(user=request.user).first()

    return Response({
        "id":           obj.id,
        "title":        obj.title,
        "post":         obj.post.url,
        "media_type":   obj.media_type,
        "user_id":      obj.user.id,
        "username":     obj.user.username,
        "likes":        0,
        "is_liked":     False,
        "followcount":  Follow.objects.filter(following=request.user).count(),
        "likedusers":   [],
        "created_at":   obj.created_at.isoformat(),
        "is_following": False,
        "profile":      request.build_absolute_uri(
            profile.profile.url
        ) if profile and profile.profile else None,
        "bio": profile.bio if profile else None,
    })

# =========================================
# likeshandler — FIXED (N+1 fix + is_liked + limit)
# =========================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def likeshandler(request, post_id):

    post = get_object_or_404(Post, id=post_id)
    like_qs = Likes.objects.filter(user=request.user, post=post)

    if like_qs.exists():
        like_qs.delete()
        is_liked = False
    else:
        Likes.objects.create(user=request.user, post=post)
        is_liked = True

    likes_count = Likes.objects.filter(post=post).count()

    # ✅ FIX: 'user__profilemodel' (OneToOneField reverse — 'profilemodel_set' இல்லை)
    recent_likes = Likes.objects.filter(post=post).select_related(
        'user'
    ).prefetch_related(
        Prefetch(
            'user__profilemodel',
            queryset=Profilemodel.objects.only('user_id', 'profile'),
            to_attr='prefetched_profile'
        )
    ).order_by('-id')[:LIKED_USERS_LIMIT]

    liked_users = []
    for like in recent_likes:
        # ✅ FIX: single object — getattr safe access
        profile = getattr(like.user, 'prefetched_profile', None)
        liked_users.append({
            "username": like.user.username,
            "profile":  profile.profile.url if profile and profile.profile else None  # ✅

               
        })

    return Response({
        "likes":      likes_count,
        "likedusers": liked_users,
        "is_liked":   is_liked,
    })
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

    # =========================
    # GET — pagination + N+1 fix
    # =========================
    if request.method == "GET":

        page      = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))

        # ✅ FIX: 'user__profilemodel' (OneToOneField reverse — 'profilemodel_set' இல்லை)
        comments_qs = Comment.objects.filter(post=post).select_related(
            'user'
        ).prefetch_related(
            Prefetch(
                'user__profilemodel',
                queryset=Profilemodel.objects.only('user_id', 'profile'),
                to_attr='prefetched_profile'
            )
        ).order_by('-id')

        paginator = Paginator(comments_qs, page_size)

        try:
            page_obj = paginator.page(page)
        except Exception:
            return Response({
                "results": [],
                "pagination": {
                    "current_page":   page,
                    "total_pages":    paginator.num_pages,
                    "total_comments": paginator.count,
                    "has_next":       False,
                    "has_previous":   False,
                }
            })

        data = []
        for c in page_obj.object_list:
            # ✅ FIX: single object — getattr safe access
            profile = getattr(c.user, 'prefetched_profile', None)

            data.append({
                "id":         c.id,
                "text":       c.text,
                "username":   c.user.username,
                "created_at": c.created_at.isoformat(),
                "profile":    profile.profile.url if profile and profile.profile else None  # ✅

            })

        return Response({
            "results": data,
            "pagination": {
                "current_page":   page,
                "total_pages":    paginator.num_pages,
                "total_comments": paginator.count,
                "has_next":       page_obj.has_next(),
                "has_previous":   page_obj.has_previous(),
            }
        })

    # =========================
    # POST — comment create
    # =========================
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
        ) if profile and profile.profile else None
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
    
    # ✅ S3 storage — storage.delete() use பண்ணவும்
    # os.path.isfile() வேண்டாம் — S3-க்கு work ஆகாது
    if post.post:
        try:
            post.post.storage.delete(post.post.name)
        except Exception:
            pass  # file இல்லாட்டாலும் post delete ஆகும்
    
    post.delete()
    return Response({"message": "Post deleted successfully"})



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sorthandler(request):

    page_number = int(request.query_params.get('page', 1))
    page_size   = int(request.query_params.get('page_size', 20))

    users_qs = User.objects.annotate(
        followers_count=Count('followers', distinct=True)
    ).prefetch_related(
        Prefetch(
            'profilemodel',
            queryset=Profilemodel.objects.only('user_id', 'profile','bio'),
            to_attr='prefetched_profile'
        )
    ).order_by('-followers_count')

    paginator = Paginator(users_qs, page_size)
    page_obj  = paginator.get_page(page_number)

    data = []
    for u in page_obj.object_list:

        # ✅ FIX: single object — list இல்லை, getattr safe access
        profile = getattr(u, 'prefetched_profile', None)

        data.append({
            "user_id":   u.id,
            "username":  u.username,
            "district":  u.district,
            "followers": u.followers_count,
            "profile":   request.build_absolute_uri(
                profile.profile.url
            ) if profile and profile.profile else None,
            "hometown":  u.hometown,  
            "bio":profile.bio if profile else None

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
# =========================================
# You — FIXED (posts pagination)
# views.py-ல் இந்த function மட்டும் replace பண்ணவும்
#
# Import add பண்ணவும் (இல்லை என்றால்):
# from django.core.paginator import Paginator
# =========================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def You(request):

    user = request.user

    page      = int(request.query_params.get('page', 1))
    page_size = int(request.query_params.get('page_size', 30))

    profile = Profilemodel.objects.filter(user=user).first()

    posts_qs  = Post.objects.filter(user=user).order_by('-created_at')
    paginator = Paginator(posts_qs, page_size)
    page_obj  = paginator.get_page(page)

    posts_data = [
        request.build_absolute_uri(p.post.url)
        for p in page_obj.object_list
    ]

    return Response({
        "username":  user.username,
        "district":  user.district,
        "followers": Follow.objects.filter(following=user).count(),
        "following": Follow.objects.filter(follower=user).count(),
        "profile":   request.build_absolute_uri(
            profile.profile.url
        ) if profile and profile.profile else None,

        # ✅ current page posts மட்டும்
        "posts": posts_data,

        # ✅ NEW — pagination object + total_posts (stats count-க்கு)
        "pagination": {
            "current_page": page,
            "total_pages":  paginator.num_pages,
            "total_posts":  paginator.count,
            "has_next":     page_obj.has_next(),
            "has_previous": page_obj.has_previous(),
        }
    })

# =========================================
# SORTED WITH DISTRICT  ✅ PAGINATION + FIX
# =========================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sortedwithdistrict(request):

    page_number = int(request.query_params.get('page', 1))
    page_size   = int(request.query_params.get('page_size', 20))

    district_q = request.query_params.get('district', '').strip()

    # ✅ N+1 FIX + ✅ FIX: 'profilemodel' (OneToOneField reverse, 'profilemodel_set' இல்லை)
    users_qs = User.objects.annotate(
        follow_count=Count('followers', distinct=True)
    ).prefetch_related(
        Prefetch(
            'profilemodel',
            queryset=Profilemodel.objects.only('user_id', 'profile','bio'),
            to_attr='prefetched_profile'
        )
    ).order_by('-follow_count')

    if district_q:
        users_qs = users_qs.filter(district__icontains=district_q)

    paginator = Paginator(users_qs, page_size)
    page_obj  = paginator.get_page(page_number)

    data = []
    for u in page_obj.object_list:

        # ✅ FIX: single object — getattr safe access
        profile = getattr(u, 'prefetched_profile', None)

        data.append({
            "username":     u.username,
            "district":     u.district or "Unknown",
            "follow_count": u.follow_count,
            "profile":      request.build_absolute_uri(
                profile.profile.url
            ) if profile and profile.profile else None,
            "hometown": u.hometown or "Unknown",
            "bio": profile.bio if profile else None 

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

# =========================================
# get_friend_requests — FIXED (N+1 fix)
# views.py-ல் இந்த function மட்டும் replace பண்ணவும்
#
# Import add பண்ணவும் (இல்லை என்றால்):
# from django.db.models import Prefetch
#
# Pagination தேவையில்லை — pending requests usually small list
# Response format மாறவில்லை — Notifications.tsx-ல் மாற்றம் தேவையில்லை
# =========================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_friend_requests(request):

    reqs = FriendRequest.objects.filter(
        receiver=request.user, status='pending'
    ).select_related('sender').prefetch_related(
        Prefetch(
            'sender__profilemodel',
            queryset=Profilemodel.objects.only('user_id', 'profile'),
            to_attr='prefetched_profile'
        )
    ).order_by('-created_at')

    data = []
    for req in reqs:
        # ✅ DB hit இல்லை — prefetch cache, single object getattr
        profile = getattr(req.sender, 'prefetched_profile', None)

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
# =========================================
# =========================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_friends(request):

    # ✅ FIX: 'receiver__profilemodel' / 'sender__profilemodel'
    # (OneToOneField reverse — 'profilemodel_set' இல்லை)
    sent = FriendRequest.objects.filter(
        sender=request.user, status='accepted'
    ).select_related('receiver').prefetch_related(
        Prefetch(
            'receiver__profilemodel',
            queryset=Profilemodel.objects.only('user_id', 'profile','bio'),
            to_attr='prefetched_profile'
        )
    )

    received = FriendRequest.objects.filter(
        receiver=request.user, status='accepted'
    ).select_related('sender').prefetch_related(
        Prefetch(
            'sender__profilemodel',
            queryset=Profilemodel.objects.only('user_id', 'profile','bio'),
            to_attr='prefetched_profile'
        )
    )

    data = []
    seen = set()

    for req in sent:
        friend = req.receiver
        if friend.id not in seen:
            seen.add(friend.id)
            # ✅ FIX: single object — getattr safe access
            profile = getattr(friend, 'prefetched_profile', None)

            data.append({
                'friend_id': friend.id,
                'username':  friend.username,
                'district':  friend.district,
                'hometown':  friend.hometown,          
                'bio':       profile.bio if profile else None, 
                'profile':   request.build_absolute_uri(
                    profile.profile.url
                ) if profile and profile.profile else None,
                
            })

    for req in received:
        friend = req.sender
        if friend.id not in seen:
            seen.add(friend.id)
            profile = getattr(friend, 'prefetched_profile', None)

            data.append({
                'friend_id': friend.id,
                'username':  friend.username,
                'district':  friend.district,
                'hometown':  friend.hometown,        
                'bio':       profile.bio if profile else None,  
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

# =========================================
# get_sent_requests — FIXED
# views.py-ல் இந்த function மட்டும் replace பண்ணவும்
#
# Import மாற்றம் தேவையில்லை — already select_related இருக்கு
# Response format — backward compatible (மாறவில்லை)
# Home.tsx-ல் மாற்றம் தேவையில்லை (optional improvement மட்டும்)
# =========================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_sent_requests(request):


    sent = FriendRequest.objects.filter(
        sender=request.user
    ).select_related('receiver').order_by('-created_at')   # ✅ FIX: ordering சேர்த்தோம்

    status_filter = request.query_params.get('status', '').strip()
    if status_filter:
        sent = sent.filter(status=status_filter)

    data = []
    for req in sent:
        data.append({
            'request_id':        req.id,
            'receiver_id':       req.receiver.id,
            'receiver_username': req.receiver.username,
            'status':            req.status
        })

    return Response(data)

#
# Import add பண்ணவும் (இல்லை என்றால்):
# from django.db.models import Count, Exists, OuterRef, Prefetch
# =========================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def reelhandler(request):

    if request.method == 'GET':

        page_number = int(request.query_params.get('page', 1))
        page_size   = int(request.query_params.get('page_size', 5))

        user_like = ReelLike.objects.filter(
            reel=OuterRef('pk'), user=request.user
        )

        following_ids = set(
            Follow.objects.filter(
                follower=request.user
            ).values_list('following_id', flat=True)
        )

        # ✅ FIX: 'user__profilemodel' (OneToOneField reverse — 'profilemodel_set' இல்லை)
        reels_qs = Reel.objects.select_related('user').annotate(
            likes_count=Count('likes', distinct=True),
            comments_count=Count('comments', distinct=True),
            is_liked=Exists(user_like),
            followers_count=Count('user__followers', distinct=True),
        ).prefetch_related(
            Prefetch(
                'user__profilemodel',
                queryset=Profilemodel.objects.only('user_id', 'profile'),
                to_attr='prefetched_profile'
            )
        ).order_by('-created_at')

        paginator = Paginator(reels_qs, page_size)
        page_obj  = paginator.get_page(page_number)

        data = []
        for r in page_obj.object_list:
            # ✅ FIX: single object — getattr safe access
            profile = getattr(r.user, 'prefetched_profile', None)

            is_following = r.user.id in following_ids

            data.append({
                'id':           r.id,
                'title':        r.title,
                'media':        request.build_absolute_uri(r.media.url),
                'username':     r.user.username,
                'user_id':      r.user.id,
                'profile':      request.build_absolute_uri(
                    profile.profile.url
                ) if profile and profile.profile else None,
                'followers':    r.followers_count,
                'likes':        r.likes_count,
                'comments':     r.comments_count,
                'is_liked':     r.is_liked,
                'is_following': is_following,
                'created_at':   r.created_at.isoformat(),
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

    # =========================================
    # POST REEL
    # =========================================
   # =========================================
    # POST REEL
    # =========================================
    title = request.data.get('title')
    media = request.FILES.get('media')

    if not title or not media:
        return Response({'error': 'Title and media required'}, status=400)

    name = media.name.lower()
    is_video = name.endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm', '.3gp'))

    if is_video:
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_input:
            for chunk in media.chunks():
                tmp_input.write(chunk)
            input_path = tmp_input.name

        output_path = input_path.replace('.mp4', '_compressed.mp4')

        try:
            (
                ffmpeg
                .input(input_path)
                .output(
                    output_path,
                    vcodec='libx264',
                    crf=28,
                    preset='fast',
                    acodec='aac',
                    movflags='faststart'
                )
                .run(overwrite_output=True, quiet=True)
            )

            from django.core.files import File
            unique_name = f"{uuid.uuid4().hex}.mp4"

            with open(output_path, 'rb') as f:
                django_file = File(f, name=unique_name)
                reel = Reel.objects.create(
                    user=request.user,
                    title=title,
                    media=django_file
                )

        finally:
            if os.path.exists(input_path):
                os.unlink(input_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    else:
        media.name = f"{uuid.uuid4().hex}.{name.rsplit('.', 1)[-1]}"
        reel = Reel.objects.create(user=request.user, title=title, media=media)
    profile = Profilemodel.objects.filter(user=request.user).first()

    return Response({
        'id':           reel.id,
        'title':        reel.title,
        'media':        request.build_absolute_uri(reel.media.url),
        'username':     request.user.username,
        'user_id':      request.user.id,
        'profile':      request.build_absolute_uri(
            profile.profile.url
        ) if profile and profile.profile else None,
        'followers':    Follow.objects.filter(following=request.user).count(),
        'likes':        0,
        'comments':     0,
        'is_liked':     False,
        'is_following': False,
        'created_at':   reel.created_at.isoformat(),
    }, status=201)


# =========================================
# LIKE / UNLIKE — மாற்றம் இல்லை
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
# REEL COMMENTS — FIXED
# =========================================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def reel_comment(request, reel_id):

    reel = get_object_or_404(Reel, id=reel_id)

    if request.method == 'GET':

        page_number = int(request.query_params.get('page', 1))
        page_size   = int(request.query_params.get('page_size', 20))

        # ✅ FIX: 'user__profilemodel' (OneToOneField reverse)
        comments = ReelComment.objects.filter(
            reel=reel
        ).select_related('user').prefetch_related(
            Prefetch(
                'user__profilemodel',
                queryset=Profilemodel.objects.only('user_id', 'profile'),
                to_attr='prefetched_profile'
            )
        ).order_by('-id')

        paginator = Paginator(comments, page_size)
        page_obj  = paginator.get_page(page_number)

        data = []
        for c in page_obj.object_list:
            # ✅ FIX: single object — getattr safe access
            profile = getattr(c.user, 'prefetched_profile', None)

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

    # POST COMMENT
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
    
    
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def postviewhandler(request, post_id):
    """
    ✅ View record create — ஒரு user ஒரு post-ஐ ஒரே ஒரு முறை மட்டும்
    Frontend Set-ல் already tracked ஆனாலும், backend-லயும் unique_together guard
    """
    post = get_object_or_404(Post, id=post_id)
 
    # ✅ get_or_create — duplicate இல்லை, already viewed = silently ignore
    _, created = PostView.objects.get_or_create(
        user=request.user,
        post=post
    )
 
    views_count = PostView.objects.filter(post=post).count()
 
    return Response({
        "views":   views_count,
        "created": created   # True = new view, False = already viewed
    })
 
 
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def postviewershandler(request, post_id):
    """
    ✅ Viewers list — pagination + N+1 fix (OneToOneField prefetch)
    """
    post      = get_object_or_404(Post, id=post_id)
    page      = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
 
    viewers_qs = PostView.objects.filter(post=post).select_related(
        'user'
    ).prefetch_related(
        Prefetch(
            'user__profilemodel',
            queryset=Profilemodel.objects.only('user_id', 'profile'),
            to_attr='prefetched_profile'
        )
    ).order_by('-created_at')
 
    paginator = Paginator(viewers_qs, page_size)
 
    try:
        page_obj = paginator.page(page)
    except Exception:
        return Response({
            "results": [],
            "pagination": {
                "current_page":  page,
                "total_pages":   paginator.num_pages,
                "total_viewers": paginator.count,
                "has_next":      False,
                "has_previous":  False,
            }
        })
 
    data = []
    for v in page_obj.object_list:
        profile = getattr(v.user, 'prefetched_profile', None)
        data.append({
            "username": v.user.username,
            "profile":  request.build_absolute_uri(
                profile.profile.url
            ) if profile and profile.profile else None,
            "viewed_at": v.created_at.isoformat()
        })
 
    return Response({
        "results": data,
        "pagination": {
            "current_page":  page,
            "total_pages":   paginator.num_pages,
            "total_viewers": paginator.count,
            "has_next":      page_obj.has_next(),
            "has_previous":  page_obj.has_previous(),
        }
    })
 
 
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sorthometown(request):

    page_number = int(request.query_params.get('page', 1))
    page_size   = int(request.query_params.get('page_size', 20))

    hometown_q = request.query_params.get('hometown', '').strip()

    users_qs = User.objects.annotate(
        follow_count=Count('followers', distinct=True)
    ).prefetch_related(
        Prefetch(
            'profilemodel',
            queryset=Profilemodel.objects.only('user_id', 'profile','bio'),
            to_attr='prefetched_profile'
        )
    ).order_by('-follow_count')

    if hometown_q:
        users_qs = users_qs.filter(hometown__icontains=hometown_q)

    paginator = Paginator(users_qs, page_size)
    page_obj  = paginator.get_page(page_number)

    data = []
    for u in page_obj.object_list:
        profile = getattr(u, 'prefetched_profile', None)
        data.append({
            "username":     u.username,
            "district":     u.district or "Unknown",
            "hometown":     u.hometown or "Unknown",
            "follow_count": u.follow_count,
            "profile":      request.build_absolute_uri(
                profile.profile.url
            ) if profile and profile.profile else None,
            "bio": profile.bio if profile else None,  

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
    
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_friends(request, user_id):
    target = get_object_or_404(User, id=user_id)

    page      = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))

    sent = FriendRequest.objects.filter(
        sender=target, status='accepted'
    ).select_related('receiver').prefetch_related(
        Prefetch(
            'receiver__profilemodel',
            queryset=Profilemodel.objects.only('user_id', 'profile', 'bio'),
            to_attr='prefetched_profile'
        )
    )

    received = FriendRequest.objects.filter(
        receiver=target, status='accepted'
    ).select_related('sender').prefetch_related(
        Prefetch(
            'sender__profilemodel',
            queryset=Profilemodel.objects.only('user_id', 'profile', 'bio'),
            to_attr='prefetched_profile'
        )
    )

    data = []
    seen = set()

    for req in sent:
        friend = req.receiver
        if friend.id not in seen:
            seen.add(friend.id)
            profile = getattr(friend, 'prefetched_profile', None)
            data.append({
                'friend_id': friend.id,
                'username':  friend.username,
                'district':  friend.district,
                'hometown':  friend.hometown,
                'bio':       profile.bio if profile else None,
                'profile':   request.build_absolute_uri(
                    profile.profile.url
                ) if profile and profile.profile else None,
            })

    for req in received:
        friend = req.sender
        if friend.id not in seen:
            seen.add(friend.id)
            profile = getattr(friend, 'prefetched_profile', None)
            data.append({
                'friend_id': friend.id,
                'username':  friend.username,
                'district':  friend.district,
                'hometown':  friend.hometown,
                'bio':       profile.bio if profile else None,
                'profile':   request.build_absolute_uri(
                    profile.profile.url
                ) if profile and profile.profile else None,
            })

    # Pagination
    total       = len(data)
    start       = (page - 1) * page_size
    end         = start + page_size
    paged_data  = data[start:end]
    total_pages = (total + page_size - 1) // page_size

    return Response({
        'results': paged_data,
        'pagination': {
            'current_page': page,
            'total_pages':  total_pages,
            'total_friends': total,
            'has_next':     page < total_pages,
            'has_previous': page > 1,
        }
    })
    
    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_friend_request(request, user_id):
    target = get_object_or_404(User, id=user_id)

    if target.id == request.user.id:
        return Response({'error': 'Cannot add yourself'}, status=400)

    existing = FriendRequest.objects.filter(sender=request.user, receiver=target).first()
    if existing:
        return Response({'status': existing.status, 'message': f'Already {existing.status}'}, status=200)

    reverse = FriendRequest.objects.filter(sender=target, receiver=request.user).first()
    if reverse and reverse.status == 'accepted':
        return Response({'status': 'accepted', 'message': 'Already friends'}, status=200)
    if reverse and reverse.status == 'pending':
        # அவங்க ஏற்கனவே உங்களுக்கு request அனுப்பியிருந்தா, accept பண்ணுங்க
        reverse.status = 'accepted'
        reverse.save()
        return Response({'status': 'accepted', 'message': 'Friend request accepted'}, status=200)

    req = FriendRequest.objects.create(sender=request.user, receiver=target, status='pending')
    return Response({'status': 'pending', 'request_id': req.id}, status=201)