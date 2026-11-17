import numpy as np
from PySide6.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Slot, Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VIGILANT v1.0 - Test de Integración Hilos")
        self.setFixedSize(800, 600)

        # Panel de Video
        self.video_label = QLabel("Iniciando motor de visión...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: black; color: white;")
        
        # Panel de Métrica Biométrica
        self.ear_label = QLabel("EAR Promedio: Calculando...")
        self.ear_label.setAlignment(Qt.AlignCenter)
        self.ear_label.setStyleSheet("font-size: 28px; font-weight: bold; padding: 10px;")

        # Estructura visual
        layout = QVBoxLayout()
        layout.addWidget(self.video_label, stretch=1)
        layout.addWidget(self.ear_label)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    # El "Slot" es el receptor oficial de la señal del QThread
    @Slot(np.ndarray, float)
    def actualizar_frame(self, frame, ear):
        # 1. Imprimir la matemática en la UI
        self.ear_label.setText(f"EAR Promedio: {ear:.3f}")

        # 2. Convertir la matriz de OpenCV (BGR) a formato Qt (QImage -> QPixmap)
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        q_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_BGR888)
        pixmap = QPixmap.fromImage(q_img)
        
        # 3. Proyectar escalando sin deformar
        self.video_label.setPixmap(pixmap.scaled(self.video_label.size(), Qt.KeepAspectRatio))