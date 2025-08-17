
# --- hardware.py: Manejo de hardware físico con gpiozero ---
from gpiozero import LED, Button
from .models import Corte, Pausa

# Pines para lámparas de estado
PIN_LAMP_RUN   = 19  # Verde (jornada en proceso)
PIN_LAMP_PAUSE = 20  # Amarillo (pausa)
PIN_LAMP_STOP  = 21  # Rojo (parado)

# Pines para botones físicos
PIN_BTN_START = 5    # Inicio
PIN_BTN_PAUSE = 6    # Pausa
PIN_BTN_STOP  = 13   # Paro

HOLD_SECONDS = 5.0   # Segundos para activar acción por "hold"



class HardwareJornada:
    """
    Controla 3 botones físicos (start/pause/stop) y 3 lámparas de estado.
    Las transiciones llaman a callbacks configurables desde views.py:
        - on_start(), on_pause(), on_stop()
    """
    def __init__(self, factory):
        # Inicialización de lámparas
        self.lamp_run   = LED(PIN_LAMP_RUN,   pin_factory=factory)
        self.lamp_pause = LED(PIN_LAMP_PAUSE, pin_factory=factory)
        self.lamp_stop  = LED(PIN_LAMP_STOP,  pin_factory=factory)

        # Inicialización de botones físicos con "hold" y antirrebote
        self.btn_start = Button(PIN_BTN_START, pull_up=True, bounce_time=0.05, hold_time=HOLD_SECONDS, pin_factory=factory)
        self.btn_pause = Button(PIN_BTN_PAUSE, pull_up=True, bounce_time=0.05, hold_time=HOLD_SECONDS, pin_factory=factory)
        self.btn_stop  = Button(PIN_BTN_STOP,  pull_up=True, bounce_time=0.05, hold_time=HOLD_SECONDS, pin_factory=factory)

        # Callbacks configurables
        self.on_start = lambda: None
        self.on_pause = lambda: None
        self.on_stop  = lambda: None

        # Conectar eventos "hold" a métodos internos
        self.btn_start.when_held = self._held_start
        self.btn_pause.when_held = self._held_pause
        self.btn_stop.when_held  = self._held_stop

        # Estado inicial: parado (rojo)
        self.update_luces("stopped")


    def _get_estado_actual(self):
        """
        Devuelve el estado actual de la jornada:
        - 'stopped': no hay corte, no hay inicio, o ya hay fin
        - 'paused': último Pausa sin fin_pausa
        - 'running': corte iniciado sin pausa abierta ni fin
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


    # --- Lógica de botones físicos ---
    def _held_start(self):
        """Solo reanuda si está en pausa y hay jornada activa."""
        if self._hay_jornada_activa() and self._get_estado_actual() == "paused":
            self.on_start()

    def _held_pause(self):
        """Solo pausa si está en running y hay jornada activa."""
        if self._hay_jornada_activa() and self._get_estado_actual() == "running":
            self.on_pause()

    def _held_stop(self):
        """Solo finaliza si está en running o paused y hay jornada activa."""
        if self._hay_jornada_activa() and self._get_estado_actual() in ("running", "paused"):
            self.on_stop()


    # --- Control de lámparas de estado ---
    def update_luces(self, estado: str):
        """
        Enciende solo la lámpara correspondiente al estado actual.
        """
        self.lamp_run.value   = 1 if estado == "running" else 0
        self.lamp_pause.value = 1 if estado == "paused"  else 0
        self.lamp_stop.value  = 1 if estado == "stopped" else 0
