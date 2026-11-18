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
        ventana_fatiga=60.0
    ):
        self.ear_umbral = ear_umbral
        self.mar_umbral = mar_umbral
        self.pitch_umbral = pitch_umbral
        self.tiempo_microsueno = tiempo_microsueno
        self.tiempo_bostezo = tiempo_bostezo
        self.ventana_fatiga = ventana_fatiga

        # Timers internos
        self._inicio_ojos_cerrados = None
        self._inicio_bostezo = None
        self._ultima_fatiga = None

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

    def evaluar(self, ear: float, mar: float, pitch: float) -> dict:
        """
        Evalúa las métricas actuales y devuelve un diccionario con el estado del sistema.
        """
        ahora = time.time()

        # 1. Manejo de rostro perdido (Bandera acordada: ear == -1.0)
        if ear == -1.0:
            self._inicio_ojos_cerrados = None
            self._inicio_bostezo = None
            return {
                "estado": self.ESTADO_PERDIDO,
                "duracion_evento": 0.0,
                "fatiga_acumulada": self._tiene_fatiga_reciente(ahora),
                "calibrando": self._calibrando,
                "nuevo_incidente": False,
                "tipo_incidente": None
            }

        self.historial_ear.append(ear)

        # 2. Proceso de calibración dinámica (3 segundos)
        if self._calibrando:
            self._muestras_calibracion.append(ear)
            if ahora - self._inicio_calibracion >= 3.0:
                if self._muestras_calibracion:
                    ear_base = sum(self._muestras_calibracion) / len(self._muestras_calibracion)
                    self.ear_umbral = round(ear_base * 0.70, 3)
                self._calibrando = False

        # 3. Evaluación de Bostezo (MAR) y Cabeceo (Pitch) -> Fatiga temprana
        bostezo_confirmado = False
        if mar > self.mar_umbral:
            if self._inicio_bostezo is None:
                self._inicio_bostezo = ahora
            elif (ahora - self._inicio_bostezo) >= self.tiempo_bostezo:
                bostezo_confirmado = True
                self._ultima_fatiga = ahora
        else:
            self._inicio_bostezo = None

        cabeceo_detectado = pitch < self.pitch_umbral
        if cabeceo_detectado:
            self._ultima_fatiga = ahora

        fatiga_acumulada = self._tiene_fatiga_reciente(ahora)

        # Si ya hay fatiga acumulada, somos más estrictos con el tiempo de microsueño (1.0s)
        limite_microsueno = 1.0 if fatiga_acumulada else self.tiempo_microsueno

        # 4. Evaluación de Ojos Cerrados (EAR) -> Microsueño
        duracion_ojos = 0.0
        if ear < self.ear_umbral:
            if self._inicio_ojos_cerrados is None:
                self._inicio_ojos_cerrados = ahora
            duracion_ojos = ahora - self._inicio_ojos_cerrados

            if duracion_ojos >= limite_microsueno:
                return {
                    "estado": self.ESTADO_MICROSUEÑO,
                    "duracion_evento": round(duracion_ojos, 2),
                    "fatiga_acumulada": fatiga_acumulada,
                    "calibrando": self._calibrando,
                    "nuevo_incidente": True,
                    "tipo_incidente": "Microsueño Crítico"
                }
        else:
            self._inicio_ojos_cerrados = None

        # 5. Estado de advertencia (Alerta Amarilla)
        if bostezo_confirmado or cabeceo_detectado or fatiga_acumulada:
            tipo = "Bostezo Prolongado" if bostezo_confirmado else ("Cabeceo" if cabeceo_detectado else None)
            return {
                "estado": self.ESTADO_FATIGA,
                "duracion_evento": 0.0,
                "fatiga_acumulada": True,
                "calibrando": self._calibrando,
                "nuevo_incidente": tipo is not None,
                "tipo_incidente": tipo
            }

        # 6. Vigilia normal (Verde)
        return {
            "estado": self.ESTADO_NORMAL,
            "duracion_evento": 0.0,
            "fatiga_acumulada": False,
            "calibrando": self._calibrando,
            "nuevo_incidente": False,
            "tipo_incidente": None
        }

    def _tiene_fatiga_reciente(self, ahora: float) -> bool:
        if self._ultima_fatiga is None:
            return False
        return (ahora - self._ultima_fatiga) <= self.ventana_fatiga