import time
import numpy as np


class DrowsinessAnalyzer:

    ESTADO_NORMAL = "NORMAL"
    ESTADO_FATIGA = "FATIGA_TEMPRANA"
    ESTADO_MICROSUEÑO = "MICROSUEÑO"
    ESTADO_SIN_ROSTRO = "OBJETIVO_PERDIDO"

    def __init__(self):
        # Umbrales de referencia y respaldo
        self.ear_umbral = 0.21
        self.ear_histeresis = 0.03

        self.mar_umbral = 0.60
        self.mar_histeresis = 0.10

        self.pitch_umbral = -18.0
        self.pitch_histeresis = 4.0

        self.yaw_limite = 28.0

        # Umbrales IA (CNN ojos cerrados con histéresis)
        self.prob_umbral_cierre = 0.50
        self.prob_umbral_apertura = 0.22

        # Factores de suavizado EMA
        self.alpha_geo = 0.35
        self.alpha_prob = 0.40

        # Temporizaciones y cooldown
        self.duracion_microsueño_normal = 1.5
        self.duracion_microsueño_fatiga = 1.0
        self.duracion_bostezo = 1.5
        self.duracion_cabeceo = 1.2
        self.ventana_fatiga = 60.0
        self.cooldown_incidente = 15.0

        # Estado suavizado EMA
        self._ear_ema = None
        self._mar_ema = None
        self._pitch_ema = None
        self._yaw_ema = None
        self._prob_ema = None

        # Estados con histéresis y relojes
        self._ojos_cerrados = False
        self._bostezando = False
        self._cabeceando = False

        self._inicio_cierre = None
        self._inicio_bostezo = None
        self._inicio_cabeceo = None

        self._incidente_microsueño_registrado = False
        self._ultimo_evento_fatiga = 0.0
        self._ultimo_bostezo = 0.0
        self._ultimo_cabeceo = 0.0

        # Calibración dinámica (3 s)
        self._calibrando = False
        self._inicio_calibracion = 0.0
        self._muestras_ear = []
        self._muestras_pitch = []

    def iniciar_calibracion(self):
        self._calibrando = True
        self._inicio_calibracion = time.time()
        self._muestras_ear.clear()
        self._muestras_pitch.clear()
        self._reiniciar_eventos_activos()

    def _reiniciar_ema(self):
        self._ear_ema = None
        self._mar_ema = None
        self._pitch_ema = None
        self._yaw_ema = None
        self._prob_ema = None

    def _reiniciar_eventos_activos(self):
        self._ojos_cerrados = False
        self._bostezando = False
        self._cabeceando = False
        self._inicio_cierre = None
        self._inicio_bostezo = None
        self._inicio_cabeceo = None
        self._incidente_microsueño_registrado = False

    @staticmethod
    def _actualizar_ema(anterior, actual, alpha):
        if anterior is None:
            return float(actual)
        return float(alpha * actual + (1.0 - alpha) * anterior)

    def _resultado(
        self,
        estado,
        calibrando=False,
        mirada_desviada=False,
        fatiga_acumulada=False,
        duracion_evento=0.0,
        nuevo_incidente=False,
        tipo_incidente=None,
        modo_ojos="EAR",
        prob_cierre_ema=-1.0,
        ear_ema=-1.0,
    ):
        return {
            "estado": estado,
            "calibrando": calibrando,
            "mirada_desviada": mirada_desviada,
            "fatiga_acumulada": fatiga_acumulada,
            "duracion_evento": duracion_evento,
            "nuevo_incidente": nuevo_incidente,
            "tipo_incidente": tipo_incidente,
            "modo_ojos": modo_ojos,
            "prob_cierre_ema": prob_cierre_ema,
            "ear_ema": ear_ema,
        }

    def evaluar(self, ear, mar, pitch, yaw=0.0, prob_cierre=-1.0):
        ahora = time.time()
        fatiga_acumulada = (ahora - self._ultimo_evento_fatiga) <= self.ventana_fatiga

        # Sin rostro detectado
        if ear < 0:
            self._reiniciar_ema()
            self._reiniciar_eventos_activos()
            return self._resultado(
                estado=self.ESTADO_SIN_ROSTRO,
                calibrando=self._calibrando,
                fatiga_acumulada=fatiga_acumulada,
                modo_ojos="IA_CNN" if prob_cierre >= 0 else "EAR",
            )

        # 1. Suavizado EMA
        self._ear_ema = self._actualizar_ema(self._ear_ema, ear, self.alpha_geo)
        self._mar_ema = self._actualizar_ema(self._mar_ema, mar, self.alpha_geo)
        self._pitch_ema = self._actualizar_ema(self._pitch_ema, pitch, self.alpha_geo)
        self._yaw_ema = self._actualizar_ema(self._yaw_ema, yaw, self.alpha_geo)

        if prob_cierre >= 0.0:
            self._prob_ema = self._actualizar_ema(self._prob_ema, prob_cierre, self.alpha_prob)
            modo_ojos = "IA_CNN"
            prob_salida = self._prob_ema
        else:
            self._prob_ema = None
            modo_ojos = "EAR"
            prob_salida = -1.0

        # 2. Calibración dinámica de postura (Pitch) y respaldo (EAR)
        if self._calibrando:
            if abs(self._yaw_ema) <= self.yaw_limite:
                self._muestras_ear.append(ear)
                self._muestras_pitch.append(pitch)

            if (ahora - self._inicio_calibracion) >= 3.0:
                if len(self._muestras_ear) >= 15:
                    # Percentil 75 ignora parpadeos naturales durante los 3 segundos
                    ear_base = float(np.percentile(self._muestras_ear, 75))
                    self.ear_umbral = float(np.clip(ear_base * 0.75, 0.15, 0.28))

                    pitch_base = float(np.median(self._muestras_pitch))
                    self.pitch_umbral = float(pitch_base - 15.0)

                self._calibrando = False

            return self._resultado(
                estado=self.ESTADO_NORMAL,
                calibrando=self._calibrando,
                fatiga_acumulada=fatiga_acumulada,
                modo_ojos=modo_ojos,
                prob_cierre_ema=prob_salida,
                ear_ema=self._ear_ema,
            )

        # 3. Bloqueo por giro lateral (mirar espejos o conversar de lado)
        if abs(self._yaw_ema) > self.yaw_limite:
            self._reiniciar_eventos_activos()
            return self._resultado(
                estado=self.ESTADO_NORMAL,
                mirada_desviada=True,
                fatiga_acumulada=fatiga_acumulada,
                modo_ojos=modo_ojos,
                prob_cierre_ema=prob_salida,
                ear_ema=self._ear_ema,
            )

        # 4. Detección de ojos cerrados (CNN principal / EAR respaldo) con histéresis
        # Si la cabeza está inclinada hacia abajo (cabeceo), la perspectiva eleva
        # falsamente la probabilidad de cierre; exigimos >= 85% para no pisar "Cabeceo".
        cabeza_inclinada = self._pitch_ema < self.pitch_umbral

        if modo_ojos == "IA_CNN":
            umbral_cierre_cnn = (
                max(self.prob_umbral_cierre, 0.85)
                if cabeza_inclinada
                else self.prob_umbral_cierre
            )
            if not self._ojos_cerrados:
                if self._prob_ema >= umbral_cierre_cnn:
                    self._ojos_cerrados = True
            else:
                if self._prob_ema < self.prob_umbral_apertura:
                    self._ojos_cerrados = False
        else:
            umbral_ear_efectivo = (
                self.ear_umbral * 0.85
                if cabeza_inclinada
                else self.ear_umbral
            )
            if not self._ojos_cerrados:
                if self._ear_ema < umbral_ear_efectivo:
                    self._ojos_cerrados = True
            else:
                if self._ear_ema > (self.ear_umbral + self.ear_histeresis):
                    self._ojos_cerrados = False

        if self._ojos_cerrados:
            if self._inicio_cierre is None:
                self._inicio_cierre = ahora
            duracion_cierre = ahora - self._inicio_cierre
        else:
            self._inicio_cierre = None
            duracion_cierre = 0.0
            self._incidente_microsueño_registrado = False

        # 5. Detección de bostezo (MAR con histéresis)
        if not self._bostezando:
            if self._mar_ema > self.mar_umbral:
                self._bostezando = True
        else:
            if self._mar_ema < (self.mar_umbral - self.mar_histeresis):
                self._bostezando = False

        if self._bostezando:
            if self._inicio_bostezo is None:
                self._inicio_bostezo = ahora
            duracion_bostezo = ahora - self._inicio_bostezo
        else:
            self._inicio_bostezo = None
            duracion_bostezo = 0.0

        # 6. Detección de cabeceo (Pitch con histéresis)
        if not self._cabeceando:
            if self._pitch_ema < self.pitch_umbral:
                self._cabeceando = True
        else:
            if self._pitch_ema > (self.pitch_umbral + self.pitch_histeresis):
                self._cabeceando = False

        if self._cabeceando:
            if self._inicio_cabeceo is None:
                self._inicio_cabeceo = ahora
            duracion_cabeceo = ahora - self._inicio_cabeceo
        else:
            self._inicio_cabeceo = None
            duracion_cabeceo = 0.0

        # 7. Evaluación de estado e incidentes con cooldown
        nuevo_incidente = False
        tipo_incidente = None
        limite_microsueño = (
            self.duracion_microsueño_fatiga
            if fatiga_acumulada
            else self.duracion_microsueño_normal
        )

        if duracion_cierre >= limite_microsueño:
            estado = self.ESTADO_MICROSUEÑO
            if not self._incidente_microsueño_registrado:
                nuevo_incidente = True
                tipo_incidente = "Microsueño"
                self._incidente_microsueño_registrado = True
                self._ultimo_evento_fatiga = ahora
                fatiga_acumulada = True
        else:
            if (
                duracion_bostezo >= self.duracion_bostezo
                and (ahora - self._ultimo_bostezo) >= self.cooldown_incidente
            ):
                nuevo_incidente = True
                tipo_incidente = "Bostezo Prolongado"
                self._ultimo_bostezo = ahora
                self._ultimo_evento_fatiga = ahora
                fatiga_acumulada = True
            elif (
                duracion_cabeceo >= self.duracion_cabeceo
                and (ahora - self._ultimo_cabeceo) >= self.cooldown_incidente
            ):
                nuevo_incidente = True
                tipo_incidente = "Cabeceo"
                self._ultimo_cabeceo = ahora
                self._ultimo_evento_fatiga = ahora
                fatiga_acumulada = True

            estado = self.ESTADO_FATIGA if fatiga_acumulada else self.ESTADO_NORMAL

        duracion_evento = max(duracion_cierre, duracion_bostezo, duracion_cabeceo)

        return self._resultado(
            estado=estado,
            fatiga_acumulada=fatiga_acumulada,
            duracion_evento=duracion_evento,
            nuevo_incidente=nuevo_incidente,
            tipo_incidente=tipo_incidente,
            modo_ojos=modo_ojos,
            prob_cierre_ema=prob_salida,
            ear_ema=self._ear_ema,
        )