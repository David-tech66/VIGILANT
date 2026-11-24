import time
from collections import deque

class DrowsinessAnalyzer:

    # =========================================================================
    # BLOQUE 1: CONSTANTES DE LA MÁQUINA DE ESTADOS
    # Qué es: Las 4 etiquetas fijas que definen el estado del conductor.
    # Para qué sirve: Estandarizar la salida para que la interfaz sepa qué alerta mostrar.
    # =========================================================================
    ESTADO_NORMAL = "NORMAL"
    ESTADO_FATIGA = "FATIGA_TEMPRANA"
    ESTADO_MICROSUEÑO = "MICROSUEÑO"
    ESTADO_PERDIDO = "OBJETIVO_PERDIDO"

    # =========================================================================
    # BLOQUE 2: CONFIGURACIÓN INICIAL (__init__)
    # Qué es: El constructor donde se definen umbrales, tiempos, filtros y variables internas.
    # Para qué sirve: Inicializar los límites de detección (EAR, MAR, Pitch, Yaw),
    #                 el suavizado EMA, la histéresis, los cooldowns y el historial.
    # =========================================================================
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

        self.alpha_ear = 0.45
        self.alpha_mar = 0.40
        self.alpha_pose = 0.30

        self.histeresis_ear = 0.025
        self.histeresis_mar = 0.07
        self.histeresis_pitch = 3.0

        self._ear_suave = None
        self._mar_suave = None
        self._pitch_suave = None
        self._yaw_suave = None

        self._ojos_cerrados_activo = False
        self._boca_abierta_activa = False
        self._cabeceo_activo = False

        self._inicio_ojos_cerrados = None
        self._inicio_bostezo = None
        self._inicio_cabeceo = None
        self._ultima_fatiga = None

        self._ultimo_aviso_bostezo = 0.0
        self._ultimo_aviso_cabeceo = 0.0

        self._microsueno_reportado = False
        self._bostezo_reportado = False
        self._cabeceo_reportado = False

        self.historial_ear = deque(maxlen=100)

        self._calibrando = False
        self._inicio_calibracion = None
        self._muestras_ear = []
        self._muestras_pitch = []

    # =========================================================================
    # BLOQUE 3: UTILIDADES DE CALIBRACIÓN Y SUAVIZADO (EMA)
    # Qué es: Métodos de apoyo para activar la calibración y filtrar ruido de la cámara.
    # Para qué sirve: Iniciar la toma de muestras de 3s y estabilizar las métricas
    #                 frente a vibraciones o cambios de luz.
    # =========================================================================
    def iniciar_calibracion(self):
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

    # =========================================================================
    # BLOQUE 4: MOTOR PRINCIPAL DE EVALUACIÓN (evaluar)
    # Qué es: El método que corre en cada frame para decidir el estado del conductor.
    # Para qué sirve: Procesar las métricas en orden de prioridad y devolver el diagnóstico.
    # =========================================================================
    def evaluar(self, ear: float, mar: float, pitch: float, yaw: float = 0.0) -> dict:
        ahora = time.time()

        # --- BLOQUE 4.1: ROSTRO PERDIDO ---
        # Qué es: Validación de la bandera ear == -1.0.
        # Para qué sirve: Limpiar timers y filtros cuando la cámara deja de ver la cara.
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

        # --- BLOQUE 4.2: SUAVIZADO Y TELEMETRÍA ---
        # Qué es: Aplicación del filtro EMA y registro en la cola historial_ear.
        # Para qué sirve: Estabilizar los valores antes de evaluarlos y alimentar la gráfica.
        ear_s = self._suavizar(
            "_ear_suave", 
            ear, 
            self.alpha_ear
        )
        
        mar_s = self._suavizar(
            "_mar_suave", 
            mar, 
            self.alpha_mar
        )
        
        pitch_s = self._suavizar(
            "_pitch_suave", 
            pitch, 
            self.alpha_pose
        )
        
        yaw_s = self._suavizar(
            "_yaw_suave", 
            yaw, 
            self.alpha_pose
        )

        self.historial_ear.append(ear_s)

        # --- BLOQUE 4.3: CALIBRACIÓN DINÁMICA (3 SEGUNDOS) ---
        # Qué es: Recolección de muestras mirando al frente y cálculo de percentiles.
        # Para qué sirve: Ajustar automáticamente los umbrales de EAR y Pitch a cada usuario.
        if self._calibrando:
            if abs(yaw_s) <= 20.0:
                self._muestras_ear.append(ear_s)
                self._muestras_pitch.append(pitch_s)

            if ahora - self._inicio_calibracion >= 3.0:
                if self._muestras_ear:
                    ordenadas_ear = sorted(self._muestras_ear)
                    ear_base = ordenadas_ear[int(len(ordenadas_ear) * 0.65)]
                    self.ear_umbral = max(0.15, min(round(ear_base * 0.70, 3), 0.25))

                if self._muestras_pitch:
                    ordenadas_pitch = sorted(self._muestras_pitch)
                    pitch_base = ordenadas_pitch[len(ordenadas_pitch) // 2]
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

        # --- BLOQUE 4.4: BLOQUEO POR GIRO LATERAL (YAW GATING) ---
        # Qué es: Filtro que detecta si la cabeza giró demasiado hacia los lados.
        # Para qué sirve: Pausar timers al mirar espejos y evitar falsos microsueños.
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

        # --- BLOQUE 4.5: EVALUACIÓN DE BOSTEZO (MAR) ---
        # Qué es: Detector de boca abierta prolongada con histéresis y cooldown.
        # Para qué sirve: Confirmar bostezos reales, marcar fatiga y evitar alertas repetidas.
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

        # --- BLOQUE 4.6: EVALUACIÓN DE CABECEO (PITCH) ---
        # Qué es: Detector de inclinación prolongada de cabeza hacia abajo con histéresis y cooldown.
        # Para qué sirve: Identificar pérdida de postura por sueño y registrar fatiga reciente.
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

        # --- BLOQUE 4.7: EVALUACIÓN DE MICROSUEÑO (EAR - ALERTA ROJA) ---
        # Qué es: Detector de ojos cerrados con prioridad máxima y límite adaptable.
        # Para qué sirve: Disparar alerta crítica más rápido (1.0s) si ya hay fatiga acumulada.
        fatiga_acumulada = self._tiene_fatiga_reciente(ahora)
        limite_microsueno = 1.0 if fatiga_acumulada else self.tiempo_microsueno

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

        # --- BLOQUE 4.8: ESTADO DE ADVERTENCIA (ALERTA AMARILLA) ---
        # Qué es: Salida de fatiga temprana por bostezo, cabeceo o fatiga reciente.
        # Para qué sirve: Advertir al conductor antes de que llegue a un microsueño.
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

        # --- BLOQUE 4.9: VIGILIA NORMAL (VERDE) ---
        # Qué es: Retorno por defecto cuando no hay anomalías.
        # Para qué sirve: Indicar que el conductor está atento y sin signos de fatiga.
        return {
            "estado": self.ESTADO_NORMAL,
            "duracion_evento": 0.0,
            "fatiga_acumulada": False,
            "calibrando": False,
            "nuevo_incidente": False,
            "tipo_incidente": None,
            "mirada_desviada": False
        }

    # =========================================================================
    # BLOQUE 5: MÉTODOS AUXILIARES INTERNOS
    # Qué es: Funciones privadas de limpieza y consulta de memoria temporal.
    # Para qué sirve: Resetear eventos en curso y comprobar si la fatiga sigue vigente.
    # =========================================================================
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