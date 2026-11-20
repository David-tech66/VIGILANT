import sys
from PySide6.QtWidgets import QApplication
from src.ui.main_window import MainWindow
from src.vision.video_worker import VideoWorker


def main():

    # 1. Iniciar el motor gráfico de PySide6
    app = QApplication(sys.argv)

    # 2. Instanciar Capa Consumidora (Interfaz)
    ventana = MainWindow()

    # 3. Instanciar Capa Productora (Visión Artificial)
    worker = VideoWorker()

    # 4. CONECTAR EL PUENTE (Señal -> Slot)
    worker.frame_processed.connect(ventana.actualizar_frame)
    ventana.source_changed.connect(worker.set_source)

    # 5. Cierre seguro del hilo y liberación de la cámara
    app.aboutToQuit.connect(worker.stop)

    # 6. Arrancar los componentes
    ventana.show()
    worker.start()

    # 7. Mantener la aplicación viva
    sys.exit(app.exec())

if __name__ == "__main__":
    main()