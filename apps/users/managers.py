from django.db import models
from django.contrib.auth.models import BaseUserManager


class UserManager(BaseUserManager, models.Manager):
    
    def _create_user(self, nombres, apellidos, email, rol, password, is_staff, is_superuser, is_active, **extra_fields):
        user = self.model(
            nombres=nombres,
            apellidos=apellidos,
            rol=rol,
            email=email,
            is_staff=is_staff,
            is_superuser=is_superuser,
            is_active=is_active,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self.db)

        return user
    
    def _create_superuser(self, email, password, is_staff, is_superuser, is_active, **extra_fields):
        user = self.model(
            email=email,
            is_staff=is_staff,
            is_superuser=is_superuser,
            is_active=is_active,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self.db)

        return user

    def create_user(self, nombres, apellidos, email, rol, password, **extra_fields):
        return self._create_user(nombres, apellidos, email, rol, password, True, False, True, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        return self._create_superuser(email, password, True, True, True, **extra_fields)