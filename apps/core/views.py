from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from gpiozero import LED, Button
import os
from django.conf import settings
from .models import Corte, Pausa, Conteo, Configuracion
from datetime import datetime
from datetime import timedelta
from .hardware import HardwareJornada
from django.utils import timezone

import time


# --- Inicialización de hardware Raspberry Pi ---
def inicializar_hardware():
    MODE = getattr(settings, "MODE", os.environ.get("MODE", "production"))
    if MODE == "production":
        from gpiozero.pins.lgpio import LGPIOFactory
        factory = LGPIOFactory(chip=0)
        ledgreen = LED(17, pin_factory=factory)
        ledyellow = LED(23, pin_factory=factory)
        ledred = LED(26, pin_factory=factory)
        siren = LED(24, pin_factory=factory)
        input_btn = Button(27, pin_factory=factory)
        hardware = HardwareJornada(factory=factory)
    else:
        factory = None
        ledgreen = None
        ledyellow = None
        ledred = None
        siren = None
        input_btn = None
        hardware = None
    return {
        "factory": factory,
        "ledgreen": ledgreen,
        "ledyellow": ledyellow,
        "ledred": ledred,
        "siren": siren,
        "input_btn": input_btn,
        "hardware": hardware
    }

# Instancia global de hardware
hw = inicializar_hardware()
ledgreen = hw["ledgreen"]
ledyellow = hw["ledyellow"]
ledred = hw["ledred"]
siren = hw["siren"]
input_btn = hw["input_btn"]
hardware = hw["hardware"]

def get_estado_actual():
    corte = Corte.objects.last()
    if not corte or not corte.inicio or corte.fin:
        return "stopped"
    pausa = Pausa.objects.filter(corte=corte).last()
    if pausa and pausa.fin_pausa is None:
        return "paused"
    return "running"


_ultimo_estado_luces = None
def actualizar_luces_estado():
    global _ultimo_estado_luces
    if hardware:
        estado_actual = get_estado_actual()
        if estado_actual != _ultimo_estado_luces:
            hardware.update_luces(estado_actual)
            _ultimo_estado_luces = estado_actual

# --- Helpers para transiciones de estado (unifican virtual/físico) ---
def accion_inicio_o_reanudar():
    """
    - Si no hay inicio: inicia jornada (sólo debería ocurrir desde pantalla)
    - Si ya había inicio y hay pausa abierta: cierra pausa (reanudar)
    """
    corte = Corte.objects.last()
    if not corte:
        return False, 'No hay cortes'
    if not corte.inicio:
        # Inicio nuevo (sólo debería venir de botón virtual)
        corte.inicio = datetime.now()
        corte.save()
        actualizar_luces_estado()
        return True, 'Corte Iniciado'
    else:
        # Reanudar si hay pausa abierta
        pausa = Pausa.objects.filter(corte=corte, fin_pausa__isnull=True).last()
        if pausa:
            pausa.fin_pausa = datetime.now()
            pausa.save()
            actualizar_luces_estado()
            return True, 'Pausa finalizada'
        return False, 'Nada que reanudar'

def accion_pausar():
    corte = Corte.objects.last()
    if not corte:
        return False, 'No hay cortes'
    if corte.inicio and not corte.fin:
        # Crea pausa nueva sólo si no hay una ya abierta
        pausa_abierta = Pausa.objects.filter(corte=corte, fin_pausa__isnull=True).exists()
        if not pausa_abierta:
            Pausa.objects.create(corte=corte)
            actualizar_luces_estado()
            return True, 'Pausa Iniciada'
        return False, 'Ya existe una pausa abierta'
    return False, 'Corte no iniciado'

def accion_finalizar():
    corte = Corte.objects.last()
    if not corte:
        return False, 'No hay cortes'
    if corte.inicio and not corte.fin:
        corte.fin = datetime.now()
        corte.save()
        actualizar_luces_estado()
        return True, 'Corte finalizado'
    return False, 'Corte no finalizado'


# --- Conectar callbacks físicos si hay hardware ---
def conectar_callbacks_hardware():
    if not hardware:
        return
    def _on_start_fisico():
        accion_inicio_o_reanudar()
    def _on_pause_fisico():
        accion_pausar()
    def _on_stop_fisico():
        accion_finalizar()
    hardware.on_start = _on_start_fisico
    hardware.on_pause = _on_pause_fisico
    hardware.on_stop  = _on_stop_fisico

conectar_callbacks_hardware()


# --- Inicialización de sirena y botón físico ---
if siren:
    siren.on()

def input_pressed():
    if input_btn:
        print('Input pressed')
        if (corte := Corte.objects.last()) and corte.inicio and not corte.fin:
            Conteo.objects.create(corte=corte, cantidad=0.5)
        time.sleep(1)  # Evita doble conteo rápido

if input_btn:
    input_btn.when_pressed = input_pressed

class LedOnYellow(APIView):

    permission_classes = [AllowAny]

    def get(self, request, format=None):
        if ledyellow:
            if ledyellow.value == 1:
                ledyellow.off()
            else:
                if ledgreen and ledgreen.value == 1:
                    ledgreen.off()
                if ledred and ledred.value == 1:
                    ledred.off()
                ledyellow.on()
            return Response({'OK': 'Led Encendido'} if ledyellow.value == 1 else {'OK': 'Led Apagado'}, status=status.HTTP_200_OK)
        return Response({'ERROR': 'No hardware'}, status=status.HTTP_400_BAD_REQUEST)

class LedOnGreen(APIView):

    permission_classes = [AllowAny]

    def get(self, request, format=None):
        if ledgreen:
            if ledgreen.value == 1:
                ledgreen.off()
            else:
                if ledyellow and ledyellow.value == 1:
                    ledyellow.off()
                if ledred and ledred.value == 1:
                    ledred.off()
                ledgreen.on()
            return Response({'OK': 'Led Encendido'} if ledgreen.value == 1 else {'OK': 'Led Apagado'}, status=status.HTTP_200_OK)
        return Response({'ERROR': 'No hardware'}, status=status.HTTP_400_BAD_REQUEST)

class LedOnRed(APIView):

    permission_classes = [AllowAny]

    def get(self, request, format=None):
        if ledred:
            if ledred.value == 1:
                ledred.off()
            else:
                if ledyellow and ledyellow.value == 1:
                    ledyellow.off()
                if ledgreen and ledgreen.value == 1:
                    ledgreen.off()
                ledred.on()
            return Response({'OK': 'Led Encendido'} if ledred.value == 1 else {'OK': 'Led Apagado'}, status=status.HTTP_200_OK)
        return Response({'ERROR': 'No hardware'}, status=status.HTTP_400_BAD_REQUEST)

class SirenOn(APIView):

    permission_classes = [AllowAny]

    def get(self, request, format=None):
        if siren:
            siren.off()
            time.sleep(2)
            siren.on()
            time.sleep(1)
            siren.off()
            time.sleep(2)
            siren.on()
            return Response({'OK': 'Sirena Encendida'}, status=status.HTTP_200_OK)
        return Response({'ERROR': 'No hardware'}, status=status.HTTP_400_BAD_REQUEST)

class SirenOff(APIView):

    permission_classes = [AllowAny]

    def get(self, request, format=None):
        siren.on()
        return Response({'OK': 'Sirena Apagada'}, status=status.HTTP_200_OK)

class CortesView(APIView):

    permission_classes = [AllowAny]

    def post(self, request, format=None):
        data = request.data
        Corte.objects.create(
            cantidad_canales=data['cantidad_canales'],
            horas_jornada=data['horas_jornada'],
            canales_hora=data['canales_hora'],
            tiempo_entre_canales=data['tiempo_canal'],
            grasa_carne=data['grasa_carne'],
            hueso_carne=data['hueso_carne'],
            piezas_vendibles=data['piezas_vendibles'],
            tiempo_muerto=data['tiempo_muerto'],
        )

        return Response({'message': 'Corte creado correctamente'}, status=status.HTTP_200_OK)

    def get(self, request, format=None):
        cortes = Corte.objects.all()
        list = []
        for corte in cortes:
            list.append({
                'id': corte.id,
                'cantidad_canales': corte.cantidad_canales,
                'horas_jornada': corte.horas_jornada,
                'canales_hora': corte.canales_hora,
                'tiempo_entre_canales': corte.tiempo_entre_canales,
                'grasa_carne': corte.grasa_carne,
                'hueso_carne': corte.hueso_carne,
                'piezas_vendibles': corte.piezas_vendibles,
                'tiempo_muerto': corte.tiempo_muerto,
                'inicio': corte.inicio,
                'fin': corte.fin
            })
        return Response(list, status=status.HTTP_200_OK)

class StatusCorte(APIView):

    permission_classes = [AllowAny]

    def get(self, request):
        corte = Corte.objects.last()
        if corte:
            pausa = Pausa.objects.filter(corte=corte).last()
            if pausa:
                pausa_actual = False if pausa.fin_pausa else True
                response = {
                    'status': False if corte.fin else True,
                    'inicio': True if corte.inicio else False,
                    'fecha_inicio': corte.inicio,
                    'cantidad_canales': corte.cantidad_canales,
                    'horas_jornada': corte.horas_jornada,
                    'canales_hora': corte.canales_hora,
                    'tiempo_entre_canales': corte.tiempo_entre_canales,
                    'grasa_carne': corte.grasa_carne,
                    'hueso_carne': corte.hueso_carne,
                    'piezas_vendibles': corte.piezas_vendibles,
                    'tiempo_muerto': corte.tiempo_muerto,
                    'pausa': True if pausa_actual else False,
                }
                return Response(response, status=status.HTTP_200_OK)
            else:
                response = {
                    'status': False if corte.fin else True,
                    'inicio': True if corte.inicio else False,
                    'fecha_inicio': corte.inicio,
                    'cantidad_canales': corte.cantidad_canales,
                    'horas_jornada': corte.horas_jornada,
                    'canales_hora': corte.canales_hora,
                    'grasa_carne': corte.grasa_carne,
                    'hueso_carne': corte.hueso_carne,
                    'piezas_vendibles': corte.piezas_vendibles,
                    'tiempo_muerto': corte.tiempo_muerto,
                    'tiempo_entre_canales': corte.tiempo_entre_canales,
                    'pausa': False,
                }
                return Response(response, status=status.HTTP_200_OK)
        else:
            return Response({'status': False}, status=status.HTTP_200_OK)

class InicioView(APIView):

    permission_classes = [AllowAny]

    def get(self, request):
        corte = Corte.objects.last()
        if corte:
            if corte.inicio:
                pausa = Pausa.objects.last()
                if pausa:
                    pausa.fin_pausa = datetime.now()
                    pausa.save()

                    # NUEVO: reflejar estado (debería quedar "running")
                    actualizar_luces_estado()

                return Response({'message': 'Pausa finalizada'}, status=status.HTTP_200_OK)
            else:
                corte.inicio = datetime.now()
                corte.save()

                # NUEVO: reflejar estado (debería quedar "running")
                actualizar_luces_estado()

                return Response({'message': 'Corte Iniciado'}, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'No hay cortes'}, status=status.HTTP_400_BAD_REQUEST)
                
class PausaView(APIView):

    permission_classes = [AllowAny]

    def get(self, request):
        corte = Corte.objects.last()
        if corte:
            if corte.inicio:
                Pausa.objects.create(corte=corte)

                # NUEVO: reflejar estado (debería quedar "paused")
                actualizar_luces_estado()

                return Response({'message': 'Pausa Iniciada'}, status=status.HTTP_200_OK)
            else:
                return Response({'message': 'Corte no iniciado'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({'message': 'No hay cortes'}, status=status.HTTP_400_BAD_REQUEST)
            
class FinView(APIView):

    permission_classes = [AllowAny]

    def get(self, request):
        corte = Corte.objects.last()
        if corte:
            if corte.inicio:
                corte.fin = datetime.now()
                corte.save()

                # <<< NUEVO: reflejar estado en las 3 lámparas físicas >>>
                actualizar_luces_estado()

                return Response({'message':'Corte finalizado'}, status=status.HTTP_200_OK)
            else:
                return Response({'message':'Corte no finalizado'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({'message':'No hay cortes'}, status=status.HTTP_400_BAD_REQUEST)


class MonitorView(APIView):

    permission_classes = [AllowAny]

    def get(self, request):
        corte = Corte.objects.last()
        if corte:
            if corte.inicio and not corte.fin:
                conteos = Conteo.objects.filter(corte=corte)
                pausas = Pausa.objects.filter(corte=corte)
                configuraciones = Configuracion.objects.all()

                grasa_carne_color = 'Verde' if corte.grasa_carne < configuraciones[0].verde else 'Amarillo' if corte.grasa_carne < configuraciones[0].amarillo else 'Rojo'
                hueso_carne_color = 'Verde' if corte.hueso_carne < configuraciones[1].verde else 'Amarillo' if corte.hueso_carne < configuraciones[1].amarillo else 'Rojo'
                piezas_vendibles_color = 'Verde' if corte.piezas_vendibles >= configuraciones[2].verde else 'Amarillo' if corte.piezas_vendibles < configuraciones[2].verde and corte.piezas_vendibles >= configuraciones[2].amarillo else 'Rojo'

                list = []
                list2 = []
                list3 = []
                for conteo in conteos:
                    list.append({
                        'hora': conteo.hora,
                        'cantidad': conteo.cantidad
                    })
                for pausa in pausas:
                    list2.append({
                        'inicio_pausa': pausa.inicio_pausa,
                        'fin_pausa': pausa.fin_pausa,
                        'duracion': (pausa.fin_pausa - pausa.inicio_pausa) if pausa.fin_pausa and pausa.inicio_pausa else None
                    })
                for config in configuraciones:
                    list3.append({
                        'verde': config.verde,
                        'amarillo': config.amarillo,
                        'rojo': config.rojo
                    })
                corte_object = {
                    'cantidad_canales': corte.cantidad_canales,
                    'horas_jornada': corte.horas_jornada,
                    'canales_hora': corte.canales_hora,
                    'tiempo_entre_canales': corte.tiempo_entre_canales,
                    'grasa_carne': corte.grasa_carne,
                    'hueso_carne': corte.hueso_carne,
                    'piezas_vendibles': corte.piezas_vendibles,
                    'tiempo_muerto': corte.tiempo_muerto,
                    'inicio': corte.inicio,
                    'conteos': list,
                    'pausas': list2,
                    'grasa_carne_config': list3[0] if configuraciones else None,
                    'hueso_carne_config': list3[1] if configuraciones else None,
                    'piezas_vendibles_config': list3[2] if configuraciones else None,
                    'grasa_carne_color': grasa_carne_color,
                    'hueso_carne_color': hueso_carne_color,
                    'piezas_vendibles_color': piezas_vendibles_color,
                }
                return Response(corte_object, status=status.HTTP_200_OK)
            else:
                return Response({'message':'Corte no iniciado'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({'message':'No hay cortes'}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        corte = Corte.objects.last()

        if corte:
            if corte.inicio and not corte.fin:
                conteos = Conteo.objects.filter(corte=corte)
                if conteos:
                    count = 0
                    for conteo in conteos:
                        count += 1
                    return Response({'conteo': count}, status=status.HTTP_200_OK)
                else:
                    return Response({'conteo': 0}, status=status.HTTP_200_OK)
            else:
                return Response({'message':'Corte no iniciado'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({'message':'No hay cortes'}, status=status.HTTP_400_BAD_REQUEST)

class LastFiveCortesView(APIView):

    permission_classes = [AllowAny]

    def get(self, request):
        cortes = Corte.objects.all().order_by('-id')[:5]
        configuraciones = Configuracion.objects.all()
        list = []
        for corte in cortes:
            conteos = Conteo.objects.filter(corte=corte)
            pausa = Pausa.objects.filter(corte=corte)
            canales_hora = (Pausa.objects.filter(corte=corte).count()/2) / corte.horas_jornada
            conteo = 0
            pausas = []

            grasa_carne_color = 'Verde' if corte.grasa_carne < configuraciones[0].verde else 'Amarillo' if corte.grasa_carne < configuraciones[0].amarillo else 'Rojo'
            hueso_carne_color = 'Verde' if corte.hueso_carne < configuraciones[1].verde else 'Amarillo' if corte.hueso_carne < configuraciones[1].amarillo else 'Rojo'
            piezas_vendibles_color = 'Verde' if corte.piezas_vendibles >= configuraciones[2].verde else 'Amarillo' if corte.piezas_vendibles < configuraciones[2].verde and corte.piezas_vendibles >= configuraciones[2].amarillo else 'Rojo'

            for c in conteos:
                conteo += c.cantidad
            for p in pausa:
                pausas.append({
                    'inicio_pausa': p.inicio_pausa,
                    'fin_pausa': p.fin_pausa
                })
            tiempo_m = None
            for ps in pausas:
                if ps['fin_pausa']:
                    if not tiempo_m:
                        tiempo_m = ps['fin_pausa'] - ps['inicio_pausa']
                    tiempo_m += ps['fin_pausa'] - ps['inicio_pausa']

            list.append({
                'id': corte.id,
                'cantidad_canales': corte.cantidad_canales,
                'horas_jornada': corte.horas_jornada,
                'canales_hora': corte.canales_hora,
                'tiempo_entre_canales': corte.tiempo_entre_canales,
                'grasa_carne': corte.grasa_carne,
                'grasa_carne_color': grasa_carne_color,
                'hueso_carne': corte.hueso_carne,
                'hueso_carne_color': hueso_carne_color,
                'piezas_vendibles': corte.piezas_vendibles,
                'piezas_vendibles_color': piezas_vendibles_color,
                'tiempo_muerto_max': corte.tiempo_muerto,
                'tiempo_muerto': tiempo_m if tiempo_m else 0,
                'inicio': corte.inicio,
                'fin': corte.fin,
                'conteo': conteo,
                'pausas': pausas,
                'promedio_canales_hora': canales_hora,
            })
        return Response(list, status=status.HTTP_200_OK)

class CortesReportView(APIView):

    permission_classes = [AllowAny]

    def get(self, request):
        fecha_inicio = request.GET.get('fecha_inicio')
        fecha_fin = request.GET.get('fecha_fin')
        cortes = Corte.objects.filter(inicio__range=[datetime.strptime(fecha_inicio, '%Y-%m-%d'), datetime.strptime(fecha_fin, '%Y-%m-%d')])
        configuraciones = Configuracion.objects.all()

        list = []
        for corte in cortes:
            conteos = Conteo.objects.filter(corte=corte)
            pausa = Pausa.objects.filter(corte=corte)
            canales_hora = (Pausa.objects.filter(corte=corte).count()/2) / corte.horas_jornada
            conteo = 0
            pausas = []

            for c in conteos:
                conteo += c.cantidad
            for p in pausa:
                pausas.append({
                    'inicio_pausa': p.inicio_pausa,
                    'fin_pausa': p.fin_pausa
                })
            tiempo_m = None
            for ps in pausas:
                if ps['fin_pausa']:
                    if not tiempo_m:
                        tiempo_m = ps['fin_pausa'] - ps['inicio_pausa']
                    tiempo_m += ps['fin_pausa'] - ps['inicio_pausa']

            grasa_carne_color = 'Verde' if corte.grasa_carne < configuraciones[0].verde else 'Amarillo' if corte.grasa_carne < configuraciones[0].amarillo else 'Rojo'
            hueso_carne_color = 'Verde' if corte.hueso_carne < configuraciones[1].verde else 'Amarillo' if corte.hueso_carne < configuraciones[1].amarillo else 'Rojo'
            piezas_vendibles_color = 'Verde' if corte.piezas_vendibles >= configuraciones[2].verde else 'Amarillo' if corte.piezas_vendibles < configuraciones[2].verde and corte.piezas_vendibles >= configuraciones[2].amarillo else 'Rojo'

            list.append({
                'id': corte.id,
                'cantidad_canales': corte.cantidad_canales,
                'horas_jornada': corte.horas_jornada,
                'canales_hora': corte.canales_hora,
                'tiempo_entre_canales': corte.tiempo_entre_canales,
                'grasa_carne': corte.grasa_carne,
                'grasa_carne_color': grasa_carne_color,
                'hueso_carne': corte.hueso_carne,
                'hueso_carne_color': hueso_carne_color,
                'tiempo_muerto_max': corte.tiempo_muerto,
                'piezas_vendibles': corte.piezas_vendibles,
                'piezas_vendibles_color': piezas_vendibles_color,
                'tiempo_muerto': tiempo_m if tiempo_m else 0,
                'inicio': corte.inicio,
                'fin': corte.fin,
                'conteo': conteo,
                'pausas': pausas,
                'promedio_canales_hora': canales_hora,
            })
        return Response(list, status=status.HTTP_200_OK)

class ConfiguracionView(APIView):
    def get(self, request):
        configuracion = Configuracion.objects.all()
        list = []
        for config in configuracion:
            list.append({
                'tipo': config.tipo,
                'verde': config.verde,
                'amarillo': config.amarillo,
                'rojo': config.rojo
            })
        return Response(list, status=status.HTTP_200_OK)

    def put(self, request):
        data = request.data
        configuracion = Configuracion.objects.get(tipo=data['tipo'])
        configuracion.verde = data['verde']
        configuracion.amarillo = data['amarillo']
        configuracion.rojo = data['rojo']
        configuracion.save()
        return Response({'message': 'Configuracion actualizada'}, status=status.HTTP_200_OK)

class ReporteTopMayorView(APIView):

    permission_classes = [AllowAny]

    def get(self, request):
        rango_dias_atras = request.GET.get('rango')
        tipo = request.GET.get('tipo')
        configuraciones = Configuracion.objects.all()
        cortes = Corte.objects.filter(inicio__range=[datetime.now() - timedelta(days=int(rango_dias_atras)), datetime.now()])
        list = []

        if tipo == 'Canales Procesados':
            for corte in cortes:
                conteos = Conteo.objects.filter(corte=corte)
                pausa = Pausa.objects.filter(corte=corte)
                canales_hora = (Pausa.objects.filter(corte=corte).count()/2) / corte.horas_jornada
                conteo = 0
                pausas = []

                for c in conteos:
                    conteo += c.cantidad
                for p in pausa:
                    pausas.append({
                        'inicio_pausa': p.inicio_pausa,
                        'fin_pausa': p.fin_pausa
                    })
                tiempo_m = None
                for ps in pausas:
                    if ps['fin_pausa']:
                        if not tiempo_m:
                            tiempo_m = ps['fin_pausa'] - ps['inicio_pausa']
                        tiempo_m += ps['fin_pausa'] - ps['inicio_pausa']

                grasa_carne_color = 'Verde' if corte.grasa_carne < configuraciones[0].verde else 'Amarillo' if corte.grasa_carne < configuraciones[0].amarillo else 'Rojo'
                hueso_carne_color = 'Verde' if corte.hueso_carne < configuraciones[1].verde else 'Amarillo' if corte.hueso_carne < configuraciones[1].amarillo else 'Rojo'
                piezas_vendibles_color = 'Verde' if corte.piezas_vendibles >= configuraciones[2].verde else 'Amarillo' if corte.piezas_vendibles < configuraciones[2].verde and corte.piezas_vendibles >= configuraciones[2].amarillo else 'Rojo'

                list.append({
                    'id': corte.id,
                    'cantidad_canales': corte.cantidad_canales,
                    'horas_jornada': corte.horas_jornada,
                    'canales_hora': corte.canales_hora,
                    'tiempo_entre_canales': corte.tiempo_entre_canales,
                    'grasa_carne': corte.grasa_carne,
                    'grasa_carne_color': grasa_carne_color,
                    'hueso_carne': corte.hueso_carne,
                    'hueso_carne_color': hueso_carne_color,
                    'tiempo_muerto_max': corte.tiempo_muerto,
                    'piezas_vendibles': corte.piezas_vendibles,
                    'piezas_vendibles_color': piezas_vendibles_color,
                    'tiempo_muerto': tiempo_m if tiempo_m else 0,
                    'inicio': corte.inicio,
                    'fin': corte.fin,
                    'conteo': conteo,
                    'pausas': pausas,
                    'promedio_canales_hora': canales_hora,
                })
                lista = sorted(list, key=lambda x: x['conteo'], reverse=True)
            return Response(lista, status=status.HTTP_200_OK)

        elif tipo == 'Tiempo Muerto':
            for corte in cortes:
                conteos = Conteo.objects.filter(corte=corte)
                pausa = Pausa.objects.filter(corte=corte)
                canales_hora = (Pausa.objects.filter(corte=corte).count()/2) / corte.horas_jornada
                conteo = 0
                pausas = []

                for c in conteos:
                    conteo += c.cantidad
                for p in pausa:
                    pausas.append({
                        'inicio_pausa': p.inicio_pausa,
                        'fin_pausa': p.fin_pausa
                    })
                tiempo_m = None
                for ps in pausas:
                    if ps['fin_pausa']:
                        if not tiempo_m:
                            tiempo_m = ps['fin_pausa'] - ps['inicio_pausa']
                        tiempo_m += ps['fin_pausa'] - ps['inicio_pausa']

                grasa_carne_color = 'Verde' if corte.grasa_carne < configuraciones[0].verde else 'Amarillo' if corte.grasa_carne < configuraciones[0].amarillo else 'Rojo'
                hueso_carne_color = 'Verde' if corte.hueso_carne < configuraciones[1].verde else 'Amarillo' if corte.hueso_carne < configuraciones[1].amarillo else 'Rojo'
                piezas_vendibles_color = 'Verde' if corte.piezas_vendibles >= configuraciones[2].verde else 'Amarillo' if corte.piezas_vendibles < configuraciones[2].verde and corte.piezas_vendibles >= configuraciones[2].amarillo else 'Rojo'

                list.append({
                    'id': corte.id,
                    'cantidad_canales': corte.cantidad_canales,
                    'horas_jornada': corte.horas_jornada,
                    'canales_hora': corte.canales_hora,
                    'tiempo_entre_canales': corte.tiempo_entre_canales,
                    'grasa_carne': corte.grasa_carne,
                    'grasa_carne_color': grasa_carne_color,
                    'hueso_carne': corte.hueso_carne,
                    'hueso_carne_color': hueso_carne_color,
                    'tiempo_muerto_max': corte.tiempo_muerto,
                    'piezas_vendibles': corte.piezas_vendibles,
                    'piezas_vendibles_color': piezas_vendibles_color,
                    'tiempo_muerto': tiempo_m if tiempo_m else 0,
                    'inicio': corte.inicio,
                    'fin': corte.fin,
                    'conteo': conteo,
                    'pausas': pausas,
                    'promedio_canales_hora': canales_hora,
                })
                lista = sorted(list, key=lambda x: x['tiempo_muerto'], reverse=False)
            return Response(lista, status=status.HTTP_200_OK)
        elif tipo == 'Canales/Hora':
            for corte in cortes:
                conteos = Conteo.objects.filter(corte=corte)
                pausa = Pausa.objects.filter(corte=corte)
                canales_hora = (Pausa.objects.filter(corte=corte).count()/2) / corte.horas_jornada
                conteo = 0
                pausas = []

                for c in conteos:
                    conteo += c.cantidad
                for p in pausa:
                    pausas.append({
                        'inicio_pausa': p.inicio_pausa,
                        'fin_pausa': p.fin_pausa
                    })
                tiempo_m = None
                for ps in pausas:
                    if ps['fin_pausa']:
                        if not tiempo_m:
                            tiempo_m = ps['fin_pausa'] - ps['inicio_pausa']
                        tiempo_m += ps['fin_pausa'] - ps['inicio_pausa']

                grasa_carne_color = 'Verde' if corte.grasa_carne < configuraciones[0].verde else 'Amarillo' if corte.grasa_carne < configuraciones[0].amarillo else 'Rojo'
                hueso_carne_color = 'Verde' if corte.hueso_carne < configuraciones[1].verde else 'Amarillo' if corte.hueso_carne < configuraciones[1].amarillo else 'Rojo'
                piezas_vendibles_color = 'Verde' if corte.piezas_vendibles >= configuraciones[2].verde else 'Amarillo' if corte.piezas_vendibles < configuraciones[2].verde and corte.piezas_vendibles >= configuraciones[2].amarillo else 'Rojo'

                list.append({
                    'id': corte.id,
                    'cantidad_canales': corte.cantidad_canales,
                    'horas_jornada': corte.horas_jornada,
                    'canales_hora': corte.canales_hora,
                    'tiempo_entre_canales': corte.tiempo_entre_canales,
                    'grasa_carne': corte.grasa_carne,
                    'grasa_carne_color': grasa_carne_color,
                    'hueso_carne': corte.hueso_carne,
                    'hueso_carne_color': hueso_carne_color,
                    'tiempo_muerto_max': corte.tiempo_muerto,
                    'piezas_vendibles': corte.piezas_vendibles,
                    'piezas_vendibles_color': piezas_vendibles_color,
                    'tiempo_muerto': tiempo_m if tiempo_m else 0,
                    'inicio': corte.inicio,
                    'fin': corte.fin,
                    'conteo': conteo,
                    'pausas': pausas,
                    'promedio_canales_hora': canales_hora,
                })
                lista = sorted(list, key=lambda x: x['canales_hora'], reverse=True)
            return Response(lista, status=status.HTTP_200_OK)
        elif tipo == 'Grasa Carne':
            for corte in cortes:
                conteos = Conteo.objects.filter(corte=corte)
                pausa = Pausa.objects.filter(corte=corte)
                canales_hora = (Pausa.objects.filter(corte=corte).count()/2) / corte.horas_jornada
                conteo = 0
                pausas = []

                for c in conteos:
                    conteo += c.cantidad
                for p in pausa:
                    pausas.append({
                        'inicio_pausa': p.inicio_pausa,
                        'fin_pausa': p.fin_pausa
                    })
                tiempo_m = None
                for ps in pausas:
                    if ps['fin_pausa']:
                        if not tiempo_m:
                            tiempo_m = ps['fin_pausa'] - ps['inicio_pausa']
                        tiempo_m += ps['fin_pausa'] - ps['inicio_pausa']

                grasa_carne_color = 'Verde' if corte.grasa_carne < configuraciones[0].verde else 'Amarillo' if corte.grasa_carne < configuraciones[0].amarillo else 'Rojo'
                hueso_carne_color = 'Verde' if corte.hueso_carne < configuraciones[1].verde else 'Amarillo' if corte.hueso_carne < configuraciones[1].amarillo else 'Rojo'
                piezas_vendibles_color = 'Verde' if corte.piezas_vendibles >= configuraciones[2].verde else 'Amarillo' if corte.piezas_vendibles < configuraciones[2].verde and corte.piezas_vendibles >= configuraciones[2].amarillo else 'Rojo'

                list.append({
                    'id': corte.id,
                    'cantidad_canales': corte.cantidad_canales,
                    'horas_jornada': corte.horas_jornada,
                    'canales_hora': corte.canales_hora,
                    'tiempo_entre_canales': corte.tiempo_entre_canales,
                    'grasa_carne': corte.grasa_carne,
                    'grasa_carne_color': grasa_carne_color,
                    'hueso_carne': corte.hueso_carne,
                    'hueso_carne_color': hueso_carne_color,
                    'tiempo_muerto_max': corte.tiempo_muerto,
                    'piezas_vendibles': corte.piezas_vendibles,
                    'piezas_vendibles_color': piezas_vendibles_color,
                    'tiempo_muerto': tiempo_m if tiempo_m else 0,
                    'inicio': corte.inicio,
                    'fin': corte.fin,
                    'conteo': conteo,
                    'pausas': pausas,
                    'promedio_canales_hora': canales_hora,
                })
                lista = sorted(list, key=lambda x: x['grasa_carne'], reverse=False)
            return Response(lista, status=status.HTTP_200_OK)
        elif tipo == 'Hueso Carne':
            for corte in cortes:
                conteos = Conteo.objects.filter(corte=corte)
                pausa = Pausa.objects.filter(corte=corte)
                canales_hora = (Pausa.objects.filter(corte=corte).count()/2) / corte.horas_jornada
                conteo = 0
                pausas = []

                for c in conteos:
                    conteo += c.cantidad
                for p in pausa:
                    pausas.append({
                        'inicio_pausa': p.inicio_pausa,
                        'fin_pausa': p.fin_pausa
                    })
                tiempo_m = None
                for ps in pausas:
                    if ps['fin_pausa']:
                        if not tiempo_m:
                            tiempo_m = ps['fin_pausa'] - ps['inicio_pausa']
                        tiempo_m += ps['fin_pausa'] - ps['inicio_pausa']

                grasa_carne_color = 'Verde' if corte.grasa_carne < configuraciones[0].verde else 'Amarillo' if corte.grasa_carne < configuraciones[0].amarillo else 'Rojo'
                hueso_carne_color = 'Verde' if corte.hueso_carne < configuraciones[1].verde else 'Amarillo' if corte.hueso_carne < configuraciones[1].amarillo else 'Rojo'
                piezas_vendibles_color = 'Verde' if corte.piezas_vendibles >= configuraciones[2].verde else 'Amarillo' if corte.piezas_vendibles < configuraciones[2].verde and corte.piezas_vendibles >= configuraciones[2].amarillo else 'Rojo'

                list.append({
                    'id': corte.id,
                    'cantidad_canales': corte.cantidad_canales,
                    'horas_jornada': corte.horas_jornada,
                    'canales_hora': corte.canales_hora,
                    'tiempo_entre_canales': corte.tiempo_entre_canales,
                    'grasa_carne': corte.grasa_carne,
                    'grasa_carne_color': grasa_carne_color,
                    'hueso_carne': corte.hueso_carne,
                    'hueso_carne_color': hueso_carne_color,
                    'tiempo_muerto_max': corte.tiempo_muerto,
                    'piezas_vendibles': corte.piezas_vendibles,
                    'piezas_vendibles_color': piezas_vendibles_color,
                    'tiempo_muerto': tiempo_m if tiempo_m else 0,
                    'inicio': corte.inicio,
                    'fin': corte.fin,
                    'conteo': conteo,
                    'pausas': pausas,
                    'promedio_canales_hora': canales_hora,
                })
                lista = sorted(list, key=lambda x: x['hueso_carne'], reverse=False)
            return Response(lista, status=status.HTTP_200_OK)
        elif tipo == 'Piezas Vendibles':
            for corte in cortes:
                conteos = Conteo.objects.filter(corte=corte)
                pausa = Pausa.objects.filter(corte=corte)
                canales_hora = (Pausa.objects.filter(corte=corte).count()/2) / corte.horas_jornada
                conteo = 0
                pausas = []

                for c in conteos:
                    conteo += c.cantidad
                for p in pausa:
                    pausas.append({
                        'inicio_pausa': p.inicio_pausa,
                        'fin_pausa': p.fin_pausa
                    })
                tiempo_m = None
                for ps in pausas:
                    if ps['fin_pausa']:
                        if not tiempo_m:
                            tiempo_m = ps['fin_pausa'] - ps['inicio_pausa']
                        tiempo_m += ps['fin_pausa'] - ps['inicio_pausa']

                grasa_carne_color = 'Verde' if corte.grasa_carne < configuraciones[0].verde else 'Amarillo' if corte.grasa_carne < configuraciones[0].amarillo else 'Rojo'
                hueso_carne_color = 'Verde' if corte.hueso_carne < configuraciones[1].verde else 'Amarillo' if corte.hueso_carne < configuraciones[1].amarillo else 'Rojo'
                piezas_vendibles_color = 'Verde' if corte.piezas_vendibles >= configuraciones[2].verde else 'Amarillo' if corte.piezas_vendibles < configuraciones[2].verde and corte.piezas_vendibles >= configuraciones[2].amarillo else 'Rojo'

                list.append({
                    'id': corte.id,
                    'cantidad_canales': corte.cantidad_canales,
                    'horas_jornada': corte.horas_jornada,
                    'canales_hora': corte.canales_hora,
                    'tiempo_entre_canales': corte.tiempo_entre_canales,
                    'grasa_carne': corte.grasa_carne,
                    'grasa_carne_color': grasa_carne_color,
                    'hueso_carne': corte.hueso_carne,
                    'hueso_carne_color': hueso_carne_color,
                    'tiempo_muerto_max': corte.tiempo_muerto,
                    'piezas_vendibles': corte.piezas_vendibles,
                    'piezas_vendibles_color': piezas_vendibles_color,
                    'tiempo_muerto': tiempo_m if tiempo_m else 0,
                    'inicio': corte.inicio,
                    'fin': corte.fin,
                    'conteo': conteo,
                    'pausas': pausas,
                    'promedio_canales_hora': canales_hora,
                })
                lista = sorted(list, key=lambda x: x['piezas_vendibles'], reverse=True)
            return Response(lista, status=status.HTTP_200_OK)
        else:
            return Response({'message':'Tipo no valido'}, status=status.HTTP_400_BAD_REQUEST)

class ReporteTopMenorView(APIView):

    permission_classes = [AllowAny]

    def get(self, request):
        rango_dias_atras = request.GET.get('rango')
        tipo = request.GET.get('tipo')
        configuraciones = Configuracion.objects.all()
        cortes = Corte.objects.filter(inicio__range=[datetime.now() - timedelta(days=int(rango_dias_atras)), datetime.now()])
        list = []

        if tipo == 'Canales Procesados':
            for corte in cortes:
                conteos = Conteo.objects.filter(corte=corte)
                pausa = Pausa.objects.filter(corte=corte)
                canales_hora = (Pausa.objects.filter(corte=corte).count()/2) / corte.horas_jornada
                conteo = 0
                pausas = []

                for c in conteos:
                    conteo += c.cantidad
                for p in pausa:
                    pausas.append({
                        'inicio_pausa': p.inicio_pausa,
                        'fin_pausa': p.fin_pausa
                    })
                tiempo_m = None
                for ps in pausas:
                    if ps['fin_pausa']:
                        if not tiempo_m:
                            tiempo_m = ps['fin_pausa'] - ps['inicio_pausa']
                        tiempo_m += ps['fin_pausa'] - ps['inicio_pausa']

                grasa_carne_color = 'Verde' if corte.grasa_carne < configuraciones[0].verde else 'Amarillo' if corte.grasa_carne < configuraciones[0].amarillo else 'Rojo'
                hueso_carne_color = 'Verde' if corte.hueso_carne < configuraciones[1].verde else 'Amarillo' if corte.hueso_carne < configuraciones[1].amarillo else 'Rojo'
                piezas_vendibles_color = 'Verde' if corte.piezas_vendibles >= configuraciones[2].verde else 'Amarillo' if corte.piezas_vendibles < configuraciones[2].verde and corte.piezas_vendibles >= configuraciones[2].amarillo else 'Rojo'

                list.append({
                    'id': corte.id,
                    'cantidad_canales': corte.cantidad_canales,
                    'horas_jornada': corte.horas_jornada,
                    'canales_hora': corte.canales_hora,
                    'tiempo_entre_canales': corte.tiempo_entre_canales,
                    'grasa_carne': corte.grasa_carne,
                    'grasa_carne_color': grasa_carne_color,
                    'hueso_carne': corte.hueso_carne,
                    'hueso_carne_color': hueso_carne_color,
                    'tiempo_muerto_max': corte.tiempo_muerto,
                    'piezas_vendibles': corte.piezas_vendibles,
                    'piezas_vendibles_color': piezas_vendibles_color,
                    'tiempo_muerto': tiempo_m if tiempo_m else 0,
                    'inicio': corte.inicio,
                    'fin': corte.fin,
                    'conteo': conteo,
                    'pausas': pausas,
                    'promedio_canales_hora': canales_hora,
                })
                lista = sorted(list, key=lambda x: x['conteo'], reverse=False)
            return Response(lista, status=status.HTTP_200_OK)

        elif tipo == 'Tiempo Muerto':
            for corte in cortes:
                conteos = Conteo.objects.filter(corte=corte)
                pausa = Pausa.objects.filter(corte=corte)
                canales_hora = (Pausa.objects.filter(corte=corte).count()/2) / corte.horas_jornada
                conteo = 0
                pausas = []

                for c in conteos:
                    conteo += c.cantidad
                for p in pausa:
                    pausas.append({
                        'inicio_pausa': p.inicio_pausa,
                        'fin_pausa': p.fin_pausa
                    })
                tiempo_m = None
                for ps in pausas:
                    if ps['fin_pausa']:
                        if not tiempo_m:
                            tiempo_m = ps['fin_pausa'] - ps['inicio_pausa']
                        tiempo_m += ps['fin_pausa'] - ps['inicio_pausa']

                grasa_carne_color = 'Verde' if corte.grasa_carne < configuraciones[0].verde else 'Amarillo' if corte.grasa_carne < configuraciones[0].amarillo else 'Rojo'
                hueso_carne_color = 'Verde' if corte.hueso_carne < configuraciones[1].verde else 'Amarillo' if corte.hueso_carne < configuraciones[1].amarillo else 'Rojo'
                piezas_vendibles_color = 'Verde' if corte.piezas_vendibles >= configuraciones[2].verde else 'Amarillo' if corte.piezas_vendibles < configuraciones[2].verde and corte.piezas_vendibles >= configuraciones[2].amarillo else 'Rojo'

                list.append({
                    'id': corte.id,
                    'cantidad_canales': corte.cantidad_canales,
                    'horas_jornada': corte.horas_jornada,
                    'canales_hora': corte.canales_hora,
                    'tiempo_entre_canales': corte.tiempo_entre_canales,
                    'grasa_carne': corte.grasa_carne,
                    'grasa_carne_color': grasa_carne_color,
                    'hueso_carne': corte.hueso_carne,
                    'hueso_carne_color': hueso_carne_color,
                    'tiempo_muerto_max': corte.tiempo_muerto,
                    'piezas_vendibles': corte.piezas_vendibles,
                    'piezas_vendibles_color': piezas_vendibles_color,
                    'tiempo_muerto': tiempo_m if tiempo_m else 0,
                    'inicio': corte.inicio,
                    'fin': corte.fin,
                    'conteo': conteo,
                    'pausas': pausas,
                    'promedio_canales_hora': canales_hora,
                })
                lista = sorted(list, key=lambda x: x['tiempo_muerto'], reverse=True)
            return Response(lista, status=status.HTTP_200_OK)
        elif tipo == 'Canales/Hora':
            for corte in cortes:
                conteos = Conteo.objects.filter(corte=corte)
                pausa = Pausa.objects.filter(corte=corte)
                canales_hora = (Pausa.objects.filter(corte=corte).count()/2) / corte.horas_jornada
                conteo = 0
                pausas = []

                for c in conteos:
                    conteo += c.cantidad
                for p in pausa:
                    pausas.append({
                        'inicio_pausa': p.inicio_pausa,
                        'fin_pausa': p.fin_pausa
                    })
                tiempo_m = None
                for ps in pausas:
                    if ps['fin_pausa']:
                        if not tiempo_m:
                            tiempo_m = ps['fin_pausa'] - ps['inicio_pausa']
                        tiempo_m += ps['fin_pausa'] - ps['inicio_pausa']

                grasa_carne_color = 'Verde' if corte.grasa_carne < configuraciones[0].verde else 'Amarillo' if corte.grasa_carne < configuraciones[0].amarillo else 'Rojo'
                hueso_carne_color = 'Verde' if corte.hueso_carne < configuraciones[1].verde else 'Amarillo' if corte.hueso_carne < configuraciones[1].amarillo else 'Rojo'
                piezas_vendibles_color = 'Verde' if corte.piezas_vendibles >= configuraciones[2].verde else 'Amarillo' if corte.piezas_vendibles < configuraciones[2].verde and corte.piezas_vendibles >= configuraciones[2].amarillo else 'Rojo'

                list.append({
                    'id': corte.id,
                    'cantidad_canales': corte.cantidad_canales,
                    'horas_jornada': corte.horas_jornada,
                    'canales_hora': corte.canales_hora,
                    'tiempo_entre_canales': corte.tiempo_entre_canales,
                    'grasa_carne': corte.grasa_carne,
                    'grasa_carne_color': grasa_carne_color,
                    'hueso_carne': corte.hueso_carne,
                    'hueso_carne_color': hueso_carne_color,
                    'tiempo_muerto_max': corte.tiempo_muerto,
                    'piezas_vendibles': corte.piezas_vendibles,
                    'piezas_vendibles_color': piezas_vendibles_color,
                    'tiempo_muerto': tiempo_m if tiempo_m else 0,
                    'inicio': corte.inicio,
                    'fin': corte.fin,
                    'conteo': conteo,
                    'pausas': pausas,
                    'promedio_canales_hora': canales_hora,
                })
                lista = sorted(list, key=lambda x: x['canales_hora'], reverse=False)
            return Response(lista, status=status.HTTP_200_OK)
        elif tipo == 'Grasa Carne':
            for corte in cortes:
                conteos = Conteo.objects.filter(corte=corte)
                pausa = Pausa.objects.filter(corte=corte)
                canales_hora = (Pausa.objects.filter(corte=corte).count()/2) / corte.horas_jornada
                conteo = 0
                pausas = []

                for c in conteos:
                    conteo += c.cantidad
                for p in pausa:
                    pausas.append({
                        'inicio_pausa': p.inicio_pausa,
                        'fin_pausa': p.fin_pausa
                    })
                tiempo_m = None
                for ps in pausas:
                    if ps['fin_pausa']:
                        if not tiempo_m:
                            tiempo_m = ps['fin_pausa'] - ps['inicio_pausa']
                        tiempo_m += ps['fin_pausa'] - ps['inicio_pausa']

                grasa_carne_color = 'Verde' if corte.grasa_carne < configuraciones[0].verde else 'Amarillo' if corte.grasa_carne < configuraciones[0].amarillo else 'Rojo'
                hueso_carne_color = 'Verde' if corte.hueso_carne < configuraciones[1].verde else 'Amarillo' if corte.hueso_carne < configuraciones[1].amarillo else 'Rojo'
                piezas_vendibles_color = 'Verde' if corte.piezas_vendibles >= configuraciones[2].verde else 'Amarillo' if corte.piezas_vendibles < configuraciones[2].verde and corte.piezas_vendibles >= configuraciones[2].amarillo else 'Rojo'

                list.append({
                    'id': corte.id,
                    'cantidad_canales': corte.cantidad_canales,
                    'horas_jornada': corte.horas_jornada,
                    'canales_hora': corte.canales_hora,
                    'tiempo_entre_canales': corte.tiempo_entre_canales,
                    'grasa_carne': corte.grasa_carne,
                    'grasa_carne_color': grasa_carne_color,
                    'hueso_carne': corte.hueso_carne,
                    'hueso_carne_color': hueso_carne_color,
                    'tiempo_muerto_max': corte.tiempo_muerto,
                    'piezas_vendibles': corte.piezas_vendibles,
                    'piezas_vendibles_color': piezas_vendibles_color,
                    'tiempo_muerto': tiempo_m if tiempo_m else 0,
                    'inicio': corte.inicio,
                    'fin': corte.fin,
                    'conteo': conteo,
                    'pausas': pausas,
                    'promedio_canales_hora': canales_hora,
                })
                lista = sorted(list, key=lambda x: x['grasa_carne'], reverse=True)
            return Response(lista, status=status.HTTP_200_OK)
        elif tipo == 'Hueso Carne':
            for corte in cortes:
                conteos = Conteo.objects.filter(corte=corte)
                pausa = Pausa.objects.filter(corte=corte)
                canales_hora = (Pausa.objects.filter(corte=corte).count()/2) / corte.horas_jornada
                conteo = 0
                pausas = []

                for c in conteos:
                    conteo += c.cantidad
                for p in pausa:
                    pausas.append({
                        'inicio_pausa': p.inicio_pausa,
                        'fin_pausa': p.fin_pausa
                    })
                tiempo_m = None
                for ps in pausas:
                    if ps['fin_pausa']:
                        if not tiempo_m:
                            tiempo_m = ps['fin_pausa'] - ps['inicio_pausa']
                        tiempo_m += ps['fin_pausa'] - ps['inicio_pausa']

                grasa_carne_color = 'Verde' if corte.grasa_carne < configuraciones[0].verde else 'Amarillo' if corte.grasa_carne < configuraciones[0].amarillo else 'Rojo'
                hueso_carne_color = 'Verde' if corte.hueso_carne < configuraciones[1].verde else 'Amarillo' if corte.hueso_carne < configuraciones[1].amarillo else 'Rojo'
                piezas_vendibles_color = 'Verde' if corte.piezas_vendibles >= configuraciones[2].verde else 'Amarillo' if corte.piezas_vendibles < configuraciones[2].verde and corte.piezas_vendibles >= configuraciones[2].amarillo else 'Rojo'

                list.append({
                    'id': corte.id,
                    'cantidad_canales': corte.cantidad_canales,
                    'horas_jornada': corte.horas_jornada,
                    'canales_hora': corte.canales_hora,
                    'tiempo_entre_canales': corte.tiempo_entre_canales,
                    'grasa_carne': corte.grasa_carne,
                    'grasa_carne_color': grasa_carne_color,
                    'hueso_carne': corte.hueso_carne,
                    'hueso_carne_color': hueso_carne_color,
                    'tiempo_muerto_max': corte.tiempo_muerto,
                    'piezas_vendibles': corte.piezas_vendibles,
                    'piezas_vendibles_color': piezas_vendibles_color,
                    'tiempo_muerto': tiempo_m if tiempo_m else 0,
                    'inicio': corte.inicio,
                    'fin': corte.fin,
                    'conteo': conteo,
                    'pausas': pausas,
                    'promedio_canales_hora': canales_hora,
                })
                lista = sorted(list, key=lambda x: x['hueso_carne'], reverse=True)
            return Response(lista, status=status.HTTP_200_OK)
        elif tipo == 'Piezas Vendibles':
            for corte in cortes:
                conteos = Conteo.objects.filter(corte=corte)
                pausa = Pausa.objects.filter(corte=corte)
                canales_hora = (Pausa.objects.filter(corte=corte).count()/2) / corte.horas_jornada
                conteo = 0
                pausas = []

                for c in conteos:
                    conteo += c.cantidad
                for p in pausa:
                    pausas.append({
                        'inicio_pausa': p.inicio_pausa,
                        'fin_pausa': p.fin_pausa
                    })
                tiempo_m = None
                for ps in pausas:
                    if ps['fin_pausa']:
                        if not tiempo_m:
                            tiempo_m = ps['fin_pausa'] - ps['inicio_pausa']
                        tiempo_m += ps['fin_pausa'] - ps['inicio_pausa']

                grasa_carne_color = 'Verde' if corte.grasa_carne < configuraciones[0].verde else 'Amarillo' if corte.grasa_carne < configuraciones[0].amarillo else 'Rojo'
                hueso_carne_color = 'Verde' if corte.hueso_carne < configuraciones[1].verde else 'Amarillo' if corte.hueso_carne < configuraciones[1].amarillo else 'Rojo'
                piezas_vendibles_color = 'Verde' if corte.piezas_vendibles >= configuraciones[2].verde else 'Amarillo' if corte.piezas_vendibles < configuraciones[2].verde and corte.piezas_vendibles >= configuraciones[2].amarillo else 'Rojo'

                list.append({
                    'id': corte.id,
                    'cantidad_canales': corte.cantidad_canales,
                    'horas_jornada': corte.horas_jornada,
                    'canales_hora': corte.canales_hora,
                    'tiempo_entre_canales': corte.tiempo_entre_canales,
                    'grasa_carne': corte.grasa_carne,
                    'grasa_carne_color': grasa_carne_color,
                    'hueso_carne': corte.hueso_carne,
                    'hueso_carne_color': hueso_carne_color,
                    'tiempo_muerto_max': corte.tiempo_muerto,
                    'piezas_vendibles': corte.piezas_vendibles,
                    'piezas_vendibles_color': piezas_vendibles_color,
                    'tiempo_muerto': tiempo_m if tiempo_m else 0,
                    'inicio': corte.inicio,
                    'fin': corte.fin,
                    'conteo': conteo,
                    'pausas': pausas,
                    'promedio_canales_hora': canales_hora,
                })
                lista = sorted(list, key=lambda x: x['piezas_vendibles'], reverse=False)
            return Response(lista, status=status.HTTP_200_OK)
        else:
            return Response({'message':'Tipo no valido'}, status=status.HTTP_400_BAD_REQUEST)


class Conteos40View(APIView):

    permission_classes = [AllowAny]

    def get(self, request):
        corte = Corte.objects.last()

        if corte:
            i = 0
            while i < 40:
                Conteo.objects.create(
                    corte=corte,
                    cantidad=0.5
                )
                i += 1

            return Response({'message':'Conteos creados'}, status=status.HTTP_200_OK)

        return Response({'message':'No hay cortes'}, status=status.HTTP_400_BAD_REQUEST)