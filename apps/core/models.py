from django.db import models

TIPOS = (
    ('Grasa en carne', 'Grasa en carne'),
    ('Hueso en carne', 'Hueso en carne'),
    ('Piezas Vendibles', 'Piezas Vendibles')
)

class Corte(models.Model):
    cantidad_canales = models.IntegerField()
    horas_jornada = models.FloatField()
    canales_hora = models.FloatField()
    tiempo_entre_canales = models.FloatField()
    grasa_carne = models.FloatField()
    hueso_carne = models.FloatField()
    piezas_vendibles = models.FloatField()
    tiempo_muerto = models.IntegerField()
    inicio = models.DateTimeField(blank=True, null=True)
    fin = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f'{self.cantidad_canales} - {self.horas_jornada} - {self.canales_hora} - {self.tiempo_entre_canales} - {self.inicio} - {self.fin}'

class Pausa(models.Model):
    corte = models.ForeignKey(Corte, on_delete=models.CASCADE)
    inicio_pausa = models.DateTimeField(auto_now_add=True)
    fin_pausa = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f'{self.corte} - {self.inicio_pausa} - {self.fin_pausa}'

class Conteo(models.Model):
    corte = models.ForeignKey(Corte, on_delete=models.CASCADE)
    hora = models.DateTimeField(auto_now_add=True)
    cantidad = models.FloatField()

    def __str__(self):
        return f'{self.corte} - {self.hora} - {self.cantidad}'

class Configuracion(models.Model):
    tipo = models.CharField(max_length=50, choices=TIPOS)
    verde = models.FloatField(max_length=50)
    amarillo = models.FloatField(max_length=50)
    rojo = models.FloatField(max_length=50)

    def __str__(self):
        return f'{self.tipo} - {self.verde} - {self.amarillo} - {self.rojo}'