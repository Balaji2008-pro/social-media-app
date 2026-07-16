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
 
 
 # =========================================
# FCM TOKEN (Push Notification)
# =========================================

class FCMToken(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fcm_tokens')
    token      = models.CharField(max_length=255, unique=True)
    device_id  = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.token[:20]}..."
    
    
# =========================================
# POLITICS — PARTY SYSTEM
# =========================================

class Party(models.Model):
    creator      = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_parties')
    party_name   = models.CharField(max_length=100)
    leader_name  = models.CharField(max_length=100)
    symbol       = models.ImageField(upload_to='party_symbols/')
    description  = models.TextField(blank=True, null=True)
    district     = models.CharField(max_length=50, blank=True, null=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.party_name} (Leader: {self.leader_name})"


class PartyMembership(models.Model):

    ROLE_CHOICES = [
        ('member', 'Member'),
        ('secretary', 'Secretary'),
        ('vice_president', 'Vice President'),
    ]

    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='party_membership')
    party      = models.ForeignKey(Party, on_delete=models.CASCADE, related_name='members')
    role       = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    joined_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} joined {self.party.party_name} as {self.role}"
    
    
    
class PartyAnnouncement(models.Model):
    party      = models.ForeignKey(Party, on_delete=models.CASCADE, related_name='announcements')
    author     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='party_announcements')
    content    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.party.party_name}: {self.content[:30]}"
    
    
    
# =========================================
# RECSYS MODELS — உங்க models.py கடைசில add பண்ணவும்
# =========================================



# ✅ 1) REEL VIEW — watch tracking (like இல்லனாலும் view = weak signal)
class ReelView(models.Model):
    user        = models.ForeignKey(User, on_delete=models.CASCADE)
    reel        = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name='views')
    watch_ratio = models.FloatField(default=0.0)   # 0.0 to 1.0 — எவ்வளவு % பாத்தாங்க
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'reel')   # ஒரு user ஒரு reel-க்கு ஒரு record மட்டும் (update ஆகும்)

    def __str__(self):
        return f"{self.user.username} watched reel #{self.reel.id} ({self.watch_ratio*100:.0f}%)"


# ✅ 2) PRECOMPUTED RECOMMENDATIONS — training script இதை fill பண்ணும்
#     reelhandler இதை படிச்சு serve பண்ணும் (real-time-ல model run பண்ண வேண்டாம்)
class ReelRecommendation(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reel_recommendations')
    reel       = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name='recommended_to')
    score      = models.FloatField()
    rank       = models.IntegerField()   # 1 = top recommendation
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'reel')
        indexes = [
            models.Index(fields=['user', 'rank']),
        ]
        ordering = ['rank']

    def __str__(self):
        return f"{self.user.username} <- reel #{self.reel.id} (score={self.score:.3f}, rank={self.rank})"