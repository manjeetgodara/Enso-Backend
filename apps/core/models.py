from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone
from simple_history.models import HistoricalRecords
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

class Category(models.Model):
    c_types = (("cat", "Category"), ("subcat", "Sub Category"))

    name = models.CharField(max_length=200, unique=True)
    c_type = models.CharField(max_length=200, choices=c_types)  # is either category or subcategory
    parent = models.ForeignKey("self",null=True,blank=True,related_name="child_categories",on_delete=models.CASCADE,)

    icon = models.ImageField(blank = True)

    def __str__(self):
        return str(self.name)

    class Meta:
        verbose_name_plural = "Categories"
 

@receiver(pre_save, sender=Category)
def category_pre_save_handler(sender, instance, **kwargs):
    pass


@receiver(post_save, sender=Category)
def category_post_save_handler(sender, instance, created, **kwargs):

    if created:
        print(f'Category instance {instance.id} has been created!')
    else:
        print(f'Category instance {instance.id} has been updated!')


class Organization(models.Model):
    SIZE_CHOICES = [
        (1, "1-5 employees"),
        (2, "5-10 employees"),
        (3, "10-20 employees"),
        (4, "20+ employees"),
    ]
    name = models.CharField(max_length=200, unique=True)
    email = models.EmailField(blank=True)
    number = models.CharField(max_length=20, blank=True)
    address_line_1 = models.TextField(blank=True)
    address_line_2 = models.TextField(blank=True)
    city = models.CharField(max_length=200, blank=True)
    country = models.CharField(max_length=200, blank=True)
    pin_code = models.CharField(max_length=100, blank=True)

    company_size = models.IntegerField(choices=SIZE_CHOICES, default=1)   

    cin = models.CharField(max_length=30, blank=True)
    ac_no = models.CharField(max_length=400, blank=True)
    bank = models.CharField(max_length=200, blank=True)
    gst = models.CharField(max_length=200, blank=True)
    igst = models.CharField(max_length=200, blank=True)
    branch = models.CharField(max_length=200, blank=True)
    upi = models.CharField(max_length=50, blank = True)

    categories = models.ManyToManyField(
        to=Category, blank=True, related_name="organization_categories"
    )

    website_url = models.CharField(max_length=200, blank=True)
    org_description = models.TextField(blank=True)
    background_img_url = models.TextField(blank=True)
    company_logo_url = models.TextField(blank=True)

    use_linkBiz_for = ArrayField(models.IntegerField(), blank=True, null=True)

    is_guided_tour_completed = models.BooleanField(default=False)
    guided_tour_current_step = models.IntegerField(default=1)
    is_workflow_tour_completed = models.BooleanField(default=False)

    def __str__(self):
        return str(self.name)

            
    @property
    def lead_received_count(self):
        return self.shared_with.all().count()
    
    @property
    def lead_shared_count(self):
        user_list = self.users_set.all()
        count = 0
        for user in user_list:
            count +=user.lead_shared_by.all().count()
        
        return count
    
    @property
    def connections_count(self):
        return (self.friends.filter(accepted=True).count() + self.request_sent.filter(accepted=True).count())

@receiver(pre_save, sender=Organization)
def organization_pre_save_handler(sender, instance, **kwargs):
    pass


@receiver(post_save, sender=Organization)
def organization_post_save_handler(sender, instance, created, **kwargs):
    if created:
        print(f'Organization instance {instance.id} has been created!')
    else:
        print(f'Organization instance {instance.id} has been updated!')


def upload_to_directory(instance, filename):
    lead_id = instance.lead_id if instance.lead_id else "unknown"
    return f'uploads/lead_{lead_id}/{filename}'




pre_save.connect(category_pre_save_handler, sender=Category)
post_save.connect(category_post_save_handler, sender=Category)
pre_save.connect(organization_pre_save_handler, sender=Organization)
post_save.connect(organization_post_save_handler, sender=Organization)








