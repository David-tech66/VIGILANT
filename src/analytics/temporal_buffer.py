import time
from collections import deque


class DrowsinessAnalyzer:
    """
    Motor analítico temporal y Máquina de Estados para VIGILANT.
    Incluye suavizado EMA, bloqueo por giro lateral (Yaw), histéresis,
    calibración robusta de EAR + Pitch y cooldown anti-spam.
    """
    ESTADO_NORMAL = "NORMAL"
    ESTADO_FATIGA = "FATIGA_TEMPRANA"
    ESTADO_MICROSUEÑO = "MICROSUEÑO"
    ESTADO_PERDIDO = "OBJETIVO_PERDIDO"

    def __init__(
        self,
        ear_umbral=0.20,
        mar_umbral=0.65,
        pitch_umbral=-18.0,
        yaw_umbral=28.0,
        tiempo_microsueno=1.5,
        tiempo_bostezo=1.4,
        tiempo_cabeceo=1.2,
        ventana_fatiga=60.0,
        cooldown_fatiga=15.0
    ):
        self.ear_umbral = ear_umbral
        self.mar_umbral = mar_umbral
        self.pitch_umbral = pitch_umbral
        self.yaw_umbral = yaw_umbral
        self.tiempo_microsueno = tiempo_microsueno
        self.tiempo_bostezo = tiempo_bostezo
        self.tiempo_cabeceo = tiempo_cabeceo
        self.ventana_fatiga = ventana_fatiga
        self.cooldown_fatiga = cooldown_fatiga

        # Factores de suavizado exponencial (EMA): menor = más suave
        self.alpha_ear = 0.45
        self.alpha_mar = 0.40
        self.alpha_pose = 0.30

        # Márgenes de histéresis para evitar parpadeos en el borde del umbral
        self.histeresis_ear = 0.025
        self.histeresis_mar = 0.07
        self.histeresis_pitch = 3.0

        # Valores suavizados actuales
        self._ear_suave = None
        self._mar_suave = None
        self._pitch_suave = None
        self._yaw_suave = None

        # Estados internos con histéresis
        self._ojos_cerrados_activo = False
        self._boca_abierta_activa = False
        self._cabeceo_activo = False

        # Timers internos
        self._inicio_ojos_cerrados = None
        self._inicio_bostezo = None
        self._inicio_cabeceo = None
        self._ultima_fatiga = None

        # Cooldowns para evitar avisos repetitivos de fatiga temprana
        self._ultimo_aviso_bostezo = 0.0
        self._ultimo_aviso_cabeceo = 0.0

        # Banderas de flanco de subida
        self._microsueno_reportado = False
        self._bostezo_reportado = False
        self._cabeceo_reportado = False

        # Historial para gráfica de telemetría
        self.historial_ear = deque(maxlen=100)

        # Calibración dinámica (3 segundos: EAR + Pitch de reposo)
        self._calibrando = False
        self._inicio_calibracion = None
        self._muestras_ear = []
        self._muestras_pitch = []

    def iniciar_calibracion(self):
        """Activa la calibración de 3 s para ajustar EAR y Pitch base al usuario."""
        self._calibrando = True
        self._inicio_calibracion = time.time()
        self._muestras_ear.clear()
        self._muestras_pitch.clear()
        self._reiniciar_eventos_activos()

    def _suavizar(self, atributo: str, valor: float, alpha: float) -> float:
        previo = getattr(self, atributo)
        nuevo = valor if previo is None else (alpha * valor + (1.0 - alpha) * previo)
        setattr(self, atributo, nuevo)
        return nuevo

    def _reiniciar_suavizado(self):
        self._ear_suave = None
        self._mar_suave = None
        self._pitch_suave = None
        self._yaw_suave = None

    def evaluar(self, ear: float, mar: float, pitch: float, yaw: float = 0.0) -> dict:
        """
        Evalúa las métricas actuales y devuelve el estado del sistema.
        """
        ahora = time.time()

        # 1. Rostro perdido (Bandera: ear == -1.0)
        if ear == -1.0:
            self._reiniciar_eventos_activos()
            self._reiniciar_suavizado()
            return {
                "estado": self.ESTADO_PERDIDO,
                "duracion_evento": 0.0,
                "fatiga_acumulada": self._tiene_fatiga_reciente(ahora),
                "calibrando": self._calibrando,
                "nuevo_incidente": False,
                "tipo_incidente": None,
                "mirada_desviada": False
            }

        # 2. Suavizado exponencial (reduce ruido de landmarks por luz/lentes)
        ear_s = self._suavizar("_ear_suave", ear, self.alpha_ear)
        mar_s = self._suavizar("_mar_suave", mar, self.alpha_mar)
        pitch_s = self._suavizar("_pitch_suave", pitch, self.alpha_pose)
        yaw_s = self._suavizar("_yaw_suave", yaw, self.alpha_pose)

        self.historial_ear.append(ear_s)

        # 3. Calibración dinámica (3 segundos)
        if self._calibrando:
            # Solo guarda muestras cuando el usuario mira razonablemente al frente
            if abs(yaw_s) <= 20.0:
                self._muestras_ear.append(ear_s)
                self._muestras_pitch.append(pitch_s)

            if ahora - self._inicio_calibracion >= 3.0:
                if self._muestras_ear:
                    # Percentil 65 ignora parpadeos breves ocurridos durante la calibración
                    ordenadas_ear = sorted(self._muestras_ear)
                    ear_base = ordenadas_ear[int(len(ordenadas_ear) * 0.65)]
                    self.ear_umbral = max(0.15, min(round(ear_base * 0.70, 3), 0.25))

                if self._muestras_pitch:
                    ordenadas_pitch = sorted(self._muestras_pitch)
                    pitch_base = ordenadas_pitch[len(ordenadas_pitch) // 2]
                    # Exige caer 16° por debajo de la postura natural del usuario
                    self.pitch_umbral = max(-35.0, min(round(pitch_base - 16.0, 1), -10.0))

                self._calibrando = False

            return {
                "estado": self.ESTADO_NORMAL,
                "duracion_evento": 0.0,
                "fatiga_acumulada": False,
                "calibrando": self._calibrando,
                "nuevo_incidente": False,
                "tipo_incidente": None,
                "mirada_desviada": False
            }

        fatiga_acumulada = self._tiene_fatiga_reciente(ahora)

        # 4. Bloqueo por giro lateral (Yaw Gating)
        # Si gira la cabeza (ej. espejos) sin estar ya en microsueño, pausa timers
        if abs(yaw_s) > self.yaw_umbral and not self._microsueno_reportado:
            self._reiniciar_eventos_activos()
            return {
                "estado": self.ESTADO_FATIGA if fatiga_acumulada else self.ESTADO_NORMAL,
                "duracion_evento": 0.0,
                "fatiga_acumulada": fatiga_acumulada,
                "calibrando": False,
                "nuevo_incidente": False,
                "tipo_incidente": None,
                "mirada_desviada": True
            }

        # 5. Evaluación de Bostezo (MAR) con histéresis y cooldown
        if not self._boca_abierta_activa:
            if mar_s > self.mar_umbral:
                self._boca_abierta_activa = True
        else:
            if mar_s < (self.mar_umbral - self.histeresis_mar):
                self._boca_abierta_activa = False

        bostezo_confirmado = False
        nuevo_bostezo = False
        if self._boca_abierta_activa:
            if self._inicio_bostezo is None:
                self._inicio_bostezo = ahora
            elif (ahora - self._inicio_bostezo) >= self.tiempo_bostezo:
                bostezo_confirmado = True
                self._ultima_fatiga = ahora
                en_cooldown = (ahora - self._ultimo_aviso_bostezo) < self.cooldown_fatiga
                if not self._bostezo_reportado and not en_cooldown:
                    nuevo_bostezo = True
                    self._bostezo_reportado = True
                    self._ultimo_aviso_bostezo = ahora
        else:
            self._inicio_bostezo = None
            self._bostezo_reportado = False

        # 6. Evaluación de Cabeceo (Pitch) con histéresis y cooldown
        if not self._cabeceo_activo:
            if pitch_s < self.pitch_umbral:
                self._cabeceo_activo = True
        else:
            if pitch_s > (self.pitch_umbral + self.histeresis_pitch):
                self._cabeceo_activo = False

        cabeceo_confirmado = False
        nuevo_cabeceo = False
        if self._cabeceo_activo:
            if self._inicio_cabeceo is None:
                self._inicio_cabeceo = ahora
            elif (ahora - self._inicio_cabeceo) >= self.tiempo_cabeceo:
                cabeceo_confirmado = True
                self._ultima_fatiga = ahora
                en_cooldown = (ahora - self._ultimo_aviso_cabeceo) < self.cooldown_fatiga
                if not self._cabeceo_reportado and not en_cooldown:
                    nuevo_cabeceo = True
                    self._cabeceo_reportado = True
                    self._ultimo_aviso_cabeceo = ahora
        else:
            self._inicio_cabeceo = None
            self._cabeceo_reportado = False

        fatiga_acumulada = self._tiene_fatiga_reciente(ahora)
        limite_microsueno = 1.0 if fatiga_acumulada else self.tiempo_microsueno

        # 7. Evaluación de Ojos Cerrados (EAR) con histéresis -> Microsueño
        if not self._ojos_cerrados_activo:
            if ear_s < self.ear_umbral:
                self._ojos_cerrados_activo = True
        else:
            if ear_s > (self.ear_umbral + self.histeresis_ear):
                self._ojos_cerrados_activo = False

        if self._ojos_cerrados_activo:
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
                    "tipo_incidente": "Microsueño Crítico" if nuevo_microsueno else None,
                    "mirada_desviada": False
                }
        else:
            self._inicio_ojos_cerrados = None
            self._microsueno_reportado = False

        # 8. Estado de advertencia (Alerta Amarilla)
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
                "tipo_incidente": tipo_incidente,
                "mirada_desviada": False
            }

        # 9. Vigilia normal (Verde)
        return {
            "estado": self.ESTADO_NORMAL,
            "duracion_evento": 0.0,
            "fatiga_acumulada": False,
            "calibrando": False,
            "nuevo_incidente": False,
            "tipo_incidente": None,
            "mirada_desviada": False
        }

    def _reiniciar_eventos_activos(self):
        self._ojos_cerrados_activo = False
        self._boca_abierta_activa = False
        self._cabeceo_activo = False
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