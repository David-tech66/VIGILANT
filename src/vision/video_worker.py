import os
import threading
import cv2
import mediapipe as mp
import numpy as np

from PySide6.QtCore import QThread, Signal

from src.ai.eye_classifier import EyeStateClassifier
from src.analytics.metrics import (
    obtener_ear_promedio,
    obtener_mar,
    obtener_pose_cabeza
)
import os
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")


class VideoWorker(QThread):

    # Fotograma, EAR, MAR, PITCH, YAW y probabilidad CNN de ojos cerrados [0..1] (-1 si no aplica)
    frame_processed = Signal(np.ndarray, float, float, float, float, float)
    # Notificar a la UI qué fuente quedó realmente activa (1, 0, ruta str o None)
    source_active = Signal(object)

    def __init__(self, camera_index=1):
        super().__init__()
        self._is_running = True
        self.camera_index = camera_index

        self._source_lock = threading.Lock()
        self._pending_source = None
        self._source_changed = False

    def set_source(self, source):
        with self._source_lock:
            self._pending_source = source
            self._source_changed = True

    def _obtener_nueva_fuente(self):
        with self._source_lock:
            if self._source_changed:
                source = self._pending_source
                self._source_changed = False
                return True, source

        return False, None

    def _intentar_camara(self, indice):
        backend = cv2.CAP_MSMF if os.name == "nt" else cv2.CAP_ANY
        cap = cv2.VideoCapture(indice, backend)
        if cap.isOpened():
            ok, _ = cap.read()
            if ok:
                return cap
        cap.release()
        
        return None

    def _abrir_fuente(self, source):
        if isinstance(source, int):
            cap = self._intentar_camara(source)
            if cap is not None:
                return cap, source

            # Fallback real a la cámara integrada (0) si falló la USB (1)
            if source != 0:
                cap = self._intentar_camara(0)
                if cap is not None:
                    return cap, 0

            return None, None

        # Archivo de video (Video Benchmark)
        cap = cv2.VideoCapture(source)
        if cap.isOpened():
            return cap, source
        cap.release()
        return None, None

    def run(self):
        mp_face_mesh = mp.solutions.face_mesh
        mp_drawing = mp.solutions.drawing_utils
        mp_drawing_styles = mp.solutions.drawing_styles

        # Cargar modelo ONNX dentro del worker para no bloquear el arranque de la UI
        eye_classifier = EyeStateClassifier()

        cap, fuente_actual = self._abrir_fuente(self.camera_index)
        self.source_active.emit(fuente_actual)
        fallos_lectura = 0

        try:
            with mp_face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            ) as face_mesh:

                while self._is_running:
                    cambio, nueva_fuente = self._obtener_nueva_fuente()

                    if cambio:
                        if nueva_fuente == fuente_actual and cap is not None and cap.isOpened():
                            continue

                        if cap is not None:
                            cap.release()
                        cap, fuente_actual = self._abrir_fuente(nueva_fuente)
                        fallos_lectura = 0
                        self.source_active.emit(fuente_actual)

                    if cap is None or not cap.isOpened():
                        self.msleep(100)
                        continue

                    success, image = cap.read()

                    if not success:
                        if isinstance(fuente_actual, str):
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            self.msleep(30)
                            continue

                        fallos_lectura += 1
                        if fallos_lectura >= 5:
                            print(f"[VIGILANT] Cámara {fuente_actual} desconectada. Cambiando a respaldo...")
                            cap.release()
                            cap = None
                            fallos_lectura = 0

                            if fuente_actual != 0:
                                cap, fuente_actual = self._abrir_fuente(0)
                            else:
                                fuente_actual = None

                            self.source_active.emit(fuente_actual)

                        self.msleep(50)
                        continue

                    fallos_lectura = 0

                    # Efecto espejo solo en cámaras en vivo
                    if isinstance(fuente_actual, int):
                        image = cv2.flip(image, 1)

                    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                    image_rgb.flags.writeable = False
                    results = face_mesh.process(image_rgb)

                    image_rgb.flags.writeable = True
                    image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)

                    ear_actual = -1.0
                    mar_actual = -1.0
                    pitch_actual = 0.0
                    yaw_actual = 0.0
                    prob_cierre_actual = -1.0

                    if results.multi_face_landmarks:
                        h, w, _ = image.shape
                        face_landmarks = results.multi_face_landmarks[0]

                        ear_actual = obtener_ear_promedio(face_landmarks, w, h)
                        mar_actual = obtener_mar(face_landmarks, w, h)
                        pitch_actual, yaw_actual = obtener_pose_cabeza(face_landmarks, w, h)

                        # Clasificar ojos ANTES de dibujar la malla facial
                        prob_cierre_actual, _, _ = eye_classifier.predecir_probabilidad_cierre(
                            image, face_landmarks
                        )

                        mp_drawing.draw_landmarks(
                            image=image,
                            landmark_list=face_landmarks,
                            connections=mp_face_mesh.FACEMESH_TESSELATION,
                            landmark_drawing_spec=None,
                            connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_tesselation_style()
                        )

                    self.frame_processed.emit(
                        image,
                        ear_actual,
                        mar_actual,
                        pitch_actual,
                        yaw_actual,
                        prob_cierre_actual
                    )

        finally:
            if cap is not None:
                cap.release()

    def stop(self):
        self._is_running = False
        self.wait()