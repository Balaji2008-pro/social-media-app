from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    district = models.CharField(max_length=50, null=True, blank=True)
    hometown = models.CharField(max_length=50, null=True, blank=True)  

class Profilemodel(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile = models.ImageField(upload_to='profile/')
    bio     = models.TextField(blank=True, null=True) 


class Post(models.Model):
 
    MEDIA_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
    ]
 
    user       = models.ForeignKey(User, on_delete=models.CASCADE)
    title      = models.CharField(max_length=50) 
    post       = models.FileField(upload_to='post/')
 
    media_type = models.CharField(
        max_length=10,
        choices=MEDIA_CHOICES,
        default='image'
    )
 
    created_at = models.DateTimeField(auto_now_add=True)
    
    

class Likes(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)

class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following_users')
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')

class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
# Add to bottom of your models.py

class FriendRequest(models.Model):

    STATUS_CHOICES = [
        ('pending',  'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    ]

    sender     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_requests')
    receiver   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_requests')
    status     = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sender', 'receiver')

    def __str__(self):
        return f"{self.sender.username} → {self.receiver.username} ({self.status})"



# =========================================
# REEL
# =========================================

class Reel(models.Model):
    user       = models.ForeignKey('User', on_delete=models.CASCADE, related_name='reels')
    title      = models.CharField(max_length=255)
    media      = models.FileField(upload_to='reels/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} — {self.title}"


# =========================================
# REEL LIKE
# =========================================

class ReelLike(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE)
    reel = models.ForeignKey(
        Reel,
        on_delete=models.CASCADE,
        related_name='likes',
    )

    class Meta:
        unique_together = ('user', 'reel')   # one like per user per reel

    def __str__(self):
        return f"{self.user.username} liked reel #{self.reel.id}"


# =========================================
# REEL COMMENT
# =========================================

class ReelComment(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE)
    reel = models.ForeignKey(
        Reel,
        on_delete=models.CASCADE,
        related_name='comments',
    )
    text       = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} on reel #{self.reel.id}: {self.text[:30]}"


class PostView(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE)
    post       = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='views')
    created_at = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        unique_together = ('user', 'post')  # ✅ ஒரு user ஒரு post-ஐ ஒரே ஒரு முறை மட்டும்
 
    def __str__(self):
        return f"{self.user.username} viewed post #{self.post.id}"
 