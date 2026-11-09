import cv2
import mediapipe as mp
import time

def probar_camara():
    print("Iniciando módulo de visión... Presiona 'ESC' en la ventana de video para salir.")
    
    mp_face_mesh = mp.solutions.face_mesh
    mp_drawing = mp.solutions.drawing_utils
    mp_drawing_styles = mp.solutions.drawing_styles

    # 0 indica la cámara web predeterminada de la laptop
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: No se pudo acceder a la cámara.")
        return

    with mp_face_mesh.FaceMesh(
        max_num_faces = 1,
        refine_landmarks = True,
        min_detection_confidence = 0.5,
        min_tracking_confidence = 0.5) as face_mesh:

        prev_time = 0

        while cap.isOpened():
            success, image = cap.read()
            if not success:
                print("No se pudo leer el fotograma de la cámara.")
                break

            # Convertir colores para MediaPipe
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            image_rgb.flags.writeable = False
            
            # Extraer puntos faciales
            results = face_mesh.process(image_rgb)

            # Volver a formato de OpenCV para mostrar
            image_rgb.flags.writeable = True
            image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)

            # Dibujar malla
            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:
                    mp_drawing.draw_landmarks(
                        image = image,
                        landmark_list = face_landmarks,
                        connections = mp_face_mesh.FACEMESH_TESSELATION,
                        landmark_drawing_spec = None,
                        connection_drawing_spec = mp_drawing_styles.get_default_face_mesh_tesselation_style()
                    )

            # Medir rendimiento
            curr_time = time.time()
            fps = 1 / (curr_time - prev_time) if (curr_time - prev_time) > 0 else 0
            prev_time = curr_time
            
            cv2.putText(
                image, 
                f'FPS: {int(fps)}', 
                (20, 50), 
                cv2.FONT_HERSHEY_SIMPLEX, 
                1, 
                (0, 255, 0), 
                2
            )

            cv2.imshow('VIGILANT - Test MediaPipe', image)

            if cv2.waitKey(5) & 0xFF == 27:
                break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    probar_camara()