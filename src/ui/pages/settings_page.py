from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.ui.components import GlassCard, crear_label_icono


class SettingsPage(QWidget):
    """Ajuste en vivo de umbrales del analizador y volúmenes de alerta."""

    configuracion_actualizada = Signal()
    volumen_cambiado = Signal(float, float)  # (vol_fatiga, vol_critico) en [0.0, 1.0]

    def __init__(self, analyzer, parent=None):
        super().__init__(parent)
        self.analyzer = analyzer
        self._bloqueando = False
        self.setStyleSheet("background: transparent;")
        self._construir_ui()
        self.sincronizar_desde_analyzer()

    def _construir_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setObjectName("page-scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.viewport().setStyleSheet("background: transparent;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(12)

        # --- TARJETA 1: MODELO IA Y DETECCIÓN DE MICROSUEÑO ---
        card_ia = GlassCard(radius=14, bg_alpha=172)
        ia_layout = QVBoxLayout(card_ia)
        ia_layout.setContentsMargins(16, 14, 16, 14)
        ia_layout.setSpacing(10)

        h1 = QHBoxLayout()
        h1.addWidget(crear_label_icono("eye", "#38BDF8", 18))
        lbl1 = QLabel("Detección Ocular (CNN ONNX) y Tiempos de Microsueño")
        lbl1.setObjectName("section")
        h1.addWidget(lbl1, 1)
        ia_layout.addLayout(h1)

        grid1 = QGridLayout()
        grid1.setHorizontalSpacing(16)
        grid1.setVerticalSpacing(10)

        # Umbral probabilidad CNN
        lbl_cnn = QLabel("Umbral de cierre ocular IA (P >= %):")
        lbl_cnn.setObjectName("metric-title")
        self.slider_cnn = QSlider(Qt.Horizontal)
        self.slider_cnn.setRange(35, 75)
        self.slider_cnn.setSingleStep(1)
        self.lbl_cnn_val = QLabel("50%  (libera < 35%)")
        self.lbl_cnn_val.setObjectName("settings-value")
        self.slider_cnn.valueChanged.connect(self._on_cambio_parametro)

        grid1.addWidget(lbl_cnn, 0, 0)
        grid1.addWidget(self.slider_cnn, 0, 1)
        grid1.addWidget(self.lbl_cnn_val, 0, 2)

        # Tiempo microsueño normal
        lbl_t_norm = QLabel("Tiempo de microsueño en estado normal (s):")
        lbl_t_norm.setObjectName("metric-title")
        self.spin_t_normal = QDoubleSpinBox()
        self.spin_t_normal.setObjectName("settings-spin")
        self.spin_t_normal.setRange(0.8, 3.0)
        self.spin_t_normal.setSingleStep(0.1)
        self.spin_t_normal.setSuffix(" s")
        self.spin_t_normal.valueChanged.connect(self._on_cambio_parametro)

        grid1.addWidget(lbl_t_norm, 1, 0)
        grid1.addWidget(self.spin_t_normal, 1, 1, 1, 2)

        # Tiempo microsueño con fatiga
        lbl_t_fat = QLabel("Tiempo de microsueño con fatiga reciente (s):")
        lbl_t_fat.setObjectName("metric-title")
        self.spin_t_fatiga = QDoubleSpinBox()
        self.spin_t_fatiga.setObjectName("settings-spin")
        self.spin_t_fatiga.setRange(0.5, 2.5)
        self.spin_t_fatiga.setSingleStep(0.1)
        self.spin_t_fatiga.setSuffix(" s")
        self.spin_t_fatiga.valueChanged.connect(self._on_cambio_parametro)

        grid1.addWidget(lbl_t_fat, 2, 0)
        grid1.addWidget(self.spin_t_fatiga, 2, 1, 1, 2)

        ia_layout.addLayout(grid1)
        layout.addWidget(card_ia)

        # --- TARJETA 2: GEOMETRÍA FACIAL (BOSTEZO, CABECEO Y GIRO LATERAL) ---
        card_geo = GlassCard(radius=14, bg_alpha=172)
        geo_layout = QVBoxLayout(card_geo)
        geo_layout.setContentsMargins(16, 14, 16, 14)
        geo_layout.setSpacing(10)

        h2 = QHBoxLayout()
        h2.addWidget(crear_label_icono("target", "#8B5CF6", 18))
        lbl2 = QLabel("Sensibilidad Geométrica y Filtro de Distracción")
        lbl2.setObjectName("section")
        h2.addWidget(lbl2, 1)
        geo_layout.addLayout(h2)

        grid2 = QGridLayout()
        grid2.setHorizontalSpacing(16)
        grid2.setVerticalSpacing(10)

        # Límite de giro lateral (Yaw)
        lbl_yaw = QLabel("Ángulo límite de giro lateral (Mirada Desviada):")
        lbl_yaw.setObjectName("metric-title")
        self.spin_yaw = QSpinBox()
        self.spin_yaw.setObjectName("settings-spin")
        self.spin_yaw.setRange(15, 45)
        self.spin_yaw.setSuffix("°")
        self.spin_yaw.valueChanged.connect(self._on_cambio_parametro)
        grid2.addWidget(lbl_yaw, 0, 0)
        grid2.addWidget(self.spin_yaw, 0, 1)

        # Umbral MAR (bostezo)
        lbl_mar = QLabel("Umbral de bostezo (MAR boca >):")
        lbl_mar.setObjectName("metric-title")
        self.spin_mar = QDoubleSpinBox()
        self.spin_mar.setObjectName("settings-spin")
        self.spin_mar.setRange(0.45, 0.85)
        self.spin_mar.setSingleStep(0.02)
        self.spin_mar.setDecimals(2)
        self.spin_mar.valueChanged.connect(self._on_cambio_parametro)
        grid2.addWidget(lbl_mar, 1, 0)
        grid2.addWidget(self.spin_mar, 1, 1)

        # Umbral Pitch (cabeceo)
        lbl_pitch = QLabel("Umbral de cabeceo hacia abajo (Pitch <):")
        lbl_pitch.setObjectName("metric-title")
        self.spin_pitch = QDoubleSpinBox()
        self.spin_pitch.setObjectName("settings-spin")
        self.spin_pitch.setRange(-32.0, -8.0)
        self.spin_pitch.setSingleStep(1.0)
        self.spin_pitch.setDecimals(1)
        self.spin_pitch.setSuffix("°")
        self.spin_pitch.valueChanged.connect(self._on_cambio_parametro)
        grid2.addWidget(lbl_pitch, 2, 0)
        grid2.addWidget(self.spin_pitch, 2, 1)

        geo_layout.addLayout(grid2)
        layout.addWidget(card_geo)

        # --- TARJETA 3: VOLUMEN DE ALERTAS SONORAS ---
        card_audio = GlassCard(radius=14, bg_alpha=172)
        audio_layout = QVBoxLayout(card_audio)
        audio_layout.setContentsMargins(16, 14, 16, 14)
        audio_layout.setSpacing(10)

        h3 = QHBoxLayout()
        h3.addWidget(crear_label_icono("pulse", "#22C55E", 18))
        lbl3 = QLabel("Volumen de Alertas Sonoras")
        lbl3.setObjectName("section")
        h3.addWidget(lbl3, 1)
        audio_layout.addLayout(h3)

        grid3 = QGridLayout()
        grid3.setHorizontalSpacing(16)
        grid3.setVerticalSpacing(10)

        lbl_vf = QLabel("Aviso de Fatiga Temprana (Nivel 1):")
        lbl_vf.setObjectName("metric-title")
        self.slider_vol_fatiga = QSlider(Qt.Horizontal)
        self.slider_vol_fatiga.setRange(0, 100)
        self.slider_vol_fatiga.setValue(85)
        self.lbl_vf_val = QLabel("85%")
        self.lbl_vf_val.setObjectName("settings-value")
        self.slider_vol_fatiga.valueChanged.connect(self._on_cambio_volumen)

        lbl_vc = QLabel("Alarma Crítica de Microsueño (Nivel 2):")
        lbl_vc.setObjectName("metric-title")
        self.slider_vol_critico = QSlider(Qt.Horizontal)
        self.slider_vol_critico.setRange(0, 100)
        self.slider_vol_critico.setValue(100)
        self.lbl_vc_val = QLabel("100%")
        self.lbl_vc_val.setObjectName("settings-value")
        self.slider_vol_critico.valueChanged.connect(self._on_cambio_volumen)

        grid3.addWidget(lbl_vf, 0, 0)
        grid3.addWidget(self.slider_vol_fatiga, 0, 1)
        grid3.addWidget(self.lbl_vf_val, 0, 2)
        grid3.addWidget(lbl_vc, 1, 0)
        grid3.addWidget(self.slider_vol_critico, 1, 1)
        grid3.addWidget(self.lbl_vc_val, 1, 2)

        audio_layout.addLayout(grid3)
        layout.addWidget(card_audio)

        # --- BARRA INFERIOR DE ACCIÓN ---
        actions = QHBoxLayout()
        self.status_hint = QLabel("Los cambios se aplican en tiempo real sin detener la cámara.")
        self.status_hint.setObjectName("muted")
        actions.addWidget(self.status_hint, 1)

        btn_reset = QPushButton("Restaurar valores por defecto")
        btn_reset.setObjectName("secondary-button")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.clicked.connect(self._restaurar_defectos)
        actions.addWidget(btn_reset)

        layout.addLayout(actions)
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def sincronizar_desde_analyzer(self):
        """Refleja los valores activos de DrowsinessAnalyzer (útil tras Calibrar 3 s)."""
        self._bloqueando = True
        try:
            pct_cnn = int(round(self.analyzer.prob_umbral_cierre * 100))
            pct_lib = int(round(self.analyzer.prob_umbral_apertura * 100))
            self.slider_cnn.setValue(pct_cnn)
            self.lbl_cnn_val.setText(f"{pct_cnn}%  (libera < {pct_lib}%)")

            self.spin_t_normal.setValue(self.analyzer.duracion_microsueño_normal)
            self.spin_t_fatiga.setValue(self.analyzer.duracion_microsueño_fatiga)
            self.spin_yaw.setValue(int(round(self.analyzer.yaw_limite)))
            self.spin_mar.setValue(self.analyzer.mar_umbral)
            self.spin_pitch.setValue(self.analyzer.pitch_umbral)
        finally:
            self._bloqueando = False

    def _on_cambio_parametro(self):
        if self._bloqueando:
            return

        # Mantener invariante de histéresis en CNN (apertura siempre 15% debajo del cierre)
        prob_cierre = self.slider_cnn.value() / 100.0
        prob_apertura = max(0.15, round(prob_cierre - 0.15, 2))
        self.lbl_cnn_val.setText(
            f"{int(round(prob_cierre * 100))}%  (libera < {int(round(prob_apertura * 100))}%)"
        )

        # Garantizar que el tiempo con fatiga no supere el tiempo normal
        t_normal = round(self.spin_t_normal.value(), 1)
        t_fatiga = round(self.spin_t_fatiga.value(), 1)
        if t_fatiga > t_normal:
            self._bloqueando = True
            t_fatiga = t_normal
            self.spin_t_fatiga.setValue(t_fatiga)
            self._bloqueando = False

        self.analyzer.prob_umbral_cierre = prob_cierre
        self.analyzer.prob_umbral_apertura = prob_apertura
        self.analyzer.duracion_microsueño_normal = t_normal
        self.analyzer.duracion_microsueño_fatiga = t_fatiga
        self.analyzer.yaw_limite = float(self.spin_yaw.value())
        self.analyzer.mar_umbral = round(self.spin_mar.value(), 2)
        self.analyzer.pitch_umbral = round(self.spin_pitch.value(), 1)

        self.configuracion_actualizada.emit()

    def _on_cambio_volumen(self):
        vf = self.slider_vol_fatiga.value()
        vc = self.slider_vol_critico.value()
        self.lbl_vf_val.setText(f"{vf}%")
        self.lbl_vc_val.setText(f"{vc}%")
        self.volumen_cambiado.emit(vf / 100.0, vc / 100.0)

    def _restaurar_defectos(self):
        self._bloqueando = True
        try:
            self.analyzer.prob_umbral_cierre = 0.50
            self.analyzer.prob_umbral_apertura = 0.35
            self.analyzer.duracion_microsueño_normal = 1.5
            self.analyzer.duracion_microsueño_fatiga = 1.0
            self.analyzer.yaw_limite = 28.0
            self.analyzer.mar_umbral = 0.60
            self.analyzer.pitch_umbral = -18.0
            self.analyzer.ear_umbral = 0.21

            self.slider_vol_fatiga.setValue(85)
            self.slider_vol_critico.setValue(100)
            self.lbl_vf_val.setText("85%")
            self.lbl_vc_val.setText("100%")
        finally:
            self._bloqueando = False

        self.sincronizar_desde_analyzer()
        self.configuracion_actualizada.emit()
        self.volumen_cambiado.emit(0.85, 1.0)