import sqlite3
import time
from collections import deque
from datetime import datetime
from pathlib import Path
import numpy as np
from PySide6.QtWidgets import (
    QMainWindow, 
    QLabel, 
    QVBoxLayout, 
    QHBoxLayout,
    QWidget, 
    QFrame, 
    QPushButton, 
    QComboBox,
    QListWidget, 
    QListWidgetItem, 
    QProgressBar
)
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Qt, Slot, Signal, QUrl, QTimer

try:
    from PySide6.QtMultimedia import QSoundEffect, QMediaDevices
    AUDIO_DISPONIBLE = True
except ImportError:
    QSoundEffect = None
    QMediaDevices = None
    AUDIO_DISPONIBLE = False

from src.analytics.temporal_buffer import DrowsinessAnalyzer

try:
    import pyqtgraph as pg
    PYQTGRAPH_DISPONIBLE = True
except ImportError:
    pg = None
    PYQTGRAPH_DISPONIBLE = False


class MainWindow(QMainWindow):

    source_changed = Signal(object)

    def __init__(self):
        super().__init__()

        self.setWindowTitle("VIGILANT v2.0 | Sistema de Monitoreo de Somnolencia")
        self.setMinimumSize(1080, 680)
        self.resize(1360, 820)

        self.raiz_proyecto = Path(__file__).resolve().parents[2]
        self.analyzer = DrowsinessAnalyzer()

        self.historial_ear = deque(maxlen=120)
        self.ultimo_pixmap = None
        self.inicio_calibracion = None
        self.ultimo_frame_tiempo = None
        self._ultimo_estilo_fatiga = None
        self._cerrando = False

        # Control de alertas sonoras
        self.audio_silenciado = False
        self.sonido_fatiga = None
        self.sonido_critico = None

        self._inicializar_base_datos()
        self._inicializar_audio()
        self._cargar_estilos()
        self._construir_ui()
        self.fuente_preferida = 1   # Por defecto el sistema prefiere Cámara USB
        self.fuente_activa = None
        self._inicializar_monitor_camaras()

    # BASE DE DATOS
    def _inicializar_base_datos(self):
        ruta_db = self.raiz_proyecto / "src" / "database" / "vigilant.db"
        ruta_db.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(ruta_db)

        self.db.execute("""
            CREATE TABLE IF NOT EXISTS incidentes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                fecha TEXT NOT NULL,
                hora TEXT NOT NULL
            )
        """)
        self.db.commit()

    # SISTEMA DE AUDIO (QSoundEffect)
    def _inicializar_audio(self):
        if not AUDIO_DISPONIBLE:
            print("[VIGILANT] QtMultimedia no disponible; alertas sonoras desactivadas.")
            return

        carpeta_audio = self.raiz_proyecto / "assets" / "audio"
        ruta_fatiga = carpeta_audio / "aviso_fatiga.wav"
        ruta_critica = carpeta_audio / "alerta_critica.wav"

        if ruta_fatiga.exists():
            self.sonido_fatiga = QSoundEffect(self)
            self.sonido_fatiga.setSource(QUrl.fromLocalFile(str(ruta_fatiga)))
            self.sonido_fatiga.setLoopCount(1)
            self.sonido_fatiga.setVolume(0.85)
        else:
            print(f"[VIGILANT] Aviso: no se encontró {ruta_fatiga}")

        if ruta_critica.exists():
            self.sonido_critico = QSoundEffect(self)
            self.sonido_critico.setSource(QUrl.fromLocalFile(str(ruta_critica)))
            loop_infinito = (
                QSoundEffect.Loop.Infinite.value
                if hasattr(QSoundEffect, "Loop")
                else int(QSoundEffect.Infinite)
            )
            self.sonido_critico.setLoopCount(loop_infinito)
            self.sonido_critico.setVolume(1.0)
        else:
            print(f"[VIGILANT] Aviso: no se encontró {ruta_critica}")

    def _detener_alertas(self):
        if self.sonido_critico is not None and self.sonido_critico.isPlaying():
            self.sonido_critico.stop()
        if self.sonido_fatiga is not None and self.sonido_fatiga.isPlaying():
            self.sonido_fatiga.stop()

    def _gestionar_alertas_sonoras(self, resultado):
        if self.audio_silenciado or resultado["calibrando"]:
            self._detener_alertas()
            return

        estado = resultado["estado"]

        # Nivel 2 (Crítico): bucle continuo mientras persista MICROSUEÑO
        if estado == DrowsinessAnalyzer.ESTADO_MICROSUEÑO:
            if self.sonido_fatiga is not None and self.sonido_fatiga.isPlaying():
                self.sonido_fatiga.stop()
            if self.sonido_critico is not None and not self.sonido_critico.isPlaying():
                self.sonido_critico.play()
            return

        # Al salir de MICROSUEÑO, cortar la alarma crítica inmediatamente
        if self.sonido_critico is not None and self.sonido_critico.isPlaying():
            self.sonido_critico.stop()

        # Nivel 1 (Fatiga temprana): reproducir una sola vez por incidente nuevo
        if (
            resultado["nuevo_incidente"]
            and resultado["tipo_incidente"] in ("Bostezo Prolongado", "Cabeceo")
            and self.sonido_fatiga is not None
            and not self.sonido_fatiga.isPlaying()
        ):
            self.sonido_fatiga.play()

    def _alternar_audio(self):
        self.audio_silenciado = not self.audio_silenciado
        if self.audio_silenciado:
            self._detener_alertas()
            self.audio_button.setText("AUDIO: OFF")
            self.audio_button.setObjectName("audio-off")
        else:
            self.audio_button.setText("AUDIO: ON")
            self.audio_button.setObjectName("audio-on")

        self.audio_button.style().unpolish(self.audio_button)
        self.audio_button.style().polish(self.audio_button)

    def _cargar_estilos(self):
        ruta_style = self.raiz_proyecto / "assets" / "styles" / "Style.css"
        if ruta_style.exists():
            with open(ruta_style, "r", encoding="utf-8") as archivo:
                self.setStyleSheet(archivo.read())

    # CONSTRUCCIÓN DE INTERFAZ
    def _construir_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 10, 16, 8)
        main_layout.setSpacing(8)

        # BARRA SUPERIOR
        header = QHBoxLayout()
        header.setSpacing(10)

        logo_layout = QVBoxLayout()
        logo_layout.setSpacing(1)

        logo = QLabel("VIGILANT")
        logo.setObjectName("logo")

        version = QLabel("SISTEMA DE MONITOREO DE SOMNOLENCIA • v2.0")
        version.setObjectName("subtitle")

        logo_layout.addWidget(logo)
        logo_layout.addWidget(version)

        header.addLayout(logo_layout)
        header.addStretch()

        source_title = QLabel("FUENTE:")
        source_title.setObjectName("muted")

        self.source_select = QComboBox()
        self.source_select.setObjectName("source-select")
        self.source_select.addItem("Cámara USB", 1)
        self.source_select.addItem("Cámara integrada", 0)
        self.source_select.addItem("Video Benchmark", str(self.raiz_proyecto / "assets" / "benchmark.mp4"))
        self.source_select.currentIndexChanged.connect(self._on_fuente_cambiada)

        header.addWidget(source_title)
        header.addWidget(self.source_select)

        self.audio_button = QPushButton("AUDIO: ON")
        self.audio_button.setObjectName("audio-on")
        self.audio_button.setCursor(Qt.PointingHandCursor)
        self.audio_button.clicked.connect(self._alternar_audio)
        header.addWidget(self.audio_button)

        self.status_label = QLabel("ESPERANDO VIDEO")
        self.status_label.setObjectName("status-normal")
        self.status_label.setAlignment(Qt.AlignCenter)
        header.addWidget(self.status_label)

        self.fps_label = QLabel("FPS: --")
        self.fps_label.setObjectName("fps-label")
        self.fps_label.setAlignment(Qt.AlignCenter)
        header.addWidget(self.fps_label)

        main_layout.addLayout(header)

        separator = QFrame()
        separator.setObjectName("separator")
        separator.setFixedHeight(2)
        main_layout.addWidget(separator)

        # CONTENIDO PRINCIPAL
        body = QHBoxLayout()
        body.setSpacing(12)

        # COLUMNA IZQUIERDA
        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)

        # VISOR DE VIDEO
        video_card = QFrame()
        video_card.setObjectName("video-card")

        video_layout = QVBoxLayout(video_card)
        video_layout.setContentsMargins(12, 10, 12, 10)
        video_layout.setSpacing(6)

        video_title = QLabel("VISOR DE MONITOREO FACIAL")
        video_title.setObjectName("section")
        video_layout.addWidget(video_title)

        points_label = QLabel("MEDIAPIPE FACE MESH • OJOS • BOCA • POSE")
        points_label.setObjectName("muted")
        video_layout.addWidget(points_label)

        camera_info = QHBoxLayout()
        self.camera_label = QLabel("● CONECTANDO CÁMARA...")
        self.camera_label.setObjectName("camera-info")

        self.event_label = QLabel("EVENTO: 0.0s")
        self.event_label.setObjectName("event-info")

        camera_info.addWidget(self.camera_label)
        camera_info.addStretch()
        camera_info.addWidget(self.event_label)
        video_layout.addLayout(camera_info)

        self.video_label = QLabel("Esperando señal de cámara...")
        self.video_label.setObjectName("video")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(450, 240)
        video_layout.addWidget(self.video_label, 1)

        left_panel.addWidget(video_card, 3)

        # OSCILOSCOPIO EAR
        graph_card = QFrame()
        graph_card.setObjectName("graph-card")

        graph_layout = QVBoxLayout(graph_card)
        graph_layout.setContentsMargins(12, 10, 12, 10)
        graph_layout.setSpacing(6)

        graph_header = QHBoxLayout()
        graph_title = QLabel("OSCILOSCOPIO EAR EN TIEMPO REAL")
        graph_title.setObjectName("section")

        self.graph_threshold_label = QLabel(
            f"UMBRAL: {self.analyzer.ear_umbral:.3f}"
        )
        self.graph_threshold_label.setObjectName("threshold-info")

        graph_header.addWidget(graph_title, 1)
        graph_header.addWidget(self.graph_threshold_label)
        graph_layout.addLayout(graph_header)

        if PYQTGRAPH_DISPONIBLE:
            self.graph = pg.PlotWidget()
            self.graph.setObjectName("ear-graph")
            self.graph.setBackground("#030A13")
            self.graph.showGrid(x=True, y=True, alpha=0.20)
            self.graph.setLabel("left", "EAR", color="#9CB2CA")
            self.graph.setLabel("bottom", "Muestras", color="#9CB2CA")
            self.graph.setYRange(0, 0.5)
            self.graph.setMouseEnabled(x=False, y=False)
            self.graph.setMenuEnabled(False)
            self.graph.getAxis("left").setTextPen("#9CB2CA")
            self.graph.getAxis("bottom").setTextPen("#9CB2CA")

            self.curva_ear = self.graph.plot(pen = pg.mkPen("#38BDF8", width = 2))
            self.linea_umbral = pg.InfiniteLine(
                pos = self.analyzer.ear_umbral,
                angle = 0,
                pen = pg.mkPen("#EF4444", width = 2, style = Qt.DotLine)
            )
            self.graph.addItem(self.linea_umbral)
            graph_layout.addWidget(self.graph, 1)
        else:
            self.graph = None
            self.curva_ear = None
            self.linea_umbral = None
            graph_message = QLabel("Instala pyqtgraph para visualizar el osciloscopio EAR")
            graph_message.setObjectName("muted")
            graph_message.setAlignment(Qt.AlignCenter)
            graph_layout.addWidget(graph_message)

        self.graph_state = QLabel("NORMAL")
        self.graph_state.setObjectName("graph-state")
        self.graph_state.setAlignment(Qt.AlignCenter)

        self.graph_description = QLabel("Vigilia activa • Monitoreo estable")
        self.graph_description.setObjectName("graph-description")
        self.graph_description.setAlignment(Qt.AlignCenter)
        self.graph_description.setWordWrap(True)

        graph_layout.addWidget(self.graph_state)
        graph_layout.addWidget(self.graph_description)

        left_panel.addWidget(graph_card, 2)
        body.addLayout(left_panel, 3)

        # COLUMNA DERECHA
        right_panel = QVBoxLayout()
        right_panel.setSpacing(10)

        # SEMÁFORO: ESTADO DEL CONDUCTOR
        state_card = QFrame()
        state_card.setObjectName("state-card")

        state_layout = QVBoxLayout(state_card)
        state_layout.setContentsMargins(12, 8, 12, 8)
        state_layout.setSpacing(4)

        state_title = QLabel("ESTADO DEL CONDUCTOR")
        state_title.setObjectName("section")

        self.state_label = QLabel("EN ESPERA")
        self.state_label.setObjectName("state-title")
        self.state_label.setAlignment(Qt.AlignCenter)

        self.state_description = QLabel("Esperando datos biométricos")
        self.state_description.setObjectName("state-description")
        self.state_description.setAlignment(Qt.AlignCenter)
        self.state_description.setWordWrap(True)

        state_layout.addWidget(state_title)
        state_layout.addWidget(self.state_label)
        state_layout.addWidget(self.state_description)

        right_panel.addWidget(state_card)

        # TELEMETRÍA BIOMÉTRICA (3 columnas horizontales)
        metrics_card = QFrame()
        metrics_card.setObjectName("metrics-card")

        metrics_layout = QVBoxLayout(metrics_card)
        metrics_layout.setContentsMargins(12, 10, 12, 10)
        metrics_layout.setSpacing(8)

        metrics_title = QLabel("TELEMETRÍA BIOMÉTRICA")
        metrics_title.setObjectName("section")
        metrics_layout.addWidget(metrics_title)

        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(8)

        self.ear_label, self.ear_condition_label = self._crear_metrica(
            metrics_row, "EAR (OJOS)", "0.000", f"< {self.analyzer.ear_umbral:.3f}"
        )
        self.mar_label, _ = self._crear_metrica(
            metrics_row, "MAR (BOCA)", "0.000", f"> {self.analyzer.mar_umbral:.3f}"
        )
        self.pitch_label, self.pitch_condition_label = self._crear_metrica(
            metrics_row, "PITCH", "0.0°", f"< {self.analyzer.pitch_umbral:.1f}°"
        )

        metrics_layout.addLayout(metrics_row)

        fatigue_separator = QFrame()
        fatigue_separator.setObjectName("inner-separator")
        fatigue_separator.setFixedHeight(1)
        metrics_layout.addWidget(fatigue_separator)

        fatigue_layout = QHBoxLayout()
        fatigue_title = QLabel("Fatiga reciente (60s)")
        fatigue_title.setObjectName("metric-title")

        self.fatigue_label = QLabel("NO • Límite 1.5s")
        self.fatigue_label.setObjectName("fatigue-normal")
        self.fatigue_label.setAlignment(Qt.AlignCenter)

        fatigue_layout.addWidget(fatigue_title, 1)
        fatigue_layout.addWidget(self.fatigue_label)
        metrics_layout.addLayout(fatigue_layout)

        right_panel.addWidget(metrics_card)

        # CALIBRACIÓN DINÁMICA
        calibration_card = QFrame()
        calibration_card.setObjectName("calibration-card")

        calibration_layout = QVBoxLayout(calibration_card)
        calibration_layout.setContentsMargins(12, 10, 12, 10)
        calibration_layout.setSpacing(6)

        calibration_title = QLabel("CALIBRACIÓN DINÁMICA EAR")
        calibration_title.setObjectName("section")

        self.calibration_button = QPushButton("Calibrar EAR Dinámico (3 s)")
        self.calibration_button.setObjectName("calibration-button")
        self.calibration_button.clicked.connect(self._iniciar_calibracion)

        self.calibration_progress = QProgressBar()
        self.calibration_progress.setObjectName("calibration-progress")
        self.calibration_progress.setRange(0, 100)
        self.calibration_progress.setValue(0)

        self.threshold_label = QLabel(
            f"Umbral EAR: {self.analyzer.ear_umbral:.3f}"
        )
        self.threshold_label.setObjectName("muted")

        calibration_layout.addWidget(calibration_title)
        calibration_layout.addWidget(self.calibration_button)
        calibration_layout.addWidget(self.calibration_progress)
        calibration_layout.addWidget(self.threshold_label)

        right_panel.addWidget(calibration_card)

        # BITÁCORA DE INCIDENTES
        log_card = QFrame()
        log_card.setObjectName("log-card")

        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(12, 9, 12, 9)
        log_layout.setSpacing(6)

        log_header = QHBoxLayout()
        log_title = QLabel("BITÁCORA DE INCIDENTES")
        log_title.setObjectName("section")

        clear_button = QPushButton("Limpiar")
        clear_button.setObjectName("clear-button")
        clear_button.clicked.connect(self._limpiar_logs)

        log_header.addWidget(log_title, 1)
        log_header.addWidget(clear_button)

        self.log_list = QListWidget()
        self.log_list.setObjectName("log-list")
        self.log_list.setMinimumHeight(90)

        log_layout.addLayout(log_header)
        log_layout.addWidget(self.log_list, 1)

        right_panel.addWidget(log_card, 1)
        body.addLayout(right_panel, 2)
        main_layout.addLayout(body, 1)

        # PIE DE PÁGINA
        footer = QLabel(
            "VIGILANT v2.0  |  MEDIAPIPE FACE MESH  |  "
            "ANÁLISIS BIOMÉTRICO EN TIEMPO REAL  |  SQLITE"
        )
        footer.setObjectName("footer")
        footer.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(footer)

        self._cargar_logs()

    # CREAR TARJETA COMPACTA DE MÉTRICA
    def _crear_metrica(self, layout, nombre, valor, condicion):
        card = QFrame()
        card.setObjectName("metric-item")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(2)

        titulo = QLabel(nombre)
        titulo.setObjectName("metric-title")
        titulo.setAlignment(Qt.AlignCenter)

        valor_label = QLabel(valor)
        valor_label.setObjectName("metric")
        valor_label.setAlignment(Qt.AlignCenter)

        condicion_label = QLabel(condicion)
        condicion_label.setObjectName("metric-condition")
        condicion_label.setAlignment(Qt.AlignCenter)

        card_layout.addWidget(titulo)
        card_layout.addWidget(valor_label)
        card_layout.addWidget(condicion_label)

        layout.addWidget(card, 1)
        return valor_label, condicion_label

    # RECIBIR DATOS DEL VIDEO_WORKER
    @Slot(np.ndarray, float, float, float, float)
    def actualizar_frame(self, frame, ear, mar, pitch, yaw):
        if self._cerrando:
            return

        self._actualizar_fps()

        resultado = self.analyzer.evaluar(ear, mar, pitch, yaw)

        if ear >= 0:
            self._actualizar_metricas(ear, mar, pitch, resultado)
            self._actualizar_grafica(ear)
            self._actualizar_calibracion(resultado["calibrando"])
            self._registrar_incidente(resultado)
        else:
            self.ear_label.setText("--")
            self.mar_label.setText("--")
            self.pitch_label.setText("--")
            self.fatigue_label.setText("SIN ROSTRO")
            self._ultimo_estilo_fatiga = None

        self._actualizar_semaforo(resultado)
        self._gestionar_alertas_sonoras(resultado)
        self._mostrar_video(frame)

    # CALCULAR FPS
    def _actualizar_fps(self):
        ahora = time.perf_counter()
        if self.ultimo_frame_tiempo is not None:
            diferencia = ahora - self.ultimo_frame_tiempo
            if diferencia > 0:
                self.fps_label.setText(f"FPS: {1 / diferencia:.1f}")
        self.ultimo_frame_tiempo = ahora

    # ACTUALIZAR MÉTRICAS
    def _actualizar_metricas(self, ear, mar, pitch, resultado):
        self.ear_label.setText(f"{ear:.3f}")
        self.mar_label.setText(f"{mar:.3f}")
        self.pitch_label.setText(f"{pitch:.1f}°")

        estilo_fatiga = "fatigue-warning" if resultado["fatiga_acumulada"] else "fatigue-normal"
        if estilo_fatiga != self._ultimo_estilo_fatiga:
            self._ultimo_estilo_fatiga = estilo_fatiga
            self.fatigue_label.setText(
                "SÍ • Límite 1.0s" if resultado["fatiga_acumulada"] else "NO • Límite 1.5s"
            )
            self.fatigue_label.setObjectName(estilo_fatiga)
            self.fatigue_label.style().unpolish(self.fatigue_label)
            self.fatigue_label.style().polish(self.fatigue_label)

        self._sincronizar_umbral_ear()

    def _sincronizar_umbral_ear(self):
        umbral = self.analyzer.ear_umbral
        self.ear_condition_label.setText(f"< {umbral:.3f}")
        self.pitch_condition_label.setText(f"< {self.analyzer.pitch_umbral:.1f}°")
        self.threshold_label.setText(f"Umbral EAR: {umbral:.3f}")
        self.graph_threshold_label.setText(f"UMBRAL: {umbral:.3f}")

    # ACTUALIZAR GRÁFICA
    def _actualizar_grafica(self, ear):
        self.historial_ear.append(ear)
        if self.graph is not None:
            self.curva_ear.setData(list(self.historial_ear))
            self.linea_umbral.setValue(self.analyzer.ear_umbral)

    # ACTUALIZAR ESTADO DEL CONDUCTOR
    def _actualizar_semaforo(self, resultado):
        if resultado["calibrando"]:
            titulo, color, descripcion = (
                "CALIBRANDO",
                "#38BDF8",
                "Mantenga la vista al frente con ojos abiertos (3 s)"
            )
        elif resultado.get("mirada_desviada"):
            titulo, color, descripcion = (
                "MIRADA DESVIADA",
                "#38BDF8",
                "Giro lateral detectado • Monitoreo en pausa"
            )
        else:
            estados = {
                "NORMAL": (
                    "NORMAL",
                    "#22DFA0",
                    "Vigilia activa • Monitoreo estable"
                ),
                "FATIGA_TEMPRANA": (
                    "FATIGA TEMPRANA",
                    "#F59E0B",
                    "Se detectaron señales de fatiga • Umbral estricto (1.0 s)"
                ),
                "MICROSUEÑO": (
                    "MICROSUEÑO",
                    "#EF4444",
                    "¡ALERTA CRÍTICA! Cierre prolongado de ojos detectado"
                ),
                "OBJETIVO_PERDIDO": (
                    "OBJETIVO PERDIDO",
                    "#829AB5",
                    "No se detecta un rostro en cámara"
                )
            }
            titulo, color, descripcion = estados.get(
                resultado["estado"],
                ("EN ESPERA", "#38BDF8", "Esperando datos biométricos")
            )

        self.state_label.setText(titulo)
        self.state_label.setStyleSheet(f"color: {color};")
        self.state_description.setText(descripcion)

        self.graph_state.setText(titulo)
        self.graph_state.setStyleSheet(f"background-color: {color}; color: #07111F;")
        self.graph_description.setText(descripcion)

        self.status_label.setText(titulo)
        self.status_label.setStyleSheet(
            f"color: {color};"
            f"border: 1px solid {color};"
            "background-color: #0D1B2D;"
            "border-radius: 7px;"
            "padding: 7px 12px;"
            "font-weight: bold;"
        )

        self.event_label.setText(f"EVENTO: {resultado['duracion_evento']:.1f}s")

    # CALIBRACIÓN
    def _iniciar_calibracion(self):
        self._detener_alertas()
        self.analyzer.iniciar_calibracion()
        self.inicio_calibracion = time.time()
        self.calibration_progress.setValue(0)
        self.calibration_button.setEnabled(False)
        self.calibration_button.setText("CALIBRANDO...")

    def _actualizar_calibracion(self, calibrando):
        if self.inicio_calibracion is None:
            return

        if calibrando:
            transcurrido = time.time() - self.inicio_calibracion
            self.calibration_progress.setValue(min(int((transcurrido / 3.0) * 100), 99))
        else:
            self.calibration_progress.setValue(100)
            self.calibration_button.setEnabled(True)
            self.calibration_button.setText("Calibrar EAR Dinámico (3 s)")
            self._sincronizar_umbral_ear()
            self.inicio_calibracion = None

    # CAMBIO DE FUENTE
    def _on_fuente_cambiada(self, indice):
        self._detener_alertas()
        fuente = self.source_select.currentData()
        self.fuente_preferida = fuente
        self.source_changed.emit(fuente)

        self.status_label.setText("CAMBIANDO FUENTE")
        self.fps_label.setText("FPS: --")
        self.historial_ear.clear()
        self.ultimo_frame_tiempo = None

        if self.graph is not None:
            self.curva_ear.setData([])

    @Slot(object)
    def sincronizar_fuente_activa(self, fuente_real):
        cambio_real = fuente_real != self.fuente_activa
        self.fuente_activa = fuente_real    

        if cambio_real:
            self.historial_ear.clear()
            self.ultimo_frame_tiempo = None
            if self.graph is not None:
                self.curva_ear.setData([])

        if fuente_real is None:
            self.camera_label.setText("● SIN CÁMARA DISPONIBLE")
            self.status_label.setText("SIN SEÑAL")
            return

        indice = self.source_select.findData(fuente_real)
        if indice != -1:
            self.source_select.blockSignals(True)
            self.source_select.setCurrentIndex(indice)
            self.source_select.blockSignals(False)

        nombre = self.source_select.currentText().upper()
        self.camera_label.setText(f"● {nombre} ACTIVA")

    def _inicializar_monitor_camaras(self):
        if QMediaDevices is not None:
            self.media_devices = QMediaDevices(self)
            self.media_devices.videoInputsChanged.connect(
                self._on_dispositivos_video_cambiados
        )

    def _on_dispositivos_video_cambiados(self):
        if self._cerrando or QMediaDevices is None:
            return

        num_camaras = len(QMediaDevices.videoInputs())

        # Reconexión USB cuando el usuario quiere USB pero estaba en respaldo
        if self.fuente_preferida == 1 and self.fuente_activa != 1 and num_camaras >= 2:
            QTimer.singleShot(800, self._reintentar_camara_preferida)
    
        # Recuperación si antes no había ninguna cámara disponible
        elif (
            self.fuente_activa is None
            and isinstance(self.fuente_preferida, int)
            and num_camaras >= 1
        ):
            QTimer.singleShot(800, self._reintentar_camara_preferida)

    def _reintentar_camara_preferida(self):
        if self._cerrando:
            return

        if self.fuente_preferida == 1 and self.fuente_activa != 1:
            self.source_changed.emit(1)
        elif self.fuente_activa is None and isinstance(self.fuente_preferida, int):
            self.source_changed.emit(self.fuente_preferida)

    # REGISTRO DE INCIDENTES
    def _registrar_incidente(self, resultado):
        tipo = resultado["tipo_incidente"]
        if not resultado["nuevo_incidente"] or tipo is None:
            return

        ahora = datetime.now()
        fecha = ahora.strftime("%Y-%m-%d")
        hora = ahora.strftime("%H:%M:%S")

        self.db.execute(
            "INSERT INTO incidentes (tipo, fecha, hora) VALUES (?, ?, ?)",
            (tipo, fecha, hora)
        )
        self.db.commit()
        self._agregar_log(tipo, fecha, hora)

    def _agregar_log(self, tipo, fecha, hora):
        item = QListWidgetItem(f"{fecha}  |  {hora}  |  {tipo}")
        self.log_list.insertItem(0, item)

        while self.log_list.count() > 100:
            self.log_list.takeItem(self.log_list.count() - 1)

    def _cargar_logs(self):
        registros = self.db.execute(
            "SELECT tipo, fecha, hora FROM incidentes ORDER BY id DESC LIMIT 100"
        ).fetchall()

        for tipo, fecha, hora in reversed(registros):
            self._agregar_log(tipo, fecha, hora)

    def _limpiar_logs(self):
        self.db.execute("DELETE FROM incidentes")
        self.db.commit()
        self.log_list.clear()

    # MOSTRAR VIDEO
    def _mostrar_video(self, frame):
        h, w, ch = frame.shape
        q_img = QImage(
            frame.data, 
            w, 
            h, 
            ch * w, 
            QImage.Format_BGR888
        ).copy()
        
        pixmap = QPixmap.fromImage(q_img)
        self.ultimo_pixmap = pixmap

        self.video_label.setPixmap(
            pixmap.scaled(
                self.video_label.size(),
                Qt.KeepAspectRatio,
                Qt.FastTransformation
            )
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.ultimo_pixmap is not None:
            self.video_label.setPixmap(
                self.ultimo_pixmap.scaled(
                    self.video_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.FastTransformation
                )
            )

    def closeEvent(self, event):
        self._cerrando = True
        self._detener_alertas()
        self.db.close()
        event.accept()