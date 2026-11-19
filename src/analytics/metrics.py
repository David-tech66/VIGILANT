import math
import cv2
import numpy as np


def calcular_ear(ojo_puntos):
    """
    Calcula el Eye Aspect Ratio (EAR) usando distancias euclidianas de 6 puntos.
    """
    v1 = np.linalg.norm(np.array(ojo_puntos[1]) - np.array(ojo_puntos[5]))
    v2 = np.linalg.norm(np.array(ojo_puntos[2]) - np.array(ojo_puntos[4]))
    h = np.linalg.norm(np.array(ojo_puntos[0]) - np.array(ojo_puntos[3]))

    if h == 0:
        return 0.0

    return float((v1 + v2) / (2.0 * h))


def obtener_ear_promedio(landmarks, frame_width, frame_height):
    """
    Extrae los puntos clave de ambos ojos y devuelve el EAR promedio.
    """
    idx_ojo_izq = [33, 160, 158, 133, 153, 144]
    idx_ojo_der = [362, 385, 387, 263, 373, 380]

    ojo_izq = [
        (landmarks.landmark[i].x * frame_width, landmarks.landmark[i].y * frame_height)
        for i in idx_ojo_izq
    ]
    ojo_der = [
        (landmarks.landmark[i].x * frame_width, landmarks.landmark[i].y * frame_height)
        for i in idx_ojo_der
    ]

    ear_izq = calcular_ear(ojo_izq)
    ear_der = calcular_ear(ojo_der)

    return (ear_izq + ear_der) / 2.0


def calcular_mar(boca_puntos):
    """
    Calcula el Mouth Aspect Ratio (MAR) usando 6 puntos de los labios.
    """
    v1 = np.linalg.norm(np.array(boca_puntos[1]) - np.array(boca_puntos[5]))
    v2 = np.linalg.norm(np.array(boca_puntos[2]) - np.array(boca_puntos[4]))
    h = np.linalg.norm(np.array(boca_puntos[0]) - np.array(boca_puntos[3]))

    if h == 0:
        return 0.0

    return float((v1 + v2) / (2.0 * h))


def obtener_mar(landmarks, frame_width, frame_height):
    """
    Extrae los puntos clave de los labios y devuelve el MAR.
    Índices: [Izq, SupIzq, SupDer, Der, InfDer, InfIzq]
    """
    idx_boca = [78, 82, 312, 308, 317, 87]

    boca = [
        (landmarks.landmark[i].x * frame_width, landmarks.landmark[i].y * frame_height)
        for i in idx_boca
    ]

    return calcular_mar(boca)


def obtener_pitch(landmarks, frame_width, frame_height):
    """
    Calcula el ángulo de inclinación vertical de la cabeza (Pitch) en grados
    usando cv2.solvePnP.
    Retorna ~0° mirando de frente, negativo al inclinar la cabeza hacia abajo
    (cabeceo) y positivo al mirar hacia arriba.
    Nota: No aplicar cv2.flip al frame antes de llamar a esta función.
    """
    # Puntos 2D: Nariz(1), Mentón(152), Ojo Der sujeto/Izq imagen(33),
    # Ojo Izq sujeto/Der imagen(263), Boca Izq imagen(61), Boca Der imagen(291)
    idx_pose = [1, 152, 33, 263, 61, 291]
    puntos_2d = np.array([
        (landmarks.landmark[i].x * frame_width, landmarks.landmark[i].y * frame_height)
        for i in idx_pose
    ], dtype=np.float64)

    # Modelo 3D alineado al sistema de cámara de OpenCV (+X derecha, +Y abajo, +Z fondo)
    puntos_3d = np.array([
        (0.0, 0.0, 0.0),          # Nariz
        (0.0, 330.0, 65.0),       # Mentón
        (-225.0, -170.0, 135.0),  # Ojo (lado izquierdo de la imagen)
        (225.0, -170.0, 135.0),   # Ojo (lado derecho de la imagen)
        (-150.0, 150.0, 125.0),   # Comisura (lado izquierdo de la imagen)
        (150.0, 150.0, 125.0)     # Comisura (lado derecho de la imagen)
    ], dtype=np.float64)

    focal_length = float(frame_width)
    centro = (frame_width / 2.0, frame_height / 2.0)
    matriz_camara = np.array([
        [focal_length, 0.0, centro[0]],
        [0.0, focal_length, centro[1]],
        [0.0, 0.0, 1.0]
    ], dtype=np.float64)

    dist_coeffs = np.zeros((4, 1), dtype=np.float64)

    exito, vector_rotacion, _ = cv2.solvePnP(
        puntos_3d, puntos_2d, matriz_camara, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE
    )

    if not exito:
        return 0.0

    matriz_rotacion, _ = cv2.Rodrigues(vector_rotacion)

    # Elevación vertical del vector normal del rostro en el rango [-90°, +90°]
    r02 = matriz_rotacion[0, 2]
    r12 = matriz_rotacion[1, 2]
    r22 = matriz_rotacion[2, 2]
    pitch_rad = math.atan2(r12, math.hypot(r02, r22))

    return float(math.degrees(pitch_rad))