import numpy as np

from PySide6.QtWidgets import (
    QMainWindow, QLabel, QVBoxLayout, QHBoxLayout,
    QWidget, QFrame
)

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Slot, Qt

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("VIGILANT | Sistema de Monitoreo")
        self.setMinimumSize(1100, 700)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #0B1120;
            }

            QWidget {
                color: #E2E8F0;
                font-family: Segoe UI;
            }

            QFrame#sidebar {
                background-color: #111C30;
                border-right: 1px solid #263449;
            }

            QFrame#card {
                background-color: #162238;
                border: 1px solid #263449;
                border-radius: 12px;
            }

            QLabel#title {
                font-size: 23px;
                font-weight: bold;
                color: #F8FAFC;
            }

            QLabel#subtitle {
                color: #94A3B8;
                font-size: 12px;
            }

            QLabel#section {
                font-size: 15px;
                font-weight: bold;
                color: #F8FAFC;
            }

            QLabel#metric {
                font-size: 30px;
                font-weight: bold;
                color: #38BDF8;
            }

            QLabel#muted {
                color: #94A3B8;
                font-size: 12px;
            }

            QLabel#status {
                color: #FBBF24;
                font-size: 17px;
                font-weight: bold;
            }

            QLabel#video {
                background-color: #050A14;
                color: #64748B;
                border-radius: 8px;
                font-size: 16px;
            }
        """)

        # Contenedor principal
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Panel lateral
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 25, 20, 20)

        logo = QLabel("VIGILANT")
        logo.setStyleSheet(
            "font-size: 25px; font-weight: bold; color: #38BDF8;"
        )

        version = QLabel("SISTEMA DE SOMNOLENCIA")
        version.setObjectName("muted")

        sidebar_layout.addWidget(logo)
        sidebar_layout.addWidget(version)
        sidebar_layout.addSpacing(45)

        menu_title = QLabel("MONITOREO")
        menu_title.setObjectName("muted")

        sidebar_layout.addWidget(menu_title)

        for nombre in ["Panel principal", "Telemetría", "Historial de alertas"]:
            item = QLabel(nombre)
            item.setStyleSheet("""
                padding: 12px;
                background-color: #1E304B;
                border-radius: 7px;
                font-size: 13px;
            """)
            sidebar_layout.addWidget(item)

        sidebar_layout.addStretch()

        footer = QLabel("VIGILANT v1.0")
        footer.setObjectName("muted")
        sidebar_layout.addWidget(footer)

        main_layout.addWidget(sidebar)

        # Área de contenido
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(25, 22, 25, 20)
        content_layout.setSpacing(18)

        main_layout.addWidget(content)

        # Encabezado
        header = QHBoxLayout()

        title = QLabel("Panel de monitoreo")
        title.setObjectName("title")

        subtitle = QLabel("Detección de somnolencia en tiempo real")
        subtitle.setObjectName("subtitle")

        header_text = QVBoxLayout()
        header_text.addWidget(title)
        header_text.addWidget(subtitle)

        self.status_label = QLabel("ESPERANDO VIDEO")
        self.status_label.setObjectName("status")

        header.addLayout(header_text)
        header.addStretch()
        header.addWidget(self.status_label)

        content_layout.addLayout(header)

        # Contenido central
        body = QHBoxLayout()
        body.setSpacing(18)

        # Panel de cámara
        video_card = QFrame()
        video_card.setObjectName("card")

        video_layout = QVBoxLayout(video_card)
        video_layout.setContentsMargins(15, 15, 15, 15)

        video_title = QLabel("Visualización de cámara")
        video_title.setObjectName("section")

        self.video_label = QLabel("Esperando señal de cámara...")
        self.video_label.setObjectName("video")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(500, 400)

        video_layout.addWidget(video_title)
        video_layout.addWidget(self.video_label, 1)

        body.addWidget(video_card, 3)

        # Panel de métricas
        metrics_panel = QVBoxLayout()
        metrics_panel.setSpacing(15)

        # Tarjeta EAR
        ear_card = QFrame()
        ear_card.setObjectName("card")

        ear_layout = QVBoxLayout(ear_card)

        ear_title = QLabel("EAR PROMEDIO")
        ear_title.setObjectName("muted")

        self.ear_label = QLabel("0.000")
        self.ear_label.setObjectName("metric")

        ear_description = QLabel("Eye Aspect Ratio")
        ear_description.setObjectName("muted")

        ear_layout.addWidget(ear_title)
        ear_layout.addWidget(self.ear_label)
        ear_layout.addWidget(ear_description)

        metrics_panel.addWidget(ear_card)

        # Tarjeta de estado
        state_card = QFrame()
        state_card.setObjectName("card")

        state_layout = QVBoxLayout(state_card)

        state_title = QLabel("ESTADO DEL SISTEMA")
        state_title.setObjectName("muted")

        self.state_label = QLabel("En espera")
        self.state_label.setObjectName("section")

        state_description = QLabel("Esperando procesamiento")
        state_description.setObjectName("muted")

        state_layout.addWidget(state_title)
        state_layout.addWidget(self.state_label)
        state_layout.addWidget(state_description)

        metrics_panel.addWidget(state_card)

        # Tarjeta de alertas
        alert_card = QFrame()
        alert_card.setObjectName("card")

        alert_layout = QVBoxLayout(alert_card)

        alert_title = QLabel("ÚLTIMAS ALERTAS")
        alert_title.setObjectName("muted")

        self.alert_label = QLabel("Sin alertas recibidas")
        self.alert_label.setWordWrap(True)
        self.alert_label.setObjectName("section")

        alert_layout.addWidget(alert_title)
        alert_layout.addWidget(self.alert_label)

        metrics_panel.addWidget(alert_card)

        metrics_panel.addStretch()

        body.addLayout(metrics_panel, 1)

        content_layout.addLayout(body, 1)

        # Pie de página
        footer_text = QLabel(
            "VIGILANT | Sistema inteligente de detección de somnolencia"
        )
        footer_text.setObjectName("muted")

        content_layout.addWidget(footer_text)

    # Recibir fotogramas y EAR desde VideoWorker
    @Slot(np.ndarray, float)
    def actualizar_frame(self, frame, ear):

        # Actualizar métrica
        self.ear_label.setText(f"{ear:.3f}")

        # Indicar que estamos recibiendo video
        self.status_label.setText("VIDEO RECIBIDO")
        self.state_label.setText("Procesando video")

        # Convertir imagen OpenCV a QImage
        h, w, ch = frame.shape
        bytes_per_line = ch * w

        q_img = QImage(
            frame.data,
            w,
            h,
            bytes_per_line,
            QImage.Format_BGR888
        ).copy()

        # Convertir QImage a QPixmap
        pixmap = QPixmap.fromImage(q_img)

        # Mostrar video sin deformar la imagen
        self.video_label.setPixmap(
            pixmap.scaled(
                self.video_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )
