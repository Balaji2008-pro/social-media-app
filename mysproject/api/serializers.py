from rest_framework import serializers
from .models import Profilemodel, Post, Comment, FCMToken
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