from rest_framework import serializers
from .models import Profilemodel, Post, Comment, FCMToken,Party, PartyMembership, PartyAnnouncement
from api.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'district']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User(
            username=validated_data['username'],
            email=validated_data['email'],
            district=validated_data.get('district'),
            is_active=True
        )
        user.set_password(validated_data['password'])
        user.save()
        return user


class Profileserializer(serializers.ModelSerializer):
    class Meta:
        model = Profilemodel
        fields = ['id', 'profile']
        read_only_fields = ['id']


class Postserializer(serializers.ModelSerializer):
    views = serializers.SerializerMethodField()  # ✅ சேர்க்கவும்

    class Meta:
        model = Post
        fields = ['id', 'title', 'post', 'created_at','views']
        read_only_fields = ['id', 'created_at']
        
    def get_views(self, obj):
        return obj.views.count()


class Commentserializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    profile = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ['id', 'text', 'created_at', 'username', 'profile']
        read_only_fields = ['id', 'created_at']

    def get_profile(self, obj):
        profile = Profilemodel.objects.filter(user=obj.user).first()
        if profile:
            return self.context['request'].build_absolute_uri(profile.profile.url)
        return None
    

class FCMTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = FCMToken
        fields = ['id', 'token', 'device_id']
        read_only_fields = ['id']
        
        
# =========================================
# PARTY SERIALIZERS
# =========================================

class PartySerializer(serializers.ModelSerializer):
    members_count = serializers.SerializerMethodField()
    creator_username = serializers.CharField(source='creator.username', read_only=True)
    is_joined = serializers.SerializerMethodField()
    is_verified = serializers.SerializerMethodField()

    class Meta:
        model = Party
        fields = [
            'id', 'party_name', 'leader_name', 'symbol', 'description',
            'district', 'created_at', 'creator_username', 'members_count', 'is_joined', 'is_verified'
        ]
        read_only_fields = ['id', 'created_at']

    def get_members_count(self, obj):
        return obj.members.count()

    def get_is_joined(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.members.filter(user=request.user).exists()
        return False

    def get_is_verified(self, obj):
        return obj.members.count() >= 100
    
    
class PartyAnnouncementSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = PartyAnnouncement
        fields = ['id', 'content', 'created_at', 'author_username']
        read_only_fields = ['id', 'created_at']