from django.db import models
from django.contrib.auth.models import AbstractBaseUser,PermissionsMixin,BaseUserManager
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission
from core.models import Organization
from simple_history.models import HistoricalRecords
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
import binascii,os
# Create your models here.
# should it be abstract user?

class UserManager(BaseUserManager):

    def create_user(self, email, name, password=None):
        """
        Creates and saves a User with the given email and password.
        """
        if not email:
            raise ValueError("User must have an email address")
        user = self.model(email=self.normalize_email(email), name=name)
        user.set_password(password)
        user.save(using=self._db)
        return user
    def create_superuser(self, email, name, password=None):
        """
        Creates and saves a SuperUser with the given email and password.
        """
        if not email:
            raise ValueError("SuperUser must have an email address")
        user = self.create_user(self.normalize_email(email), name, password=password)
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.save(using=self._db)
        return user
    def get_by_natural_key(self, email_):
        return self.get(email=email_)


class Users(AbstractBaseUser,PermissionsMixin):
    USERNAME_FIELD = "email"
    # EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["name"]
    MALE = 'MALE'
    FEMALE = 'FEMALE'
    OTHER = 'OTHER'
    GENDER_CHOICES = [
        (MALE, 'Male'),
        (FEMALE, 'Female'),
        (OTHER, 'Other'),
    ]
    ROLE_CHOICES = [
        ('SUPER ADMIN', 'Super Admin'),
        ('ADMIN', 'Admin'),
        ('MANAGER', 'Manager'),
        ('EXECUTIVE', 'Executive'),
    ]

    name=models.CharField(max_length=255,null=True,blank=True)
    mobile=models.CharField(max_length=10,null=False,blank=False)
    email=models.EmailField(max_length=255,unique=True)
    gender=models.CharField(max_length=6,choices=GENDER_CHOICES,null=True)
    role = models.CharField(max_length=50,choices=ROLE_CHOICES, null=True, blank=True)
    is_active=models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    profile_pic = models.ImageField(upload_to='user/profile_pic' , max_length=255, null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, default=None, null=True)
    history = HistoricalRecords()
    objects= UserManager()
    fcm_token = models.CharField(max_length=1000, blank=True, null=True)
    slug=models.CharField(max_length=5, null=True, blank=True)

    def __str__(self):
        return "{0}-{1}".format(self.name, self.id)
    

    @property
    def is_authenticated(self):
        return True
    
    class Meta:
        managed = True
        verbose_name_plural = "Users"
        db_table = "users"


@receiver(pre_save, sender=Users)
def users_pre_save_handler(sender, instance, **kwargs):

    print(f'Users instance {instance.id} about to be saved!')

    user_name = instance.name

    name_parts = [part.strip() for part in user_name.split(' ')]
    
    # Check if there are at least two parts
    slug = ''
    if len(name_parts) >= 2:
        slug = (name_parts[0][:1]+name_parts[1][:1]).upper()
    else:
        slug = user_name[:2].upper()

    # print('slug:', slug)
    instance.slug = slug


@receiver(post_save, sender=Users)
def users_post_save_handler(sender, instance, created, **kwargs):

    if created:
        print(f'Users instance {instance.id} has been created!')
    else:
        print(f'Users instance {instance.id} has been updated!')

    groups = instance.groups.all()
    # print('groups:', groups)
    cce_group_exists = any(group.name == "CALL_CENTER_EXECUTIVE" for group in groups)
    # print('cce_group_exists:', cce_group_exists)
    if cce_group_exists:
        from firebase_admin import db, firestore
        from django.conf import settings

        fr_data={
            "show_lead_form":False,
            "data":None
            }

        db = firestore.client(app=settings.FIREBASE_APPS['mcube'])
        fr_data_ref = db.collection('mcubeLeadForm').document(str(instance.id)).set(fr_data)


pre_save.connect(users_pre_save_handler, sender=Users)
post_save.connect(users_post_save_handler, sender=Users)

class OTPSession(models.Model):
    otp=models.CharField(max_length=6)
    session_id=models.UUIDField()
    expires_at=models.DateTimeField()
    identifier =models.CharField(max_length=255)
    history = HistoricalRecords()

    def __str__(self) -> str:
        return self.identifier


@receiver(pre_save, sender=OTPSession)
def otpsession_pre_save_handler(sender, instance, **kwargs):

    print(f'OTPSession instance {instance.id} about to be saved!')


@receiver(post_save, sender=OTPSession)
def otpsession_post_save_handler(sender, instance, created, **kwargs):

    if created:
        print(f'OTPSession instance {instance.id} has been created!')
    else:
        print(f'OTPSession instance {instance.id} has been updated!')


pre_save.connect(otpsession_pre_save_handler, sender=OTPSession)
post_save.connect(otpsession_post_save_handler, sender=OTPSession)