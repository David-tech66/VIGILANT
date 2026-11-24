from pathlib import Path
import cv2
import numpy as np

try:
    import onnxruntime as ort
    ORT_DISPONIBLE = True
except ImportError:
    ort = None
    ORT_DISPONIBLE = False


# Contornos de ojos en MediaPipe Face Mesh
LEFT_EYE_CONTOUR = (
    33, 7, 163, 144, 145, 153, 154, 155,
    133, 173, 157, 158, 159, 160, 161, 246
)
RIGHT_EYE_CONTOUR = (
    362, 382, 381, 380, 374, 373, 390, 249,
    263, 466, 388, 387, 386, 385, 384, 398
)


class EyeStateClassifier:
    """Clasificador CNN ligero (ONNX) para estimar P(ojos cerrados) en [0.0, 1.0]."""

    IMG_SIZE = 64

    def __init__(self, model_path=None):
        self.disponible = False
        self.session = None
        self.input_name = None
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))

        if not ORT_DISPONIBLE:
            print("[VIGILANT] onnxruntime no instalado; modo respaldo por EAR.")
            return

        if model_path is None:
            raiz = Path(__file__).resolve().parents[2]
            model_path = raiz / "assets" / "models" / "eye_cnn.onnx"
        else:
            model_path = Path(model_path)

        if not model_path.exists():
            print(f"[VIGILANT] Modelo no encontrado en {model_path}; modo respaldo por EAR.")
            return

        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 2
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        self.session = ort.InferenceSession(
            str(model_path),
            sess_options=sess_options,
            providers=["CPUExecutionProvider"],
        )
        self.input_name = self.session.get_inputs()[0].name
        self.disponible = True
        print(f"[VIGILANT] CNN de ojos cargada correctamente: {model_path.name}")

    def _recortar_ojo(self, frame_gray, face_landmarks, indices, w, h, escala_margen=1.8):
        xs = [face_landmarks.landmark[i].x * w for i in indices]
        ys = [face_landmarks.landmark[i].y * h for i in indices]

        cx = 0.5 * (min(xs) + max(xs))
        cy = 0.5 * (min(ys) + max(ys))
        ancho_ojo = max(max(xs) - min(xs), max(ys) - min(ys))

        # Recorte cuadrado proporcional al tamaño del ojo (similar a MRL Eye Dataset)
        lado = max(int(round(ancho_ojo * escala_margen)), 24)
        mitad = lado // 2

        x1 = int(round(cx)) - mitad
        y1 = int(round(cy)) - mitad
        x2 = x1 + lado
        y2 = y1 + lado

        # Limitar al marco de la imagen
        x1_c, y1_c = max(0, x1), max(0, y1)
        x2_c, y2_c = min(w, x2), min(h, y2)

        if (x2_c - x1_c) < 12 or (y2_c - y1_c) < 12:
            return None

        crop = frame_gray[y1_c:y2_c, x1_c:x2_c]
        crop = cv2.resize(crop, (self.IMG_SIZE, self.IMG_SIZE), interpolation=cv2.INTER_AREA)
        crop = self.clahe.apply(crop)
        return crop.astype(np.float32) / 255.0

    def predecir_probabilidad_cierre(self, frame_bgr, face_landmarks):
        """
        Devuelve (prob_promedio, prob_izq, prob_der) en [0.0, 1.0].
        Si no está disponible o falla el recorte, devuelve (-1.0, -1.0, -1.0).
        """
        if not self.disponible:
            return -1.0, -1.0, -1.0

        h, w = frame_bgr.shape[:2]
        frame_gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

        crop_izq = self._recortar_ojo(frame_gray, face_landmarks, LEFT_EYE_CONTOUR, w, h)
        crop_der = self._recortar_ojo(frame_gray, face_landmarks, RIGHT_EYE_CONTOUR, w, h)

        crops = []
        etiquetas = []
        if crop_izq is not None:
            crops.append(crop_izq)
            etiquetas.append("izq")
        if crop_der is not None:
            crops.append(crop_der)
            etiquetas.append("der")

        if not crops:
            return -1.0, -1.0, -1.0

        # Lote (N, 1, 64, 64) para inferir ambos ojos en una sola llamada
        batch = np.stack(crops, axis=0)[:, np.newaxis, :, :]
        probs = self.session.run(None, {self.input_name: batch})[0].reshape(-1)

        p_izq = -1.0
        p_der = -1.0
        for etiqueta, valor in zip(etiquetas, probs):
            if etiqueta == "izq":
                p_izq = float(valor)
            else:
                p_der = float(valor)

        prob_promedio = float(np.mean(probs))
        return prob_promedio, p_izq, p_der