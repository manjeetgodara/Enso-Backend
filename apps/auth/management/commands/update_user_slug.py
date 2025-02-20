from django.core.management.base import BaseCommand
from auth.models import Users

class Command(BaseCommand):
    help = 'Update slug field for existing records in Users'

    def handle(self, *args, **kwargs):
        for instance in Users.objects.all():
            if not instance.slug:
                user_name = instance.name

                name_parts = [part.strip() for part in user_name.split(' ')]
                
                # Check if there are at least two parts
                slug = ''
                if len(name_parts) >= 2:
                    slug = (name_parts[0][:1]+name_parts[1][:1]).upper()
                else:
                    slug = user_name[:2].upper()
            
                instance.slug = slug
                instance.save()
                self.stdout.write(self.style.SUCCESS(f'Updated {instance.name} with slug {instance.slug}'))
