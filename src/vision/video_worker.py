
import cv2
import mediapipe as mp
import numpy as np
import threading

from PySide6.QtCore import QThread, Signal

from src.analytics.metrics import(
    obtener_ear_promedio,
    obtener_mar,
    obtener_pitch
)


class VideoWorker(QThread):

    # Enviar fotograma, EAR, MAR y PITCH a la interfaz
    frame_processed = Signal(np.ndarray, float, float, float)

    def __init__(self, camera_index=1):
        super().__init__()
        self._is_running = True
        self.camera_index = camera_index

        # Permite solicitar un cambio de fuente de forma segura
        self._source_lock = threading.Lock()
        self._pending_source = None
        self._source_changed = False

    def set_source(self, source):
        # Recibe el índice de cámara o la ruta del video
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

    def _abrir_fuente(self, source):
        cap = cv2.VideoCapture(source)

        # Si falla una cámara USB, intenta con la integrada
        if isinstance(source, int) and not cap.isOpened():
            cap.release()

            if source != 0:
                cap = cv2.VideoCapture(0)

        return cap

    def run(self):
        mp_face_mesh = mp.solutions.face_mesh
        mp_drawing = mp.solutions.drawing_utils
        mp_drawing_styles = mp.solutions.drawing_styles

        fuente_actual = self.camera_index
        cap = self._abrir_fuente(fuente_actual)

        try:
            with mp_face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            ) as face_mesh:

                while self._is_running:

                    # Comprobar si la interfaz solicitó otra fuente
                    cambio, nueva_fuente = self._obtener_nueva_fuente()

                    if cambio:
                        cap.release()
                        fuente_actual = nueva_fuente
                        cap = self._abrir_fuente(fuente_actual)

                    if not cap.isOpened():
                        self.msleep(100)
                        continue

                    success, image = cap.read()

                    if not success:
                        # Si es archivo de video, reinicia en bucle sin matar el hilo
                        if isinstance(fuente_actual, str):
                            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            self.msleep(30)
                            continue
                        
                        # Si es cámara, espera brevemente a que se recupere o cambie la fuente
                        self.msleep(50)
                        continue

                    # Efecto espejo solo cuando la lectura fue exitosa
                    if isinstance(fuente_actual, int):
                        image = cv2.flip(image, 1)

                    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                    image_rgb.flags.writeable = False
                    results = face_mesh.process(image_rgb)

                    image_rgb.flags.writeable = True
                    image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)

                    # -1.0 significa que no se detectó un rostro
                    ear_actual = -1.0
                    mar_actual = -1.0
                    pitch_actual = 0.0

                    if results.multi_face_landmarks:
                        h, w, _ = image.shape

                        for face_landmarks in results.multi_face_landmarks:

                            # Calcular EAR
                            ear_actual = obtener_ear_promedio(
                                face_landmarks,
                                w,
                                h
                            )

                            # Calcular MAR
                            mar_actual = obtener_mar(
                                face_landmarks,
                                w,
                                h
                            )

                            # Calcular PITCH
                            pitch_actual = obtener_pitch(
                                face_landmarks,
                                w,
                                h
                            )

                            # Dibujar la malla facial
                            mp_drawing.draw_landmarks(
                                image=image,
                                landmark_list=face_landmarks,
                                connections=mp_face_mesh.FACEMESH_TESSELATION,
                                landmark_drawing_spec=None,
                                connection_drawing_spec=mp_drawing_styles.get_default_face_mesh_tesselation_style()
                            )

                    # Enviar los datos a la interfaz
                    self.frame_processed.emit(
                        image,
                        ear_actual,
                        mar_actual,
                        pitch_actual
                    )

        finally:
            cap.release()

    def stop(self):
        self._is_running = False
        self.wait()
