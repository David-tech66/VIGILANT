# VIGILANT - Sistema Inteligente de Detección de Señales Visuales de Somnolencia

**Versión:** 1.0 (Prototipo Académico)
**Fecha de Presentación:** --/--/-- 
**Desarrolladores:** David-tech66 (Líder / Visión), --- (UI / Interfaz), --- (Lógica / Datos).

---

## 1. Visión General del Proyecto

VIGILANT es un sistema de visión artificial diseñado para monitorear e identificar señales visuales persistentes de fatiga en un conductor. 

El proyecto resuelve un problema fundamental: **los detectores basados en un solo frame generan demasiadas falsas alarmas.** VIGILANT soluciona esto implementando una ventana de análisis temporal (persistencia de datos) sobre parámetros biométricos (EAR) extraídos en tiempo real.

### 1.1 Naturaleza del Sistema (Contexto Industrial & Prototipo)
*   **Contexto Industrial:** Conceptualmente, VIGILANT se modela como un dispositivo **Aftermarket (Retrofit)**. Es decir, opera como un módulo independiente (tipo *dashcam*) con cámara y procesamiento propio, sin necesidad de integrarse al sistema operativo nativo del panel del vehículo (evitando problemas de compatibilidad con distintas marcas).
*   **Prototipo:** Para validar la lógica matemática y la viabilidad del software a costo S/0, el prototipo es una **Aplicación de Escritorio (Desktop App) en Windows**, que procesará el video y simulará la pantalla de este módulo independiente.

---

## 2. Stack Tecnológico y Entorno de Desarrollo

Todo el equipo trabajará bajo el mismo entorno estandarizado para evitar conflictos de compatibilidad:

*   **IDE Oficial:** **Visual Studio Code (VS Code)** con las extensiones de *Python* y *Pylance*.
*   **Lenguaje:** Python 3.10 o 3.11 (Ejecutado bajo un entorno virtual `.venv`).
*   **Visión y Captura:** OpenCV (`opencv-python`) para captura de cuadros y conversiones de color.
*   **IA e Inferencia:** MediaPipe (`mediapipe` Face Mesh) para la extracción de 468 landmarks faciales optimizados para CPU.
*   **Cálculo Numérico:** NumPy (`numpy`) para el cálculo vectorial ultrarrápido sin bucles pesados.
*   **Frontend / UI:** PySide6 (`PySide6`) para la interfaz de escritorio y `pyqtgraph` para la telemetría en tiempo real.
*   **Persistencia:** SQLite (Librería nativa `sqlite3`) para la bitácora local de eventos.
*   **Control de Versiones:** Git y GitHub.

---

## 3. Arquitectura del Software

El sistema utiliza una **Arquitectura Desacoplada en Capas** con concurrencia (Multithreading) basada en el patrón Productor-Consumidor. Esto garantiza que la inferencia de IA no congele la interfaz de usuario.

1.  **Capa de Presentación (UI - Hilo Principal):** Módulo en PySide6. Muestra el video, renderiza la gráfica en vivo y emite las alarmas sonoras. No hace cálculos matemáticos.
2.  **Capa de Procesamiento (Worker - Hilo Secundario `QThread`):** Módulo que captura el fotograma (OpenCV) y extrae los puntos faciales (MediaPipe).
3.  **Capa de Dominio (Motor Analítico):** Módulo en Python/NumPy puro. Recibe las coordenadas, calcula el EAR y evalúa la regla temporal.
4.  **Capa de Datos:** Repositorio en SQLite que guarda un registro en la tabla local solo cuando se confirma una alerta de somnolencia.

---

## 4. Algoritmo Core y Matemática

El indicador principal es el **EAR (Eye Aspect Ratio)**, que calcula la relación entre el alto y el ancho del ojo.
La fórmula euclidiana implementada mediante NumPy es:

$$EAR = \frac{||p_2 - p_6|| + ||p_3 - p_5||}{2 \cdot ||p_1 - p_4||}$$

*(Donde $p_1, \dots, p_6$ son las coordenadas 2D de los landmarks de MediaPipe específicos para cada ojo).*

### 4.1 Lógica Temporal (Evitando el falso positivo)
No evaluamos frames aislados. El sistema almacena los últimos valores de EAR en una estructura de cola (`collections.deque`). 
*   **Parpadeo Normal:** El EAR cae por debajo del umbral pero se recupera en menos de 400 ms (aprox. 12 frames). **Se ignora.**
*   **Microsueño (Alerta):** El EAR cae por debajo del umbral y se mantiene bajo de forma continua por más de **1.5 a 2.0 segundos (aprox. 45-60 frames continuos)**. **Se dispara la alerta.**

---

## 5. Características Especiales (Demo)

1.  **Calibración Dinámica (3 segundos):** Un botón en la interfaz que toma los primeros 3 segundos de una persona sentada frente a la cámara, calcula su EAR base promedio ($\mu_{EAR}$) y ajusta automáticamente el umbral de disparo al 70% de su propia apertura normal. Esto elimina errores por diferentes formas de ojos.
2.  **Gráfica de Telemetría en Tiempo Real:** Un widget que dibuja la onda del ojo parpadeando en la interfaz. Visualmente impactante para el jurado y la prensa.
3.  **Modo "Fallo-Cero" (Selector de Fuente):** Un selector en la interfaz que permita cambiar la fuente de video de `Cámara Web` a `Video de Benchmark` (un video pregrabado de validación). Si la iluminación del auditorio falla, se pasa al video sin interrumpir la exposición.

---