# apps/core/hardware.py
from gpiozero import LED, Button
from datetime import datetime
from .models import Corte, Pausa
from threading import Timer
import time

# Pines propuestos para LÁMPARAS de estado (distintas del semáforo que ya tienes):
PIN_LAMP_RUN   = 19  # Verde (jornada en proceso)
PIN_LAMP_PAUSE = 20  # Amarillo (pausa)
PIN_LAMP_STOP  = 21  # Rojo (parado)

# Pines propuestos para BOTONES físicos:
PIN_BTN_START = 5    # Inicio (habilitado sólo si ya hay jornada iniciada y estás en pausa)
PIN_BTN_PAUSE = 6    # Pausa
PIN_BTN_STOP  = 13   # Paro

HOLD_SECONDS = 5.0   # mantener 5 segundos

class HardwareJornada:
    """
    Maneja 3 botones físicos (start/pause/stop) y 3 lámparas de estado.
    No modifica semáforo ni sirena (eso ya lo llevas aparte).
    Las transiciones llaman a callbacks que definiremos en views.py
      - on_start(), on_pause(), on_stop()
    """

    def __init__(self, factory):
        # Lámparas
        self.lamp_run   = LED(PIN_LAMP_RUN,   pin_factory=factory)
        self.lamp_pause = LED(PIN_LAMP_PAUSE, pin_factory=factory)
        self.lamp_stop  = LED(PIN_LAMP_STOP,  pin_factory=factory)

        # Botones con hold de 5s y antirrebote
        self.btn_start = Button(PIN_BTN_START, pull_up=True, bounce_time=0.05, hold_time=HOLD_SECONDS, pin_factory=factory)
        self.btn_pause = Button(PIN_BTN_PAUSE, pull_up=True, bounce_time=0.05, hold_time=HOLD_SECONDS, pin_factory=factory)
        self.btn_stop  = Button(PIN_BTN_STOP,  pull_up=True, bounce_time=0.05, hold_time=HOLD_SECONDS, pin_factory=factory)

        # Callbacks a inyectar desde views.py
        self.on_start = lambda: None
        self.on_pause = lambda: None
        self.on_stop  = lambda: None

        # Eventos al mantener 5s
        self.btn_start.when_held = self._held_start
        self.btn_pause.when_held = self._held_pause
        self.btn_stop.when_held  = self._held_stop

        # Al encender sistema: estado parado (rojo)
        self.update_luces("stopped")

    def _get_estado_actual(self):
        """
        Devuelve 'stopped' | 'paused' | 'running'
        - stopped: no hay corte, no hay inicio, o ya hay fin
        - paused: último Pausa sin fin_pausa
        - running: corte iniciado sin pausa abierta ni fin
        """
        corte = Corte.objects.last()
        if not corte or not corte.inicio or corte.fin:
            return "stopped"
        pausa = Pausa.objects.filter(corte=corte).last()
        if pausa and pausa.fin_pausa is None:
            return "paused"
        return "running"

    def _hay_jornada_activa(self):
        """True si hay corte iniciado y sin fin."""
        corte = Corte.objects.last()
        return bool(corte and corte.inicio and not corte.fin)

    # --- LÓGICA DE BOTONES (con reglas que pediste) ---

    def _held_start(self):
        estado = self._get_estado_actual()
        # Sólo funciona si hay jornada activa y estás en 'paused' → pasar a 'running'
        if not self._hay_jornada_activa():
            return
        if estado == "paused":
            self.on_start()  # reanudar (verde)
        # Si ya está en running o stopped, no hace nada.

    def _held_pause(self):
        estado = self._get_estado_actual()
        # Sólo funciona si hay jornada activa y no estás ya pausado
        if not self._hay_jornada_activa():
            return
        if estado == "running":
            self.on_pause()  # pasar a pausa (amarillo)
        # Si está en paused o stopped, no hace nada.

    def _held_stop(self):
        estado = self._get_estado_actual()
        # Sólo funciona si hay jornada activa (running o paused)
        if not self._hay_jornada_activa():
            return
        if estado in ("running", "paused"):
            self.on_stop()  # finalizar (rojo)

    # --- LÁMPARAS ---

    def update_luces(self, estado: str):
        """
        Enciende sólo la lámpara del estado actual.
        """
        self.lamp_run.value   = 1 if estado == "running" else 0
        self.lamp_pause.value = 1 if estado == "paused"  else 0
        self.lamp_stop.value  = 1 if estado == "stopped" else 0
