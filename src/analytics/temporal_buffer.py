import time
from collections import deque


class DrowsinessAnalyzer:
    """
    Motor analítico temporal y Máquina de Estados para VIGILANT.
    Diferencia parpadeos normales de microsueños y gestiona la fatiga acumulada.
    """
    ESTADO_NORMAL = "NORMAL"
    ESTADO_FATIGA = "FATIGA_TEMPRANA"
    ESTADO_MICROSUEÑO = "MICROSUEÑO"
    ESTADO_PERDIDO = "OBJETIVO_PERDIDO"

    def __init__(
        self,
        ear_umbral=0.20,
        mar_umbral=0.60,
        pitch_umbral=-15.0,
        tiempo_microsueno=1.5,
        tiempo_bostezo=1.0,
        tiempo_cabeceo=0.8,
        ventana_fatiga=60.0
    ):
        self.ear_umbral = ear_umbral
        self.mar_umbral = mar_umbral
        self.pitch_umbral = pitch_umbral
        self.tiempo_microsueno = tiempo_microsueno
        self.tiempo_bostezo = tiempo_bostezo
        self.tiempo_cabeceo = tiempo_cabeceo
        self.ventana_fatiga = ventana_fatiga

        # Timers internos
        self._inicio_ojos_cerrados = None
        self._inicio_bostezo = None
        self._inicio_cabeceo = None
        self._ultima_fatiga = None

        # Banderas de flanco de subida (evitan duplicar registros en SQLite por frame)
        self._microsueno_reportado = False
        self._bostezo_reportado = False
        self._cabeceo_reportado = False

        # Historial para gráfica de telemetría (últimos 100 valores)
        self.historial_ear = deque(maxlen=100)

        # Calibración dinámica (3 segundos)
        self._calibrando = False
        self._inicio_calibracion = None
        self._muestras_calibracion = []

    def iniciar_calibracion(self):
        """Activa la calibración de 3 segundos para ajustar el umbral EAR al usuario."""
        self._calibrando = True
        self._inicio_calibracion = time.time()
        self._muestras_calibracion.clear()
        self._reiniciar_eventos_activos()

    def evaluar(self, ear: float, mar: float, pitch: float) -> dict:
        """
        Evalúa las métricas actuales y devuelve un diccionario con el estado del sistema.
        """
        ahora = time.time()

        # 1. Manejo de rostro perdido (Bandera acordada: ear == -1.0)
        if ear == -1.0:
            self._reiniciar_eventos_activos()
            return {
                "estado": self.ESTADO_PERDIDO,
                "duracion_evento": 0.0,
                "fatiga_acumulada": self._tiene_fatiga_reciente(ahora),
                "calibrando": self._calibrando,
                "nuevo_incidente": False,
                "tipo_incidente": None
            }

        self.historial_ear.append(ear)

        # 2. Proceso de calibración dinámica (3 segundos, sin disparar falsas alarmas)
        if self._calibrando:
            self._muestras_calibracion.append(ear)
            if ahora - self._inicio_calibracion >= 3.0:
                if self._muestras_calibracion:
                    ear_base = sum(self._muestras_calibracion) / len(self._muestras_calibracion)
                    # Acota el umbral calibrado a un rango fisiológico seguro
                    self.ear_umbral = max(0.15, min(round(ear_base * 0.70, 3), 0.25))
                self._calibrando = False

            return {
                "estado": self.ESTADO_NORMAL,
                "duracion_evento": 0.0,
                "fatiga_acumulada": False,
                "calibrando": self._calibrando,
                "nuevo_incidente": False,
                "tipo_incidente": None
            }

        # 3. Evaluación de Bostezo (MAR) con filtro temporal y flanco de subida
        bostezo_confirmado = False
        nuevo_bostezo = False
        if mar > self.mar_umbral:
            if self._inicio_bostezo is None:
                self._inicio_bostezo = ahora
            elif (ahora - self._inicio_bostezo) >= self.tiempo_bostezo:
                bostezo_confirmado = True
                self._ultima_fatiga = ahora
                if not self._bostezo_reportado:
                    nuevo_bostezo = True
                    self._bostezo_reportado = True
        else:
            self._inicio_bostezo = None
            self._bostezo_reportado = False

        # 4. Evaluación de Cabeceo (Pitch) con filtro temporal y flanco de subida
        cabeceo_confirmado = False
        nuevo_cabeceo = False
        if pitch < self.pitch_umbral:
            if self._inicio_cabeceo is None:
                self._inicio_cabeceo = ahora
            elif (ahora - self._inicio_cabeceo) >= self.tiempo_cabeceo:
                cabeceo_confirmado = True
                self._ultima_fatiga = ahora
                if not self._cabeceo_reportado:
                    nuevo_cabeceo = True
                    self._cabeceo_reportado = True
        else:
            self._inicio_cabeceo = None
            self._cabeceo_reportado = False

        fatiga_acumulada = self._tiene_fatiga_reciente(ahora)

        # Si ya hay fatiga acumulada, el límite de microsueño se vuelve más estricto (1.0 s)
        limite_microsueno = 1.0 if fatiga_acumulada else self.tiempo_microsueno

        # 5. Evaluación de Ojos Cerrados (EAR) -> Microsueño (Máxima prioridad)
        if ear < self.ear_umbral:
            if self._inicio_ojos_cerrados is None:
                self._inicio_ojos_cerrados = ahora
            duracion_ojos = ahora - self._inicio_ojos_cerrados

            if duracion_ojos >= limite_microsueno:
                nuevo_microsueno = not self._microsueno_reportado
                self._microsueno_reportado = True
                return {
                    "estado": self.ESTADO_MICROSUEÑO,
                    "duracion_evento": round(duracion_ojos, 2),
                    "fatiga_acumulada": fatiga_acumulada,
                    "calibrando": False,
                    "nuevo_incidente": nuevo_microsueno,
                    "tipo_incidente": "Microsueño Crítico" if nuevo_microsueno else None
                }
        else:
            self._inicio_ojos_cerrados = None
            self._microsueno_reportado = False

        # 6. Estado de advertencia (Alerta Amarilla)
        if bostezo_confirmado or cabeceo_confirmado or fatiga_acumulada:
            if nuevo_bostezo:
                tipo_incidente = "Bostezo Prolongado"
            elif nuevo_cabeceo:
                tipo_incidente = "Cabeceo"
            else:
                tipo_incidente = None

            return {
                "estado": self.ESTADO_FATIGA,
                "duracion_evento": 0.0,
                "fatiga_acumulada": True,
                "calibrando": False,
                "nuevo_incidente": tipo_incidente is not None,
                "tipo_incidente": tipo_incidente
            }

        # 7. Vigilia normal (Verde)
        return {
            "estado": self.ESTADO_NORMAL,
            "duracion_evento": 0.0,
            "fatiga_acumulada": False,
            "calibrando": False,
            "nuevo_incidente": False,
            "tipo_incidente": None
        }

    def _reiniciar_eventos_activos(self):
        self._inicio_ojos_cerrados = None
        self._inicio_bostezo = None
        self._inicio_cabeceo = None
        self._microsueno_reportado = False
        self._bostezo_reportado = False
        self._cabeceo_reportado = False

    def _tiene_fatiga_reciente(self, ahora: float) -> bool:
        if self._ultima_fatiga is None:
            return False
        return (ahora - self._ultima_fatiga) <= self.ventana_fatiga