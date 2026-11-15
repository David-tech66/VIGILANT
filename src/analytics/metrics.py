import numpy as np

def calcular_ear(ojo_puntos):
    """
    Calcula el Eye Aspect Ratio (EAR) usando las distancias euclidianas de 6 puntos.
    """
    v1 = np.linalg.norm(np.array(ojo_puntos[1]) - np.array(ojo_puntos[5]))
    v2 = np.linalg.norm(np.array(ojo_puntos[2]) - np.array(ojo_puntos[4]))
    h = np.linalg.norm(np.array(ojo_puntos[0]) - np.array(ojo_puntos[3]))
    
    if h == 0:
        return 0.0
        
    return (v1 + v2) / (2.0 * h)

def obtener_ear_promedio(landmarks, frame_width, frame_height):
    """
    Extrae los puntos clave de la malla de MediaPipe y devuelve el EAR promedio.
    """
    idx_ojo_izq = [33, 160, 158, 133, 153, 144]
    idx_ojo_der = [362, 385, 387, 263, 373, 380]

    ojo_izq = [(int(landmarks.landmark[i].x * frame_width), 
                int(landmarks.landmark[i].y * frame_height)) for i in idx_ojo_izq]
    
    ojo_der = [(int(landmarks.landmark[i].x * frame_width), 
                int(landmarks.landmark[i].y * frame_height)) for i in idx_ojo_der]

    ear_izq = calcular_ear(ojo_izq)
    ear_der = calcular_ear(ojo_der)

    return (ear_izq + ear_der) / 2.0