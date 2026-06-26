from django.core.management.base import BaseCommand
from api.models import Posting  

class Command(BaseCommand):
    help = "This command inserts sample post data"

    def handle(self, *args, **options):
        
        img_url = [
            "https://picsum.photos/id/1/800/400",
            "https://picsum.photos/id/2/800/400",
            "https://picsum.photos/id/3/800/400",
            "https://picsum.photos/id/4/800/400",
            "https://picsum.photos/id/5/800/400",
            
        ]
       
        for img in img_url:
            Posting.objects.create(post=img)

        self.stdout.write(self.style.SUCCESS("✅ Successfully inserted sample posts"))

