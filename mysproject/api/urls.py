from django.urls import path
from . import views

from rest_framework_simplejwt.views import TokenRefreshView  # ✅ FIX

urlpatterns = [

    # AUTH
    path('login/', views.userlogin),
    path('token/refresh/', TokenRefreshView.as_view()),

    # PROFILE
    path('profile/', views.profilehandle),

    # USERNAME
    path('takeusername/', views.takeusername),

    # POSTS
    path('post/', views.posthandler),
    path('deletepost/<int:post_id>/', views.deletepost),

    # LIKES — ✅ FIX: trailing slash add பண்ணினோம்
    path('likes/<int:post_id>/', views.likeshandler),

    # FOLLOW — ✅ FIX: trailing slash add பண்ணினோம்
    path('follow/<int:user_id>/', views.followhandle),

    # COMMENTS
    path('comment/<int:post_id>/', views.commenthandler),
    path('deletecomment/<int:comment_id>/', views.deletecomment),

    # SORT
    path('sort/', views.sorthandler),
    path('sortdistrict/', views.sortedwithdistrict),

    # YOU
    path('you/', views.You),

    # FRIEND SYSTEM
    path('myid/', views.get_my_id),
    path('friend-requests/', views.get_friend_requests),
    path('friends/', views.get_friends),
    path('friend-status/<int:user_id>/', views.get_friend_status),
    path('friend-accept/<int:request_id>/', views.friend_accept),
    path('friend-reject/<int:request_id>/', views.friend_reject),
    path('friend-sent/', views.get_sent_requests),

    # REELS
    path('reels/', views.reelhandler),
    path('reels/<int:reel_id>/like/', views.reel_like),
    path('reels/<int:reel_id>/comments/', views.reel_comment),
    path('post/<int:post_id>/view/',    views.postviewhandler),
    path('post/<int:post_id>/viewers/', views.postviewershandler),
    path('sorthometown/', views.sorthometown),
    path('user-friends/<int:user_id>/', views.get_user_friends),
    path('friend-send/<int:user_id>/', views.send_friend_request),

]

# redis://red-d8t4623tqb8s73fbpp4g:6379
# redist url 

#SECRET_KEY=<இங்க உங்க generate பண்ணின secret key paste பண்ணுங்க>
# DEBUG=False
# ALLOWED_HOSTS=*
# DATABASE_URL=<Render PostgreSQL Internal Database URL paste பண்ணுங்க>
# REDIS_URL=<Render Redis Internal Key Value URL paste பண்ணுங்க>
# AWS_ACCESS_KEY_ID=<உங்க AWS Access Key ID>
# AWS_SECRET_ACCESS_KEY=<உங்க AWS Secret Access Key>
# AWS_STORAGE_BUCKET_NAME=<உங்க S3 bucket name>
# AWS_S3_REGION_NAME=<உங்க bucket region, உ.தா: ap-south-1>
# CLOUDFRONT_URL=<உங்க CloudFront domain, https:// இல்லாம, உ.தா: d123abc.cloudfront.net>



# build command 
# pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput

#start command 
# daphne -b 0.0.0.0 -p $PORT mysproject.asgi:application





# NpRLkAq4pXu2Lvf