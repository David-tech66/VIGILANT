import cv2
import mediapipe as mp
import numpy as np
from PySide6.QtCore import QThread, Signal
from src.analytics.metrics import obtener_ear_promedio

class VideoWorker(QThread):
    # El canal seguro de comunicación: envía un fotograma (matriz) y el número EAR
    frame_processed = Signal(np.ndarray, float)

    def __init__(self):
        super().__init__()
        self._is_running = True

    def run(self):
        mp_face_mesh = mp.solutions.face_mesh
        mp_drawing = mp.solutions.drawing_utils
        mp_drawing_styles = mp.solutions.drawing_styles
        
        cap = cv2.VideoCapture(0)

        with mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5) as face_mesh:

            while self._is_running and cap.isOpened():
                success, image = cap.read()
                if not success:
                    break

                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                image_rgb.flags.writeable = False
                results = face_mesh.process(image_rgb)
                
                image_rgb.flags.writeable = True
                image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
                
                ear_actual = 0.0

                if results.multi_face_landmarks:
                    for face_landmarks in results.multi_face_landmarks:
                        # 1. Calcular el EAR
                        ear_actual = obtener_ear_promedio(face_landmarks, image.shape[1], image.shape[0])
                        
                        # 2. Dibujar la malla sobre el fotograma original
                        mp_drawing.draw_landmarks(
                            image=image,
                            landmark_list=face_landmarks,
                            connections=mp_face_mesh.FACEMESH_TESSELATION,
                            landmark_drawing_spec=None,
                            connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_tesselation_style())

                # 3. Emitir el paquete de datos al Hilo Principal
                self.frame_processed.emit(image, ear_actual)

        cap.release()

    def stop(self):
        self._is_running = False
        self.wait()