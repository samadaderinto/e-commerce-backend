from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractUser
# Create your models here.


class UserManager(BaseUserManager):

    def create_user(self, email=None, password=None, **extra_fields):
        """
        Create and save a user with the given email and password.
        """
        if not email:
            raise ValueError("Email Address Is Needed")
        if not password:
            raise ValueError("Password Must Be Provided")

        emailnew = self.normalize_email(email)
        user = self.model(username=emailnew, email=emailnew, **extra_fields)

        user.set_password(password)

        user.save(using=self._db)

        return user

    def create_superuser(self, email=None, password=None, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)

    def create_staffuser(self, email=None, password=None, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("staffuser must have is_staff=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    firstname = models.CharField(max_length=30)
    lastname = models.CharField(max_length=30)
    gender = models.CharField(max_length=30)
    email = models.EmailField(unique=True)
    # phone1 = PhoneNumberField(region="US")
    password = models.CharField(max_length=90)
    # phone2 = PhoneNumberField(region="US", null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['firstname', 'lastname', 'phone1', 'password']

    objects = UserManager()
    
    