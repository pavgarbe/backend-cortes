from django.contrib import admin
from .models import Corte, Pausa, Conteo, Configuracion

admin.site.register(Corte)
admin.site.register(Pausa)
admin.site.register(Conteo)
admin.site.register(Configuracion)
