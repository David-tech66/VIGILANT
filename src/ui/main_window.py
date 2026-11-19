import sqlite3
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np

from PySide6.QtWidgets import (
    QMainWindow, QLabel, QVBoxLayout, QHBoxLayout,
    QWidget, QFrame, QPushButton, QComboBox,
    QListWidget, QListWidgetItem, QProgressBar
)

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Qt, Slot, Signal

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

        self.setWindowTitle("VIGILANT v1.0 | Sistema de Monitoreo")
        self.setMinimumSize(1150, 750)
        self.resize(1400, 900)

        self.analyzer = DrowsinessAnalyzer()

        self.historial_ear = deque(maxlen=120)
        self.ultimo_incidente = None
        self.ultimo_pixmap = None
        self.inicio_calibracion = None
        self.ultimo_frame_tiempo = None

        self._inicializar_base_datos()
        self._cargar_estilos()
        self._construir_ui()

    # BASE DE DATOS

    def _inicializar_base_datos(self):

        ruta_db = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "database"
            / "vigilant.db"
        )

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

    def _cargar_estilos(self):

        ruta_style = (
            Path(__file__).resolve().parents[2]
            / "assets"
            / "styles"
            / "Style.css"
        )

        with open(ruta_style, "r", encoding="utf-8") as archivo:
            self.setStyleSheet(archivo.read())

    # CONSTRUCCIÓN DE INTERFAZ

    def _construir_ui(self):

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 12, 16, 10)
        main_layout.setSpacing(10)

        # BARRA SUPERIOR

        header = QHBoxLayout()
        header.setSpacing(12)

        logo_layout = QVBoxLayout()
        logo_layout.setSpacing(1)

        logo = QLabel("VIGILANT")
        logo.setObjectName("logo")

        version = QLabel("SISTEMA INTELIGENTE DE MONITOREO • v1.0")
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
        self.source_select.addItem(
            "Video Benchmark",
            "assets/benchmark.mp4"
        )

        self.source_select.currentIndexChanged.connect(
            self._on_fuente_cambiada
        )

        header.addWidget(source_title)
        header.addWidget(self.source_select)

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
        video_layout.setContentsMargins(12, 10, 12, 12)
        video_layout.setSpacing(8)

        video_header = QHBoxLayout()

        video_title = QLabel("VISOR DE MONITOREO FACIAL")
        video_title.setObjectName("section")

        video_header.addWidget(video_title)
        video_header.addStretch()

        video_layout.addLayout(video_header)

        points_label = QLabel(
            "MEDIAPIPE FACE MESH • OJOS • BOCA • POSE"
        )
        points_label.setObjectName("muted")

        video_layout.addWidget(points_label)

        camera_info = QHBoxLayout()

        self.camera_label = QLabel("● CÁMARA ACTIVA")
        self.camera_label.setObjectName("camera-info")

        self.event_label = QLabel("EVENTO: 0.0s")
        self.event_label.setObjectName("event-info")

        camera_info.addWidget(self.camera_label)
        camera_info.addStretch()
        camera_info.addWidget(self.event_label)

        video_layout.addLayout(camera_info)

        self.video_label = QLabel(
            "Esperando señal de cámara..."
        )
        self.video_label.setObjectName("video")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(450, 250)

        video_layout.addWidget(self.video_label, 1)

        left_panel.addWidget(video_card, 3)

        # OSCILOSCOPIO EAR

        graph_card = QFrame()
        graph_card.setObjectName("graph-card")

        graph_layout = QVBoxLayout(graph_card)
        graph_layout.setContentsMargins(12, 10, 12, 10)
        graph_layout.setSpacing(8)

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
            self.graph.setLabel("left", "Valor EAR", color="#9CB2CA")
            self.graph.setLabel("bottom", "Muestras", color="#9CB2CA")
            self.graph.setYRange(0, 0.5)
            self.graph.setMouseEnabled(x=False, y=False)
            self.graph.setMenuEnabled(False)

            self.graph.getAxis("left").setTextPen("#9CB2CA")
            self.graph.getAxis("bottom").setTextPen("#9CB2CA")

            self.curva_ear = self.graph.plot(
                pen=pg.mkPen("#38BDF8", width=2)
            )

            self.linea_umbral = pg.InfiniteLine(
                pos=self.analyzer.ear_umbral,
                angle=0,
                pen=pg.mkPen(
                    "#EF4444",
                    width=2,
                    style=Qt.DotLine
                )
            )

            self.graph.addItem(self.linea_umbral)
            graph_layout.addWidget(self.graph, 1)

        else:

            self.graph = None
            self.curva_ear = None
            self.linea_umbral = None

            graph_message = QLabel(
                "Instala pyqtgraph para visualizar el osciloscopio EAR"
            )
            graph_message.setObjectName("muted")
            graph_message.setAlignment(Qt.AlignCenter)

            graph_layout.addWidget(graph_message)

        self.graph_state = QLabel("NORMAL")
        self.graph_state.setObjectName("graph-state")
        self.graph_state.setAlignment(Qt.AlignCenter)

        self.graph_description = QLabel(
            "Vigilia activa • Monitoreo estable"
        )
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
        state_layout.setContentsMargins(12, 10, 12, 10)
        state_layout.setSpacing(5)

        state_title = QLabel("ESTADO DEL CONDUCTOR")
        state_title.setObjectName("section")

        self.state_label = QLabel("EN ESPERA")
        self.state_label.setObjectName("state-title")
        self.state_label.setAlignment(Qt.AlignCenter)
        self.state_label.setWordWrap(True)

        self.state_description = QLabel(
            "Esperando datos biométricos"
        )
        self.state_description.setObjectName("state-description")
        self.state_description.setAlignment(Qt.AlignCenter)
        self.state_description.setWordWrap(True)

        state_layout.addWidget(state_title)
        state_layout.addWidget(self.state_label)
        state_layout.addWidget(self.state_description)

        right_panel.addWidget(state_card, 1)

        # TELEMETRÍA BIOMÉTRICA

        metrics_card = QFrame()
        metrics_card.setObjectName("metrics-card")

        metrics_layout = QVBoxLayout(metrics_card)
        metrics_card.setMinimumHeight(290)
        metrics_layout.setContentsMargins(12, 10, 12, 12)
        metrics_layout.setSpacing(8)

        metrics_title = QLabel("TELEMETRÍA BIOMÉTRICA")
        metrics_title.setObjectName("section")

        metrics_layout.addWidget(metrics_title)

        self.ear_label = self._crear_metrica(
            metrics_layout, "EAR (OJOS)", "0.000", "< 0.200"
        )

        self.mar_label = self._crear_metrica(
            metrics_layout, "MAR (BOCA)", "0.000", "> 0.600"
        )

        self.pitch_label = self._crear_metrica(
            metrics_layout, "PITCH", "0.0°", "< -15.0°"
        )

        fatigue_separator = QFrame()
        fatigue_separator.setObjectName("inner-separator")
        fatigue_separator.setFixedHeight(1)

        metrics_layout.addWidget(fatigue_separator)

        fatigue_layout = QHBoxLayout()

        fatigue_title = QLabel("Fatiga reciente (60s)")
        fatigue_title.setObjectName("metric-title")
        fatigue_title.setWordWrap(True)

        self.fatigue_label = QLabel("NO • Límite 1.5s")
        self.fatigue_label.setObjectName("fatigue-normal")
        self.fatigue_label.setAlignment(Qt.AlignCenter)

        fatigue_layout.addWidget(fatigue_title, 1)
        fatigue_layout.addWidget(self.fatigue_label)

        metrics_layout.addLayout(fatigue_layout)

        right_panel.addWidget(metrics_card, 3)

        # CALIBRACIÓN DINÁMICA

        calibration_card = QFrame()
        calibration_card.setObjectName("calibration-card")

        calibration_layout = QVBoxLayout(calibration_card)
        calibration_layout.setContentsMargins(12, 10, 12, 10)
        calibration_layout.setSpacing(7)

        calibration_title = QLabel("CALIBRACIÓN DINÁMICA EAR")
        calibration_title.setObjectName("section")

        self.calibration_button = QPushButton(
            "Calibrar EAR Dinámico (3 s)"
        )
        self.calibration_button.setObjectName("calibration-button")
        self.calibration_button.clicked.connect(
            self._iniciar_calibracion
        )

        self.calibration_progress = QProgressBar()
        self.calibration_progress.setObjectName(
            "calibration-progress"
        )
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

        right_panel.addWidget(calibration_card, 2)

        # BITÁCORA DE INCIDENTES

        log_card = QFrame()
        log_card.setObjectName("log-card")

        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(12, 9, 12, 9)
        log_layout.setSpacing(7)

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
        self.log_list.setMinimumHeight(100)

        log_layout.addLayout(log_header)
        log_layout.addWidget(self.log_list, 1)

        right_panel.addWidget(log_card, 3)

        body.addLayout(right_panel, 2)

        main_layout.addLayout(body, 1)

        # INFORMACIÓN INFERIOR

        footer = QLabel(
            "VIGILANT v1.0  |  MEDIAPIPE FACE MESH  |  "
            "ANÁLISIS BIOMÉTRICO EN TIEMPO REAL  |  SQLITE"
        )
        footer.setObjectName("footer")
        footer.setAlignment(Qt.AlignCenter)

        main_layout.addWidget(footer)

        self._cargar_logs()

    # CREAR MÉTRICAS

    def _crear_metrica(self, layout, nombre, valor, condicion):

        card = QFrame()
        card.setObjectName("metric-item")
        card.setMinimumHeight(65)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(9, 6, 9, 6)
        card_layout.setSpacing(2)

        header = QHBoxLayout()

        titulo = QLabel(nombre)
        titulo.setObjectName("metric-title")

        valor_label = QLabel(valor)
        valor_label.setObjectName("metric")
        valor_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        valor_label.setMinimumHeight(32)

        header.addWidget(titulo)
        header.addStretch()
        header.addWidget(valor_label, 0, Qt.AlignRight)

        condicion_label = QLabel(condicion)
        condicion_label.setObjectName("metric-condition")

        card_layout.addLayout(header)
        card_layout.addWidget(condicion_label)

        layout.addWidget(card)

        return valor_label

    # RECIBIR DATOS DEL VIDEOWORKER

    @Slot(np.ndarray, float, float, float)
    def actualizar_frame(self, frame, ear, mar, pitch):

        self._actualizar_fps()

        self.camera_label.setText("● CÁMARA ACTIVA")

        resultado = self.analyzer.evaluar(
            ear, mar, pitch
        )

        if ear >= 0:

            self._actualizar_metricas(
                ear, mar, pitch, resultado
            )

            self._actualizar_grafica(ear)

            self._actualizar_calibracion(
                resultado["calibrando"]
            )

            self._registrar_incidente(resultado)

        else:

            self.ear_label.setText("--")
            self.mar_label.setText("--")
            self.pitch_label.setText("--")
            self.fatigue_label.setText("NO DISPONIBLE")

            self.ultimo_incidente = None

        self._actualizar_semaforo(resultado)
        self._mostrar_video(frame)

    # CALCULAR FPS

    def _actualizar_fps(self):

        ahora = time.perf_counter()

        if self.ultimo_frame_tiempo is not None:

            diferencia = ahora - self.ultimo_frame_tiempo

            if diferencia > 0:

                fps = 1 / diferencia

                self.fps_label.setText(
                    f"FPS: {fps:.1f}"
                )

        self.ultimo_frame_tiempo = ahora

    # ACTUALIZAR MÉTRICAS

    def _actualizar_metricas(
        self, ear, mar, pitch, resultado
    ):

        self.ear_label.setText(f"{ear:.3f}")
        self.mar_label.setText(f"{mar:.3f}")
        self.pitch_label.setText(f"{pitch:.1f}°")

        if resultado["fatiga_acumulada"]:

            self.fatigue_label.setText("SÍ • Límite 1.0s")
            self.fatigue_label.setObjectName("fatigue-warning")

        else:

            self.fatigue_label.setText("NO • Límite 1.5s")
            self.fatigue_label.setObjectName("fatigue-normal")

        self.fatigue_label.style().unpolish(self.fatigue_label)
        self.fatigue_label.style().polish(self.fatigue_label)

        self.threshold_label.setText(
            f"Umbral EAR: {self.analyzer.ear_umbral:.3f}"
        )

        self.graph_threshold_label.setText(
            f"UMBRAL: {self.analyzer.ear_umbral:.3f}"
        )

    # ACTUALIZAR GRÁFICA

    def _actualizar_grafica(self, ear):

        self.historial_ear.append(ear)

        if self.graph is not None:

            valores = list(self.historial_ear)
            self.curva_ear.setData(valores)

            self.linea_umbral.setValue(
                self.analyzer.ear_umbral
            )

    # ACTUALIZAR ESTADO DEL CONDUCTOR

    def _actualizar_semaforo(self, resultado):

        estado = resultado["estado"]
        duracion = resultado["duracion_evento"]

        estados = {
            "NORMAL": (
                "NORMAL",
                "#22DFA0",
                "Vigilia activa • Monitoreo estable"
            ),
            "FATIGA_TEMPRANA": (
                "FATIGA TEMPRANA",
                "#F59E0B",
                "Se detectaron señales de fatiga"
            ),
            "MICROSUEÑO": (
                "MICROSUEÑO",
                "#EF4444",
                "Cierre prolongado de los ojos detectado"
            ),
            "OBJETIVO_PERDIDO": (
                "OBJETIVO PERDIDO",
                "#829AB5",
                "No se detecta un rostro"
            )
        }

        titulo, color, descripcion = estados.get(
            estado,
            ("EN ESPERA", "#38BDF8", "Esperando datos biométricos")
        )

        self.state_label.setText(titulo)
        self.state_label.setStyleSheet(
            f"color: {color};"
        )

        self.state_description.setText(descripcion)

        self.graph_state.setText(titulo)
        self.graph_state.setStyleSheet(
            f"background-color: {color};"
            "color: #07111F;"
        )

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

        self.event_label.setText(
            f"EVENTO: {duracion:.1f}s"
        )

    # CALIBRACIÓN

    def _iniciar_calibracion(self):

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

            progreso = min(
                int((transcurrido / 3.0) * 100),
                99
            )

            self.calibration_progress.setValue(progreso)

        else:

            self.calibration_progress.setValue(100)

            self.calibration_button.setEnabled(True)
            self.calibration_button.setText(
                "Calibrar EAR Dinámico (3 s)"
            )

            self.threshold_label.setText(
                f"Umbral EAR: {self.analyzer.ear_umbral:.3f}"
            )

            self.graph_threshold_label.setText(
                f"UMBRAL: {self.analyzer.ear_umbral:.3f}"
            )

            self.inicio_calibracion = None

    # CAMBIO DE FUENTE

    def _on_fuente_cambiada(self, indice):

        fuente = self.source_select.currentData()

        self.source_changed.emit(fuente)

        self.status_label.setText("CAMBIANDO FUENTE")
        self.fps_label.setText("FPS: --")

        self.historial_ear.clear()
        self.ultimo_frame_tiempo = None

        if self.graph is not None:
            self.curva_ear.setData([])

        self.ultimo_incidente = None

    # REGISTRO DE INCIDENTES

    def _registrar_incidente(self, resultado):

        tipo = resultado["tipo_incidente"]

        if not resultado["nuevo_incidente"] or tipo is None:
            self.ultimo_incidente = None
            return

        if tipo == self.ultimo_incidente:
            return

        self.ultimo_incidente = tipo

        ahora = datetime.now()
        fecha = ahora.strftime("%Y-%m-%d")
        hora = ahora.strftime("%H:%M:%S")

        self.db.execute(
            """
            INSERT INTO incidentes (tipo, fecha, hora)
            VALUES (?, ?, ?)
            """,
            (tipo, fecha, hora)
        )

        self.db.commit()
        self._agregar_log(tipo, fecha, hora)

    def _agregar_log(self, tipo, fecha, hora):

        texto = f"{fecha}  |  {hora}  |  {tipo}"
        item = QListWidgetItem(texto)

        self.log_list.insertItem(0, item)

        while self.log_list.count() > 100:
            self.log_list.takeItem(
                self.log_list.count() - 1
            )

    def _cargar_logs(self):

        registros = self.db.execute(
            """
            SELECT tipo, fecha, hora
            FROM incidentes
            ORDER BY id DESC
            LIMIT 100
            """
        ).fetchall()

        for tipo, fecha, hora in registros:
            self._agregar_log(tipo, fecha, hora)

    def _limpiar_logs(self):

        self.db.execute("DELETE FROM incidentes")
        self.db.commit()

        self.log_list.clear()
        self.ultimo_incidente = None

    # MOSTRAR VIDEO

    def _mostrar_video(self, frame):

        h, w, ch = frame.shape
        bytes_per_line = ch * w

        q_img = QImage(
            frame.data,
            w,
            h,
            bytes_per_line,
            QImage.Format_BGR888
        ).copy()

        pixmap = QPixmap.fromImage(q_img)
        self.ultimo_pixmap = pixmap

        self.video_label.setPixmap(
            pixmap.scaled(
                self.video_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )

    # AJUSTAR VIDEO AL CAMBIAR TAMAÑO

    def resizeEvent(self, event):

        super().resizeEvent(event)

        if self.ultimo_pixmap is not None:

            self.video_label.setPixmap(
                self.ultimo_pixmap.scaled(
                    self.video_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
            )

    # CERRAR APLICACIÓN

    def closeEvent(self, event):

        self.db.close()
        event.accept()