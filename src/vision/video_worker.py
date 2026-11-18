import cv2
import mediapipe as mp
import numpy as np
from PySide6.QtCore import QThread, Signal
from src.analytics.metrics import(
    obtener_ear_promedio, 
    obtener_mar, 
    obtener_pitch
)

class VideoWorker(QThread):
    
    # El canal seguro de comunicación: envía un fotograma (matriz), el número EAR, el MAR y el PITCH en angulos
    frame_processed = Signal(np.ndarray, float, float, float)

    def __init__(self, camera_index = 1):
        super().__init__()
        self._is_running = True
        self.camera_index = camera_index

    def run(self):
        mp_face_mesh = mp.solutions.face_mesh
        mp_drawing = mp.solutions.drawing_utils
        mp_drawing_styles = mp.solutions.drawing_styles

        # Intenta abrir la cámara configurada; si falla, usa la integrada (0)
        cap = cv2.VideoCapture(self.camera_index)
        if not cap.isOpened():
            cap = cv2.VideoCapture(0)

        with mp_face_mesh.FaceMesh(
            max_num_faces = 1,
            refine_landmarks = True,
            min_detection_confidence = 0.5,
            min_tracking_confidence = 0.5
        ) as face_mesh:

            while self._is_running and cap.isOpened():
                success, image = cap.read()
                if not success:
                    break

                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                image_rgb.flags.writeable = False
                results = face_mesh.process(image_rgb)
                
                image_rgb.flags.writeable = True
                image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
                
                # Estado por defecto: -1.0 significa "Rostro NO detectado"
                ear_actual = -1.0
                mar_actual = -1.0
                pitch_actual = 0.0

                if results.multi_face_landmarks:
                    h, w, _ = image.shape
                    for face_landmarks in results.multi_face_landmarks:
                        
                        # # 1. Extraer biométrica completa para calcular el EAR
                        ear_actual = obtener_ear_promedio(
                            face_landmarks, 
                            image.shape[1], 
                            image.shape[0]
                        )

                        mar_actual = obtener_mar(
                            face_landmarks, 
                            image.shape[1], 
                            image.shape[0]
                        )

                        pitch_actual = obtener_pitch(
                            face_landmarks, 
                            w, 
                            h
                        )
                        
                        # 2. Dibujar la malla sobre el fotograma original
                        mp_drawing.draw_landmarks(
                            image = image,
                            landmark_list = face_landmarks,
                            connections = mp_face_mesh.FACEMESH_TESSELATION,
                            landmark_drawing_spec = None,
                            connection_drawing_spec = mp_drawing_styles.get_default_face_mesh_tesselation_style()
                        )

                # 3. Emitir el paquete de datos al Hilo Principal
                self.frame_processed.emit(
                    image, 
                    ear_actual, 
                    mar_actual,
                    pitch_actual
                )

        cap.release()

    def stop(self):
        self._is_running = False
        self.wait()