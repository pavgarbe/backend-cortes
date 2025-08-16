from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from .managers import UserManager

Roles = (
    ('Administrador', 'Administrador'),
    ('Usuario', 'Usuario'),
)

class User(AbstractBaseUser, PermissionsMixin):
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    rol = models.CharField(max_length=100, choices=Roles)
    email = models.EmailField(max_length=100, unique=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.id } - {self.nombres} {self.apellidos}'
    
    objects = UserManager()

    USERNAME_FIELD = "email"

    class Meta:
        ordering = ['-id']
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'