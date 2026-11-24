import sqlite3
import time
from collections import deque
from datetime import datetime
from pathlib import Path
import numpy as np

from PySide6.QtCore import Qt, Slot, Signal, QUrl, QTimer, QSize
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtMultimedia import QSoundEffect, QMediaDevices
    AUDIO_DISPONIBLE = True
except ImportError:
    QSoundEffect = None
    QMediaDevices = None
    AUDIO_DISPONIBLE = False

try:
    import pyqtgraph as pg
    PYQTGRAPH_DISPONIBLE = True
except ImportError:
    pg = None
    PYQTGRAPH_DISPONIBLE = False

from src.analytics.temporal_buffer import DrowsinessAnalyzer
from src.ui.components import (
    AmbientGlassBackground,
    GlassCard,
    MetricCard,
    StatusBadgeIcon,
    crear_icono,
    crear_label_icono,
)
from src.ui.pages.reports_page import ReportsPage
from src.ui.pages.settings_page import SettingsPage
from src.ui.pages.about_page import AboutPage

class MainWindow(QMainWindow):

    source_changed = Signal(object)

    def __init__(self):
        super().__init__()

        self.setWindowTitle("VIGILANT v2.0 | Sistema de Monitoreo de Somnolencia con IA")
        self.setMinimumSize(1140, 700)
        self.resize(1380, 820)

        self.raiz_proyecto = Path(__file__).resolve().parents[2]
        self.analyzer = DrowsinessAnalyzer()

        self.historial_grafica = deque(maxlen=120)
        self._modo_grafica = None
        self.ultimo_pixmap = None
        self.inicio_calibracion = None
        self._tiempos_fps = deque(maxlen=20)
        self._contador_frames = 0
        self._ultimo_estilo_fatiga = None
        self._ultimo_estado_visual = None
        self._cerrando = False

        # Control de alertas sonoras
        self.audio_silenciado = False
        self.sonido_fatiga = None
        self.sonido_critico = None

        self._inicializar_base_datos()
        self._inicializar_audio()
        self._cargar_estilos()
        self._construir_ui()

        self.fuente_preferida = 1   # Preferencia inicial: Cámara USB
        self.fuente_activa = None
        self._reintentos_usb = 0
        self._inicializar_monitor_camaras()

    # ==========================================================
    # BASE DE DATOS
    # ==========================================================
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

    # ==========================================================
    # SISTEMA DE AUDIO (QSoundEffect)
    # ==========================================================
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
        if self.audio_silenciado or resultado["calibrando"] or resultado.get("mirada_desviada"):
            self._detener_alertas()
            return

        estado = resultado["estado"]

        if estado == DrowsinessAnalyzer.ESTADO_MICROSUEÑO:
            if self.sonido_fatiga is not None and self.sonido_fatiga.isPlaying():
                self.sonido_fatiga.stop()
            if self.sonido_critico is not None and not self.sonido_critico.isPlaying():
                self.sonido_critico.play()
            return

        if self.sonido_critico is not None and self.sonido_critico.isPlaying():
            self.sonido_critico.stop()

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
        ruta_style = self.raiz_proyecto / "assets" / "styles" / "style.qss"
        if ruta_style.exists():
            with open(ruta_style, "r", encoding="utf-8") as archivo:
                self.setStyleSheet(archivo.read())

    # ==========================================================
    # CONSTRUCCIÓN DE INTERFAZ (DARK LIQUID GLASS)
    # ==========================================================
    def _construir_ui(self):
        central = AmbientGlassBackground()
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. BARRA LATERAL DE NAVEGACIÓN
        root_layout.addWidget(self._construir_sidebar())

        # 2. ÁREA DERECHA (ENCABEZADO + PÁGINAS)
        workspace = QVBoxLayout()
        workspace.setContentsMargins(18, 12, 18, 14)
        workspace.setSpacing(12)

        workspace.addLayout(self._construir_header())

        divider = QFrame()
        divider.setObjectName("header-divider")
        divider.setFixedHeight(1)
        workspace.addWidget(divider)

        self.pages_stack = QStackedWidget()
        self.pages_stack.setStyleSheet("background: transparent;")

        self.home_page = self._construir_pagina_inicio()
        self.reports_page = ReportsPage(self.db)
        self.reports_page.historial_limpiado.connect(self._on_historial_limpiado_externo)

        self.settings_page = SettingsPage(self.analyzer)
        self.settings_page.configuracion_actualizada.connect(self._on_configuracion_actualizada)
        self.settings_page.volumen_cambiado.connect(self._on_volumen_cambiado)

        self.about_page = AboutPage()

        self.pages_stack.addWidget(self.home_page)
        self.pages_stack.addWidget(self.reports_page)
        self.pages_stack.addWidget(self.settings_page)
        self.pages_stack.addWidget(self.about_page)

        self.pages_stack.addWidget(self.home_page)
        self.pages_stack.addWidget(self.reports_placeholder)
        self.pages_stack.addWidget(self.settings_placeholder)
        self.pages_stack.addWidget(self.about_placeholder)

        workspace.addWidget(self.pages_stack, 1)
        root_layout.addLayout(workspace, 1)

        self._cargar_logs()

    def _construir_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(168)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(8)

        # Logo superior
        brand_box = QVBoxLayout()
        brand_box.setSpacing(4)
        brand_box.setAlignment(Qt.AlignHCenter)

        logo_icon = crear_label_icono("logo", "#38BDF8", 46)
        logo_icon.setAlignment(Qt.AlignCenter)

        brand_name = QLabel("VIGILANT")
        brand_name.setObjectName("sidebar-brand")
        brand_name.setAlignment(Qt.AlignCenter)

        brand_ver = QLabel("v2.0 • IA ONNX")
        brand_ver.setObjectName("sidebar-version")
        brand_ver.setAlignment(Qt.AlignCenter)

        brand_box.addWidget(logo_icon, 0, Qt.AlignHCenter)
        brand_box.addWidget(brand_name)
        brand_box.addWidget(brand_ver)

        layout.addLayout(brand_box)
        layout.addSpacing(14)

        # Botones de navegación
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = []

        items = [
            ("Inicio", "home", 0),
            ("Reportes", "reports", 1),
            ("Configuración", "settings", 2),
            ("Acerca de", "info", 3),
        ]

        for texto, icono_nombre, indice in items:
            btn = QPushButton(f"  {texto}")
            btn.setObjectName("nav-button")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setIcon(crear_icono(icono_nombre, "#CBD5E1", 17))
            btn.setIconSize(QSize(17, 17))
            btn.clicked.connect(lambda _=False, idx=indice: self._cambiar_pagina(idx))

            self.nav_group.addButton(btn, indice)
            self.nav_buttons.append(btn)
            layout.addWidget(btn)

        self.nav_buttons[0].setChecked(True)
        layout.addStretch()

        return sidebar

    def _cambiar_pagina(self, indice):
        self.pages_stack.setCurrentIndex(indice)
        if 0 <= indice < len(self.nav_buttons):
            self.nav_buttons[indice].setChecked(True)
        if indice == 1:
            self.reports_page.recargar_datos()
        elif indice == 2:
            self.settings_page.sincronizar_desde_analyzer()

    def _construir_header(self):
        header = QHBoxLayout()
        header.setSpacing(10)

        titulo_col = QVBoxLayout()
        titulo_col.setSpacing(1)

        logo = QLabel("VIGILANT")
        logo.setObjectName("logo")

        subtitulo = QLabel("Sistema de Monitoreo de Somnolencia  |  v2.0 (CNN ONNX)")
        subtitulo.setObjectName("subtitle")

        titulo_col.addWidget(logo)
        titulo_col.addWidget(subtitulo)

        header.addLayout(titulo_col)
        header.addStretch()

        source_title = QLabel("Fuente:")
        source_title.setObjectName("muted")
        header.addWidget(source_title)

        self.source_select = QComboBox()
        self.source_select.setObjectName("source-select")
        self.source_select.addItem("Cámara USB", 1)
        self.source_select.addItem("Cámara integrada", 0)
        self.source_select.addItem(
            "Video Benchmark",
            str(self.raiz_proyecto / "assets" / "video" / "benchmark.mp4")
        )
        self.source_select.currentIndexChanged.connect(self._on_fuente_cambiada)
        header.addWidget(self.source_select)

        self.audio_button = QPushButton("AUDIO: ON")
        self.audio_button.setObjectName("audio-on")
        self.audio_button.setCursor(Qt.PointingHandCursor)
        self.audio_button.clicked.connect(self._alternar_audio)
        header.addWidget(self.audio_button)

        self.status_label = QLabel("● EN ESPERA")
        self.status_label.setObjectName("status-pill")
        self.status_label.setAlignment(Qt.AlignCenter)
        header.addWidget(self.status_label)

        self.fps_label = QLabel("FPS: --")
        self.fps_label.setObjectName("fps-label")
        self.fps_label.setAlignment(Qt.AlignCenter)
        header.addWidget(self.fps_label)

        return header

    def _construir_pagina_inicio(self):
        page = QWidget()
        page.setStyleSheet("background: transparent;")

        body = QHBoxLayout(page)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(14)

        # ======================================================
        # COLUMNA IZQUIERDA (VISOR + OSCILOSCOPIO)
        # ======================================================
        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        # --- TARJETA 1: VISOR DE MONITOREO FACIAL ---
        video_card = GlassCard(radius=14, bg_alpha=172)
        video_layout = QVBoxLayout(video_card)
        video_layout.setContentsMargins(14, 12, 14, 12)
        video_layout.setSpacing(8)

        video_header = QHBoxLayout()
        video_header.setSpacing(8)
        video_header.addWidget(crear_label_icono("camera", "#93C5FD", 18))

        vh_text = QVBoxLayout()
        vh_text.setSpacing(1)
        video_title = QLabel("Visor de Monitoreo Facial")
        video_title.setObjectName("section")
        video_sub = QLabel("Detección en tiempo real • MediaPipe Face Mesh + CNN ONNX")
        video_sub.setObjectName("muted")
        vh_text.addWidget(video_title)
        vh_text.addWidget(video_sub)

        video_header.addLayout(vh_text, 1)

        self.event_label = QLabel("EVENTO: 0.0s")
        self.event_label.setObjectName("event-pill")
        video_header.addWidget(self.event_label)

        self.camera_label = QLabel("● CONECTANDO...")
        self.camera_label.setObjectName("camera-pill")
        video_header.addWidget(self.camera_label)

        video_layout.addLayout(video_header)

        video_frame = QFrame()
        video_frame.setObjectName("video-frame")
        vf_layout = QVBoxLayout(video_frame)
        vf_layout.setContentsMargins(3, 3, 3, 3)

        self.video_label = QLabel("Esperando señal de cámara...")
        self.video_label.setObjectName("video")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(460, 230)
        self.video_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        vf_layout.addWidget(self.video_label)

        video_layout.addWidget(video_frame, 1)
        left_col.addWidget(video_card, 3)

        # --- TARJETA 2: OSCILOSCOPIO DE PROBABILIDAD DE CIERRE ---
        graph_card = GlassCard(radius=14, bg_alpha=172)
        graph_layout = QVBoxLayout(graph_card)
        graph_layout.setContentsMargins(14, 12, 14, 12)
        graph_layout.setSpacing(8)

        graph_header = QHBoxLayout()
        graph_header.setSpacing(8)
        graph_header.addWidget(crear_label_icono("pulse", "#38BDF8", 18))

        self.graph_title = QLabel("Osciloscopio de Probabilidad de Cierre")
        self.graph_title.setObjectName("section")
        graph_header.addWidget(self.graph_title, 1)

        self.graph_threshold_label = QLabel(
            f"Umbral: {self.analyzer.prob_umbral_cierre * 100:.0f}%"
        )
        self.graph_threshold_label.setObjectName("threshold-pill")
        graph_header.addWidget(self.graph_threshold_label)

        graph_layout.addLayout(graph_header)

        if PYQTGRAPH_DISPONIBLE:
            self.graph = pg.PlotWidget()
            self.graph.setBackground("#0D1526")
            self.graph.showGrid(x=True, y=True, alpha=0.16)
            self.graph.setLabel("left", "Probabilidad (%)", color="#94A3B8")
            self.graph.setLabel("bottom", "Muestras", color="#94A3B8")
            self.graph.setYRange(0, 105)
            self.graph.setMouseEnabled(x=False, y=False)
            self.graph.setMenuEnabled(False)
            self.graph.getAxis("left").setTextPen("#94A3B8")
            self.graph.getAxis("bottom").setTextPen("#94A3B8")
            self.graph.getAxis("left").setPen(pg.mkPen(color=(148, 163, 184, 55)))
            self.graph.getAxis("bottom").setPen(pg.mkPen(color=(148, 163, 184, 55)))

            self.curva_principal = self.graph.plot(
                pen=pg.mkPen("#38BDF8", width=2.2),
                fillLevel=0,
                brush=pg.mkBrush(56, 189, 248, 42),
            )
            self.linea_umbral = pg.InfiniteLine(
                pos=self.analyzer.prob_umbral_cierre * 100.0,
                angle=0,
                pen=pg.mkPen("#EF4444", width=1.8, style=Qt.DashLine),
            )
            self.graph.addItem(self.linea_umbral)
            graph_layout.addWidget(self.graph, 1)
        else:
            self.graph = None
            self.curva_principal = None
            self.linea_umbral = None
            msg = QLabel("Instala pyqtgraph para visualizar el osciloscopio en tiempo real")
            msg.setObjectName("muted")
            msg.setAlignment(Qt.AlignCenter)
            graph_layout.addWidget(msg, 1)

        # Banner inferior de estado
        self.status_banner = QFrame()
        self.status_banner.setObjectName("status-banner")
        banner_layout = QVBoxLayout(self.status_banner)
        banner_layout.setContentsMargins(12, 8, 12, 8)
        banner_layout.setSpacing(1)

        self.graph_state = QLabel("NORMAL")
        self.graph_state.setObjectName("banner-title")
        self.graph_state.setAlignment(Qt.AlignCenter)

        self.graph_description = QLabel("Vigilia activa • No se detecta somnolencia")
        self.graph_description.setObjectName("banner-desc")
        self.graph_description.setAlignment(Qt.AlignCenter)

        banner_layout.addWidget(self.graph_state)
        banner_layout.addWidget(self.graph_description)
        graph_layout.addWidget(self.status_banner)

        left_col.addWidget(graph_card, 2)
        body.addLayout(left_col, 3)

        # ======================================================
        # COLUMNA DERECHA (ESTADO + TELEMETRÍA + CALIBRACIÓN + LOGS)
        # ======================================================
        right_col = QVBoxLayout()
        right_col.setSpacing(8)

        # --- TARJETA 1: ESTADO DEL CONDUCTOR ---
        self.state_card = GlassCard(radius=14, bg_alpha=178, glow_color="#22C55E")
        state_layout = QVBoxLayout(self.state_card)
        state_layout.setContentsMargins(14, 10, 14, 10)
        state_layout.setSpacing(8)

        state_header = QHBoxLayout()
        state_header.setSpacing(8)
        state_header.addWidget(crear_label_icono("pulse", "#CBD5E1", 17))
        state_title = QLabel("Estado del Conductor")
        state_title.setObjectName("section")
        state_header.addWidget(state_title, 1)
        state_layout.addLayout(state_header)

        state_body = QHBoxLayout()
        state_body.setSpacing(12)
        state_body.setContentsMargins(6, 0, 6, 0)

        self.state_badge = StatusBadgeIcon(size=44)
        state_body.addWidget(self.state_badge)

        state_text = QVBoxLayout()
        state_text.setSpacing(2)
        self.state_label = QLabel("EN ESPERA")
        self.state_label.setObjectName("state-title")
        self.state_description = QLabel("Esperando datos biométricos")
        self.state_description.setObjectName("state-description")
        self.state_description.setWordWrap(True)

        state_text.addWidget(self.state_label)
        state_text.addWidget(self.state_description)
        state_body.addLayout(state_text, 1)

        state_layout.addLayout(state_body)
        right_col.addWidget(self.state_card)

        # --- TARJETA 2: TELEMETRÍA BIOMÉTRICA (GRID 2x2) ---
        metrics_card = GlassCard(radius=14, bg_alpha=172)
        metrics_layout = QVBoxLayout(metrics_card)
        metrics_layout.setContentsMargins(14, 10, 14, 10)
        metrics_layout.setSpacing(8)

        m_header = QHBoxLayout()
        m_header.setSpacing(8)
        m_header.addWidget(crear_label_icono("reports", "#93C5FD", 17))
        m_title = QLabel("Telemetría Biométrica")
        m_title.setObjectName("section")
        m_header.addWidget(m_title, 1)
        metrics_layout.addLayout(m_header)

        metrics_grid = QGridLayout()
        metrics_grid.setSpacing(8)

        self.card_ai = MetricCard(
            "IA OJOS (CNN)",
            "--%",
            f">= {self.analyzer.prob_umbral_cierre * 100:.0f}%",
            "eye",
            "#2563EB",
        )
        self.card_ear = MetricCard(
            "EAR (REF.)",
            "0.000",
            f"< {self.analyzer.ear_umbral:.3f}",
            "ear",
            "#8B5CF6",
        )
        self.card_mar = MetricCard(
            "MAR (BOCA)",
            "0.000",
            f"> {self.analyzer.mar_umbral:.3f}",
            "mouth",
            "#22C55E",
        )
        self.card_pitch = MetricCard(
            "PITCH",
            "0.0°",
            f"< {self.analyzer.pitch_umbral:.1f}°",
            "pulse",
            "#F59E0B",
        )

        metrics_grid.addWidget(self.card_ai, 0, 0)
        metrics_grid.addWidget(self.card_ear, 0, 1)
        metrics_grid.addWidget(self.card_mar, 1, 0)
        metrics_grid.addWidget(self.card_pitch, 1, 1)
        metrics_layout.addLayout(metrics_grid)

        sep = QFrame()
        sep.setObjectName("inner-separator")
        sep.setFixedHeight(1)
        metrics_layout.addWidget(sep)

        fatigue_row = QHBoxLayout()
        fatigue_title = QLabel("Fatiga reciente (60s)")
        fatigue_title.setObjectName("metric-title")

        self.fatigue_label = QLabel("NO • Límite 1.5s")
        self.fatigue_label.setObjectName("fatigue-normal")
        self.fatigue_label.setAlignment(Qt.AlignCenter)

        fatigue_row.addWidget(fatigue_title, 1)
        fatigue_row.addWidget(self.fatigue_label)
        metrics_layout.addLayout(fatigue_row)

        right_col.addWidget(metrics_card)

        # --- TARJETA 3: CALIBRACIÓN DINÁMICA ---
        cal_card = GlassCard(radius=14, bg_alpha=172)
        cal_layout = QVBoxLayout(cal_card)
        cal_layout.setContentsMargins(14, 10, 14, 10)
        cal_layout.setSpacing(6)

        cal_header = QHBoxLayout()
        cal_header.setSpacing(8)
        cal_header.addWidget(crear_label_icono("target", "#93C5FD", 17))
        cal_title = QLabel("Calibración Dinámica (Postura y EAR)")
        cal_title.setObjectName("section")
        cal_header.addWidget(cal_title, 1)

        self.calibration_button = QPushButton("Calibrar (3 s)")
        self.calibration_button.setObjectName("calibration-button")
        self.calibration_button.setCursor(Qt.PointingHandCursor)
        self.calibration_button.clicked.connect(self._iniciar_calibracion)
        cal_header.addWidget(self.calibration_button)

        cal_layout.addLayout(cal_header)

        self.calibration_progress = QProgressBar()
        self.calibration_progress.setObjectName("calibration-progress")
        self.calibration_progress.setRange(0, 100)
        self.calibration_progress.setValue(0)
        self.calibration_progress.setFormat("Listo para calibrar")
        cal_layout.addWidget(self.calibration_progress)

        self.threshold_label = QLabel(
            f"Pitch: {self.analyzer.pitch_umbral:.1f}°  |  EAR resp.: {self.analyzer.ear_umbral:.3f}"
        )
        self.threshold_label.setObjectName("muted")
        cal_layout.addWidget(self.threshold_label)

        right_col.addWidget(cal_card)

        # --- TARJETA 4: HISTORIAL DE INCIDENTES ---
        log_card = GlassCard(radius=14, bg_alpha=172)
        log_layout = QVBoxLayout(log_card)
        log_layout.setContentsMargins(14, 10, 14, 10)
        log_layout.setSpacing(6)

        log_header = QHBoxLayout()
        log_header.setSpacing(8)
        log_header.addWidget(crear_label_icono("history", "#CBD5E1", 17))
        log_title = QLabel("Historial de Incidentes")
        log_title.setObjectName("section")
        log_header.addWidget(log_title, 1)

        ver_todo_btn = QPushButton("Ver todo →")
        ver_todo_btn.setObjectName("link-button")
        ver_todo_btn.setCursor(Qt.PointingHandCursor)
        ver_todo_btn.clicked.connect(lambda: self._cambiar_pagina(1))
        log_header.addWidget(ver_todo_btn)

        clear_button = QPushButton("Limpiar")
        clear_button.setObjectName("clear-button")
        clear_button.setCursor(Qt.PointingHandCursor)
        clear_button.clicked.connect(self._limpiar_logs)
        log_header.addWidget(clear_button)

        log_layout.addLayout(log_header)

        self.log_list = QListWidget()
        self.log_list.setObjectName("log-list")
        self.log_list.setMinimumHeight(72)
        log_layout.addWidget(self.log_list, 1)

        right_col.addWidget(log_card, 1)
        body.addLayout(right_col, 2)

        return page

   
    # ==========================================================
    # RECIBIR DATOS DEL VIDEOWORKER
    # ==========================================================
    @Slot(np.ndarray, float, float, float, float, float)
    def actualizar_frame(self, frame, ear, mar, pitch, yaw, prob_cierre):
        if self._cerrando:
            return

        self._actualizar_fps()
        resultado = self.analyzer.evaluar(ear, mar, pitch, yaw, prob_cierre)

        if ear >= 0:
            self._actualizar_metricas(ear, mar, pitch, resultado)
            self._actualizar_grafica(resultado)
            self._actualizar_calibracion(resultado["calibrando"])
            self._registrar_incidente(resultado)
        else:
            self.card_ai.value_label.setText("--")
            self.card_ear.value_label.setText("--")
            self.card_mar.value_label.setText("--")
            self.card_pitch.value_label.setText("--")
            self.fatigue_label.setText("SIN ROSTRO")
            self._ultimo_estilo_fatiga = None

        self._actualizar_semaforo(resultado)
        self._gestionar_alertas_sonoras(resultado)
        self._mostrar_video(frame)

    

    def _actualizar_fps(self):
        ahora = time.perf_counter()
        self._tiempos_fps.append(ahora)
        if len(self._tiempos_fps) >= 2:
            span = self._tiempos_fps[-1] - self._tiempos_fps[0]
            if span > 0:
                fps = (len(self._tiempos_fps) - 1) / span
                self.fps_label.setText(f"FPS: {fps:.1f}")

    # ==========================================================
    # MÉTRICAS Y GRÁFICA
    # ==========================================================
    def _actualizar_metricas(self, ear, mar, pitch, resultado):
        if resultado["modo_ojos"] == "IA_CNN" and resultado["prob_cierre_ema"] >= 0:
            self.card_ai.value_label.setText(f"{resultado['prob_cierre_ema'] * 100:.0f}%")
            self.card_ai.condition_label.setText(
                f">= {self.analyzer.prob_umbral_cierre * 100:.0f}% (ACTIVA)"
            )
        else:
            self.card_ai.value_label.setText("OFF")
            self.card_ai.condition_label.setText("Respaldo EAR")

        self.card_ear.value_label.setText(f"{ear:.3f}")
        self.card_mar.value_label.setText(f"{mar:.3f}")
        self.card_pitch.value_label.setText(f"{pitch:.1f}°")

        estilo_fatiga = "fatigue-warning" if resultado["fatiga_acumulada"] else "fatigue-normal"
        if estilo_fatiga != self._ultimo_estilo_fatiga:
            self._ultimo_estilo_fatiga = estilo_fatiga
            self.fatigue_label.setText(
                "SÍ • Límite 1.0s" if resultado["fatiga_acumulada"] else "NO • Límite 1.5s"
            )
            self.fatigue_label.setObjectName(estilo_fatiga)
            self.fatigue_label.style().unpolish(self.fatigue_label)
            self.fatigue_label.style().polish(self.fatigue_label)

        self._sincronizar_umbrales()

    def _sincronizar_umbrales(self):
        umbral_ear = self.analyzer.ear_umbral
        umbral_pitch = self.analyzer.pitch_umbral
        self.card_ear.condition_label.setText(f"< {umbral_ear:.3f}")
        self.card_pitch.condition_label.setText(f"< {umbral_pitch:.1f}°")
        self.threshold_label.setText(
            f"Pitch: {umbral_pitch:.1f}°  |  EAR resp.: {umbral_ear:.3f}"
        )

    def _configurar_modo_grafica(self, modo):
        if modo == self._modo_grafica:
            return

        self._modo_grafica = modo
        self.historial_grafica.clear()

        if modo == "IA_CNN":
            umbral_pct = self.analyzer.prob_umbral_cierre * 100.0
            self.graph_title.setText("Osciloscopio de Probabilidad de Cierre")
            self.graph_threshold_label.setText(f"Umbral: {umbral_pct:.0f}%")
            if self.graph is not None:
                self.graph.setLabel("left", "Probabilidad (%)", color="#94A3B8")
                self.graph.setYRange(0, 105)
                self.linea_umbral.setValue(umbral_pct)
        else:
            self.graph_title.setText("Osciloscopio EAR (Modo Respaldo)")
            self.graph_threshold_label.setText(f"Umbral EAR: {self.analyzer.ear_umbral:.3f}")
            if self.graph is not None:
                self.graph.setLabel("left", "EAR", color="#94A3B8")
                self.graph.setYRange(0, 0.5)
                self.linea_umbral.setValue(self.analyzer.ear_umbral)

    def _actualizar_grafica(self, resultado):
        modo = resultado["modo_ojos"]
        self._configurar_modo_grafica(modo)

        if modo == "IA_CNN" and resultado["prob_cierre_ema"] >= 0:
            valor = resultado["prob_cierre_ema"] * 100.0
            umbral_linea = self.analyzer.prob_umbral_cierre * 100.0
        else:
            valor = max(0.0, resultado["ear_ema"])
            umbral_linea = self.analyzer.ear_umbral
            self.graph_threshold_label.setText(f"Umbral EAR: {umbral_linea:.3f}")

        self.historial_grafica.append(valor)
        self._contador_frames += 1
        if self.graph is not None and (self._contador_frames % 2 == 0):
            self.curva_principal.setData(list(self.historial_grafica))
            self.linea_umbral.setValue(umbral_linea)

    # ==========================================================
    # SEMÁFORO DE ESTADO (CON CACHE VISUAL PARA NO PENALIZAR FPS)
    # ==========================================================
    def _actualizar_semaforo(self, resultado):
        self.event_label.setText(f"EVENTO: {resultado['duracion_evento']:.1f}s")

        if resultado["calibrando"]:
            clave = "CALIBRANDO"
        elif resultado.get("mirada_desviada"):
            clave = "MIRADA_DESVIADA"
        else:
            clave = resultado["estado"]

        if clave == self._ultimo_estado_visual:
            return
        self._ultimo_estado_visual = clave

        # (titulo, color, color_fin_banner, color_texto_banner, tipo_icono, descripcion)
        config = {
            "NORMAL": (
                "NORMAL",
                "#22C55E",
                "#10B981",
                "#052014",
                "check",
                "Vigilia activa • Monitoreo estable",
            ),
            "FATIGA_TEMPRANA": (
                "FATIGA TEMPRANA",
                "#F59E0B",
                "#D97706",
                "#1F1300",
                "alert",
                "Señales de fatiga detectadas • Límite estricto (1.0 s)",
            ),
            "MICROSUEÑO": (
                "MICROSUEÑO",
                "#EF4444",
                "#DC2626",
                "#FFFFFF",
                "alert",
                "¡ALERTA CRÍTICA! Cierre prolongado de ojos detectado",
            ),
            "CALIBRANDO": (
                "CALIBRANDO",
                "#38BDF8",
                "#2563EB",
                "#061426",
                "info",
                "Mantenga la vista al frente con ojos abiertos (3 s)",
            ),
            "MIRADA_DESVIADA": (
                "MIRADA DESVIADA",
                "#38BDF8",
                "#2563EB",
                "#061426",
                "info",
                "Giro lateral detectado • Monitoreo en pausa",
            ),
            "OBJETIVO_PERDIDO": (
                "OBJETIVO PERDIDO",
                "#64748B",
                "#475569",
                "#F8FAFC",
                "info",
                "No se detecta un rostro en cámara",
            ),
        }

        titulo, color, color2, txt_banner, icono, desc = config.get(
            clave,
            ("EN ESPERA", "#38BDF8", "#2563EB", "#061426", "info", "Esperando datos biométricos"),
        )

        self.state_card.set_glow_color(color)
        self.state_badge.set_estado(color, icono)
        self.state_label.setText(titulo)
        self.state_label.setStyleSheet(f"color: {color};")
        self.state_description.setText(desc)

        self.status_banner.setStyleSheet(
            f"QFrame#status-banner {{"
            f"border-radius: 11px;"
            f"background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {color}, stop:1 {color2});"
            f"}}"
        )
        self.graph_state.setText(titulo)
        self.graph_state.setStyleSheet(f"color: {txt_banner}; background: transparent;")
        self.graph_description.setText(desc)
        self.graph_description.setStyleSheet(f"color: {txt_banner}; background: transparent;")

        self.status_label.setText(f"● {titulo}")
        self.status_label.setStyleSheet(
            f"color: {color};"
            f"border: 1px solid {color};"
            "background-color: rgba(15, 23, 42, 0.78);"
            "border-radius: 9px;"
            "padding: 6px 12px;"
            "font-size: 11px;"
            "font-weight: 700;"
        )

    # ==========================================================
    # CALIBRACIÓN DINÁMICA
    # ==========================================================
    def _iniciar_calibracion(self):
        self._detener_alertas()
        self.analyzer.iniciar_calibracion()
        self.inicio_calibracion = time.time()
        self.calibration_progress.setValue(0)
        self.calibration_progress.setFormat("Calibrando... %p%")
        self.calibration_button.setEnabled(False)
        self.calibration_button.setText("Calibrando...")

    def _actualizar_calibracion(self, calibrando):
        if self.inicio_calibracion is None:
            return

        if calibrando:
            transcurrido = time.time() - self.inicio_calibracion
            self.calibration_progress.setValue(min(int((transcurrido / 3.0) * 100), 99))
        else:
            self.calibration_progress.setValue(100)
            self.calibration_progress.setFormat("Calibrado • 100%")
            self.calibration_button.setEnabled(True)
            self.calibration_button.setText("Calibrar (3 s)")
            self._sincronizar_umbrales()
            self.inicio_calibracion = None

    # ==========================================================
    # FUENTES DE VIDEO Y RECONEXIÓN USB EN CALIENTE
    # ==========================================================
    def _on_fuente_cambiada(self, indice):
        fuente = self.source_select.currentData()

        if isinstance(fuente, str) and not Path(fuente).exists():
            indice_actual = self.source_select.findData(self.fuente_activa)
            if indice_actual != -1:
                self.source_select.blockSignals(True)
                self.source_select.setCurrentIndex(indice_actual)
                self.source_select.blockSignals(False)
            self.camera_label.setText("● FALTA assets/video/benchmark.mp4")
            return

        self._detener_alertas()
        self.fuente_preferida = fuente
        self._reintentos_usb = 0
        if hasattr(self, "_timer_reconexion"):
            self._timer_reconexion.stop()
        self.source_changed.emit(fuente)

        self._ultimo_estado_visual = None
        self.status_label.setText("● CAMBIANDO FUENTE")
        self.fps_label.setText("FPS: --")
        self.historial_grafica.clear()
        self._tiempos_fps.clear()

        if self.graph is not None:
            self.curva_principal.setData([])

    @Slot(object)
    def sincronizar_fuente_activa(self, fuente_real):
        cambio_real = fuente_real != self.fuente_activa
        self.fuente_activa = fuente_real

        if cambio_real:
            self.historial_grafica.clear()
            self._tiempos_fps.clear()
            if self.graph is not None:
                self.curva_principal.setData([])

        if fuente_real == 1:
            self._reintentos_usb = 0
            self._timer_reconexion.stop()
        elif (
            fuente_real == 0
            and self.fuente_preferida == 1
            and QMediaDevices is not None
            and len(QMediaDevices.videoInputs()) >= 2
            and self._reintentos_usb < 3
        ):
            self._reintentos_usb += 1
            self._timer_reconexion.start(1000)

        if fuente_real is None:
            self.camera_label.setText("● SIN CÁMARA DISPONIBLE")
            self.status_label.setText("● SIN SEÑAL")
            return

        indice = self.source_select.findData(fuente_real)
        if indice != -1:
            self.source_select.blockSignals(True)
            self.source_select.setCurrentIndex(indice)
            self.source_select.blockSignals(False)

        if isinstance(fuente_real, str):
            self.camera_label.setText("● VIDEO BENCHMARK")
        else:
            nombre = self.source_select.currentText()
            self.camera_label.setText(f"● {nombre} Activa")

    def _inicializar_monitor_camaras(self):
        self._timer_reconexion = QTimer(self)
        self._timer_reconexion.setSingleShot(True)
        self._timer_reconexion.timeout.connect(self._reintentar_camara_preferida)

        if QMediaDevices is not None:
            self.media_devices = QMediaDevices(self)
            self.media_devices.videoInputsChanged.connect(
                self._on_dispositivos_video_cambiados
            )

    def _on_dispositivos_video_cambiados(self):
        if self._cerrando or QMediaDevices is None:
            return

        num_camaras = len(QMediaDevices.videoInputs())

        if self.fuente_activa == 1 and num_camaras < 2:
            self._timer_reconexion.stop()
            self._reintentos_usb = 0
            self.source_changed.emit(0)
            return

        if self.fuente_preferida == 1 and self.fuente_activa != 1 and num_camaras >= 2:
            self._reintentos_usb = 0
            self._timer_reconexion.start(1200)
        elif (
            self.fuente_activa is None
            and isinstance(self.fuente_preferida, int)
            and num_camaras >= 1
        ):
            self._reintentos_usb = 0
            self._timer_reconexion.start(1200)

    def _reintentar_camara_preferida(self):
        if self._cerrando:
            return

        if self.fuente_preferida == 1 and self.fuente_activa != 1:
            self.source_changed.emit(1)
        elif self.fuente_activa is None and isinstance(self.fuente_preferida, int):
            self.source_changed.emit(self.fuente_preferida)

    # ==========================================================
    # REGISTRO DE INCIDENTES
    # ==========================================================
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
        colores = {
            "Microsueño": "#EF4444",
            "Bostezo Prolongado": "#F59E0B",
            "Cabeceo": "#38BDF8",
        }
        color = colores.get(tipo, "#22C55E")
        item = QListWidgetItem(
            crear_icono("dot", color, 12),
            f"{fecha}  |  {hora}   —   {tipo}"
        )
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

    # ==========================================================
    # VISUALIZACIÓN DE VIDEO Y CIERRE
    # ==========================================================
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
        self._timer_reconexion.stop()
        self._detener_alertas()
        self.db.close()
        event.accept()