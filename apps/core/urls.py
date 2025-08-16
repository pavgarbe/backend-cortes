from django.urls import path
from .views import LedOnYellow, LedOnGreen, LedOnRed, SirenOn, SirenOff, CortesView, StatusCorte, PausaView, FinView, InicioView, MonitorView, LastFiveCortesView, CortesReportView, ReporteTopMayorView, ReporteTopMenorView, ConfiguracionView, Conteos40View

app_name = 'apps.core'

urlpatterns = [
    path('ledonyellow/', LedOnYellow.as_view(), name='ledonyellow'),
    path('ledongreen/', LedOnGreen.as_view(), name='ledongreen'),
    path('ledonred/', LedOnRed.as_view(), name='ledonred'),
    path('siren/', SirenOn.as_view(), name='siren'),
    path('sirenoff/', SirenOff.as_view(), name='sirenoff'),
    path('cortes/', CortesView.as_view(), name='corte_create'),
    path('cortes/status/', StatusCorte.as_view(), name='corte_status'),
    path('cortes/pausa/', PausaView.as_view(), name='pausa_create'),
    path('cortes/fin/', FinView.as_view(), name='fin_create'),
    path('cortes/inicio/', InicioView.as_view(), name='inicio_create'),
    path('cortes/monitor/', MonitorView.as_view(), name='monitor'),
    path('cortes/last5/', LastFiveCortesView.as_view(), name='last_five'),
    path('cortes/report1/', CortesReportView.as_view(), name='report1'),
    path('cortes/report2/', ReporteTopMayorView.as_view(), name='report2'),
    path('cortes/report3/', ReporteTopMenorView.as_view(), name='report3'),
    path('cortes/config/', ConfiguracionView.as_view(), name='configuracion'),
    path('cortes/conteos40/', Conteos40View.as_view(), name='conteos40'),
]
