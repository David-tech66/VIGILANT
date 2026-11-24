from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.ui.components import GlassCard, MetricCard, crear_label_icono


class AboutPage(QWidget):
    """Ficha técnica de VIGILANT v2.0, métricas de IA y equipo de desarrollo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._construir_ui()

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

        # --- TARJETA 1: IDENTIDAD DEL PROYECTO ---
        hero = GlassCard(radius=14, bg_alpha=178, glow_color="#2563EB")
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(18, 16, 18, 16)
        hero_layout.setSpacing(16)

        hero_layout.addWidget(crear_label_icono("logo", "#38BDF8", 58), 0, Qt.AlignTop)

        hero_text = QVBoxLayout()
        hero_text.setSpacing(4)
        t_main = QLabel("VIGILANT v2.0 — Sistema Inteligente de Monitoreo de Somnolencia")
        t_main.setObjectName("placeholder-title")
        t_main.setWordWrap(True)

        t_desc = QLabel(
            "Prototipo de visión por computadora e Inteligencia Artificial en tiempo real "
            "para la detección preventiva de microsueños, bostezos y cabeceos al volante. "
            "Opera 100% en local sobre CPU combinando una red neuronal convolucional (ONNX) "
            "para clasificación ocular con métricas geométricas de MediaPipe Face Mesh."
        )
        t_desc.setObjectName("placeholder-desc")
        t_desc.setWordWrap(True)

        hero_text.addWidget(t_main)
        hero_text.addWidget(t_desc)
        hero_layout.addLayout(hero_text, 1)
        layout.addWidget(hero)

        # --- TARJETA 2: MÉTRICAS VERIFICADAS DEL MODELO ---
        model_card = GlassCard(radius=14, bg_alpha=172)
        m_layout = QVBoxLayout(model_card)
        m_layout.setContentsMargins(16, 14, 16, 14)
        m_layout.setSpacing(10)

        mh = QHBoxLayout()
        mh.addWidget(crear_label_icono("eye", "#38BDF8", 18))
        ml = QLabel("Modelo EyeStateCNN (ONNX Runtime • MRL Eye Dataset — 84,898 imágenes)")
        ml.setObjectName("section")
        mh.addWidget(ml, 1)
        m_layout.addLayout(mh)

        grid_kpi = QGridLayout()
        grid_kpi.setSpacing(10)
        grid_kpi.addWidget(
            MetricCard("ACCURACY TEST", "93.94%", "Sujetos no vistos (7,190 imgs)", "reports", "#2563EB"),
            0, 0
        )
        grid_kpi.addWidget(
            MetricCard("F1-SCORE", "95.13%", "Precision 97.73% • Recall 92.67%", "pulse", "#22C55E"),
            0, 1
        )
        grid_kpi.addWidget(
            MetricCard("PARÁMETROS", "163,369", "Inferencia ligera en CPU (CLAHE 64×64)", "settings", "#8B5CF6"),
            0, 2
        )
        grid_kpi.addWidget(
            MetricCard("BAJA LUZ / SIN LENTES", "93.5% / 98.0%", "Con lentes: 89.21% (umbral 50%)", "target", "#F59E0B"),
            0, 3
        )
        m_layout.addLayout(grid_kpi)
        layout.addWidget(model_card)

        # --- FILA INFERIOR: EQUIPO + STACK TECNOLÓGICO ---
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        # Equipo
        team_card = GlassCard(radius=14, bg_alpha=172)
        t_layout = QVBoxLayout(team_card)
        t_layout.setContentsMargins(16, 14, 16, 14)
        t_layout.setSpacing(8)

        th = QHBoxLayout()
        th.addWidget(crear_label_icono("info", "#93C5FD", 18))
        tl = QLabel("Equipo de Desarrollo — Ingeniería de Software con IA")
        tl.setObjectName("section")
        th.addWidget(tl, 1)
        t_layout.addLayout(th)

        miembros = [
            ("Aaron Prado Ramirez", "Líder técnico • Capa de Visión (video_worker.py), hot-plugging y módulo IA ONNX (src/ai/)."),
            ("Jhon C. Gallegos Rios", "Analítica biométrica (metrics.py, temporal_buffer.py) y persistencia en SQLite (vigilant.db)."),
            ("Victor L. Martin Cahuaza", "Diseño de interfaz Dark Liquid Glass (src/ui/, style.qss) y alertas sonoras (assets/audio/)."),
        ]
        for nombre, rol in miembros:
            lbl_n = QLabel(f"• {nombre}")
            lbl_n.setStyleSheet("font-size: 12px; font-weight: 700; color: #F1F5F9; background: transparent;")
            lbl_r = QLabel(f"   {rol}")
            lbl_r.setObjectName("muted")
            lbl_r.setWordWrap(True)
            t_layout.addWidget(lbl_n)
            t_layout.addWidget(lbl_r)

        t_layout.addStretch()
        bottom_row.addWidget(team_card, 3)

        # Stack
        stack_card = GlassCard(radius=14, bg_alpha=172)
        s_layout = QVBoxLayout(stack_card)
        s_layout.setContentsMargins(16, 14, 16, 14)
        s_layout.setSpacing(6)

        sh = QHBoxLayout()
        sh.addWidget(crear_label_icono("settings", "#22C55E", 18))
        sl = QLabel("Stack Tecnológico")
        sl.setObjectName("section")
        sh.addWidget(sl, 1)
        s_layout.addLayout(sh)

        tecnologias = [
            "Python 3.10 + PySide6 (QtWidgets / QtMultimedia)",
            "ONNX Runtime (CPUExecutionProvider)",
            "MediaPipe Face Mesh 0.10.9 + OpenCV 4.10",
            "PyQtGraph (Osciloscopio en tiempo real)",
            "SQLite3 (Bitácora persistente y exportación CSV)",
        ]
        for tech in tecnologias:
            lbl = QLabel(f"• {tech}")
            lbl.setStyleSheet("font-size: 11px; color: #CBD5E1; background: transparent;")
            lbl.setWordWrap(True)
            s_layout.addWidget(lbl)

        s_layout.addStretch()
        bottom_row.addWidget(stack_card, 2)

        layout.addLayout(bottom_row)
        layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)