from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


def crear_icono(nombre, color="#CBD5E1", size=18):

    # Genera iconos vectoriales nitidos con QPainter sin depender de archivos externos.
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)

    c = QColor(color)
    
    pen = QPen(
        c, 
        max(1.5, size * 0.095), 
        Qt.SolidLine, 
        Qt.RoundCap, 
        Qt.RoundJoin
    )

    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    s = float(size)

    if nombre == "logo":
        grad = QLinearGradient(0, 0, s, s)
        grad.setColorAt(0.0, QColor("#38BDF8"))
        grad.setColorAt(1.0, QColor("#2563EB"))

        escudo = QPainterPath()
        
        escudo.moveTo(
            s * 0.50, 
            s * 0.08
        )
        
        escudo.lineTo(
            s * 0.86, 
            s * 0.22
        )

        escudo.lineTo(
            s * 0.86, 
            s * 0.52
        )
        
        escudo.quadTo(
            s * 0.86, 
            s * 0.80, 
            s * 0.50, 
            s * 0.93
        )

        escudo.quadTo(
            s * 0.14, 
            s * 0.80, 
            s * 0.14, 
            s * 0.52
        )

        escudo.lineTo(
            s * 0.14, 
            s * 0.22
        )

        escudo.closeSubpath()

        p.setPen(QPen(QColor("#7DD3FC"), s * 0.05))
        p.setBrush(grad)
        p.drawPath(escudo)

        # Ojo interior
        ojo = QPainterPath()
        
        ojo.moveTo(
            s * 0.28, 
            s * 0.50
        )
        
        ojo.quadTo(
            s * 0.50, 
            s * 0.30, 
            s * 0.72, 
            s * 0.50
        )

        ojo.quadTo(
            s * 0.50, 
            s * 0.70, 
            s * 0.28, 
            s * 0.50
        )

        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#0B1220"))
        p.drawPath(ojo)

        p.setBrush(QColor("#E0F2FE"))
        
        p.drawEllipse(
            QPointF(s * 0.50, s * 0.50), 
            s * 0.10, 
            s * 0.10
        )

    elif nombre == "home":
        techo = QPainterPath()
        
        techo.moveTo(
            s * 0.16, 
            s * 0.48
        )
        
        techo.lineTo(
            s * 0.50, 
            s * 0.18
        )

        techo.lineTo(
            s * 0.84, 
            s * 0.48
        )
        
        p.drawPath(techo)
        
        p.drawRoundedRect(
            QRectF(
                s * 0.27, 
                s * 0.46, 
                s * 0.46, 
                s * 0.36
            ), 
            1.5, 
            1.5)

    elif nombre == "reports":
        p.drawLine(
            QPointF(s * 0.24, s * 0.80), 
            QPointF(s * 0.24, s * 0.52)
        )
        p.drawLine(
            QPointF(s * 0.50, s * 0.80), 
            QPointF(s * 0.50, s * 0.24)
        )
        p.drawLine(
            QPointF(s * 0.76, s * 0.80), 
            QPointF(s * 0.76, s * 0.38)
        )

    elif nombre == "settings":
        p.drawEllipse(
            QPointF(
                s * 0.50, 
                s * 0.50
            ), 
            s * 0.17, 
            s * 0.17)
        p.drawEllipse(
            QPointF(
                s * 0.50, 
                s * 0.50
            ), 
            s * 0.33, 
            s * 0.33
        )

    elif nombre == "info":
        p.drawEllipse(QPointF(s * 0.50, s * 0.50), s * 0.38, s * 0.38)
        p.drawLine(QPointF(s * 0.50, s * 0.46), QPointF(s * 0.50, s * 0.69))
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(s * 0.50, s * 0.32), s * 0.06, s * 0.06)

    elif nombre == "camera":
        p.drawRoundedRect(QRectF(s * 0.12, s * 0.28, s * 0.54, s * 0.44), 2.5, 2.5)
        lente = QPainterPath()
        lente.moveTo(s * 0.68, s * 0.42)
        lente.lineTo(s * 0.88, s * 0.30)
        lente.lineTo(s * 0.88, s * 0.70)
        lente.lineTo(s * 0.68, s * 0.58)
        lente.closeSubpath()
        p.drawPath(lente)

    elif nombre == "pulse":
        onda = QPainterPath()
        onda.moveTo(s * 0.10, s * 0.54)
        onda.lineTo(s * 0.28, s * 0.54)
        onda.lineTo(s * 0.40, s * 0.22)
        onda.lineTo(s * 0.56, s * 0.78)
        onda.lineTo(s * 0.68, s * 0.46)
        onda.lineTo(s * 0.90, s * 0.46)
        p.drawPath(onda)

    elif nombre == "eye":
        ojo = QPainterPath()
        ojo.moveTo(s * 0.12, s * 0.50)
        ojo.quadTo(s * 0.50, s * 0.18, s * 0.88, s * 0.50)
        ojo.quadTo(s * 0.50, s * 0.82, s * 0.12, s * 0.50)
        p.drawPath(ojo)
        p.drawEllipse(QPointF(s * 0.50, s * 0.50), s * 0.13, s * 0.13)

    elif nombre == "ear":
        p.drawEllipse(QPointF(s * 0.50, s * 0.50), s * 0.34, s * 0.22)
        p.drawLine(QPointF(s * 0.50, s * 0.28), QPointF(s * 0.50, s * 0.72))
        p.drawLine(QPointF(s * 0.16, s * 0.50), QPointF(s * 0.84, s * 0.50))

    elif nombre == "mouth":
        arco = QPainterPath()
        arco.moveTo(s * 0.18, s * 0.44)
        arco.quadTo(s * 0.50, s * 0.84, s * 0.82, s * 0.44)
        arco.quadTo(s * 0.50, s * 0.56, s * 0.18, s * 0.44)
        p.drawPath(arco)

    elif nombre == "target":
        p.drawEllipse(QPointF(s * 0.50, s * 0.50), s * 0.32, s * 0.32)
        p.drawLine(QPointF(s * 0.50, s * 0.10), QPointF(s * 0.50, s * 0.26))
        p.drawLine(QPointF(s * 0.50, s * 0.74), QPointF(s * 0.50, s * 0.90))
        p.drawLine(QPointF(s * 0.10, s * 0.50), QPointF(s * 0.26, s * 0.50))
        p.drawLine(QPointF(s * 0.74, s * 0.50), QPointF(s * 0.90, s * 0.50))

    elif nombre == "history":
        p.drawEllipse(QPointF(s * 0.50, s * 0.50), s * 0.36, s * 0.36)
        p.drawLine(QPointF(s * 0.50, s * 0.30), QPointF(s * 0.50, s * 0.52))
        p.drawLine(QPointF(s * 0.50, s * 0.52), QPointF(s * 0.68, s * 0.62))

    elif nombre == "dot":
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawEllipse(QPointF(s * 0.50, s * 0.50), s * 0.28, s * 0.28)

    p.end()
    return QIcon(pixmap)


def crear_label_icono(nombre, color="#93C5FD", size=18):
    lbl = QLabel()
    lbl.setFixedSize(size, size)
    lbl.setPixmap(crear_icono(nombre, color, size).pixmap(size, size))
    lbl.setStyleSheet("background: transparent;")
    return lbl


class AmbientGlassBackground(QWidget):
    """Fondo oscuro con resplandores radiales en cache para dar profundidad al efecto cristal."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bg_cache = None

    def _regenerar_cache(self):
        w = max(1, self.width())
        h = max(1, self.height())
        pm = QPixmap(w, h)
        pm.fill(QColor("#080E1A"))

        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)

        # Degradado base profundo
        base = QLinearGradient(0, 0, w, h)
        base.setColorAt(0.0, QColor("#0B1324"))
        base.setColorAt(0.55, QColor("#0B1220"))
        base.setColorAt(1.0, QColor("#070D19"))
        p.fillRect(0, 0, w, h, base)

        # Luces ambientales suaves (hacen visible la translucidez de las GlassCards)
        luces = [
            (w * 0.14, h * 0.12, max(w, h) * 0.42, QColor(37, 99, 235, 58)),
            (w * 0.84, h * 0.18, max(w, h) * 0.38, QColor(16, 185, 129, 34)),
            (w * 0.52, h * 0.88, max(w, h) * 0.45, QColor(56, 189, 248, 30)),
            (w * 0.88, h * 0.82, max(w, h) * 0.36, QColor(139, 92, 246, 36)),
        ]

        for cx, cy, radio, color in luces:
            grad = QRadialGradient(cx, cy, radio)
            grad.setColorAt(0.0, color)
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.fillRect(0, 0, w, h, grad)

        p.end()
        self._bg_cache = pm

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._regenerar_cache()

    def paintEvent(self, event):
        if self._bg_cache is None or self._bg_cache.size() != self.size():
            self._regenerar_cache()
        p = QPainter(self)
        p.drawPixmap(0, 0, self._bg_cache)
        p.end()


class GlassCard(QFrame):
    """Tarjeta Dark Liquid Glass con reflejo especular superior y halo reactivo opcional."""

    def __init__(self, parent=None, radius=14, bg_alpha=172, glow_color=None):
        super().__init__(parent)
        self._radius = radius
        self._bg_alpha = bg_alpha
        self._glow_color = QColor(glow_color) if glow_color else None

    def set_glow_color(self, hex_color):
        nuevo = QColor(hex_color) if hex_color else None
        if self._glow_color != nuevo:
            self._glow_color = nuevo
            self.update()

    def paintEvent(self, event):
        rect = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setClipPath(path)

        # Cuerpo de vidrio oscuro semitransparente
        cuerpo = QLinearGradient(0, rect.top(), 0, rect.bottom())
        cuerpo.setColorAt(0.0, QColor(24, 34, 54, min(230, self._bg_alpha + 14)))
        cuerpo.setColorAt(1.0, QColor(13, 20, 34, self._bg_alpha))
        p.fillPath(path, cuerpo)

        # Halo reactivo opcional (usado en Estado del Conductor)
        if self._glow_color is not None:
            glow = QRadialGradient(
                rect.left() + rect.width() * 0.25,
                rect.top() + rect.height() * 0.55,
                max(rect.width(), rect.height()) * 0.75,
            )
            c_centro = QColor(self._glow_color)
            c_centro.setAlpha(44)
            glow.setColorAt(0.0, c_centro)
            glow.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.fillPath(path, glow)

        # Reflejo especular superior (efecto cristal liquido)
        reflejo = QLinearGradient(0, rect.top(), 0, rect.top() + rect.height() * 0.42)
        reflejo.setColorAt(0.0, QColor(255, 255, 255, 24))
        reflejo.setColorAt(0.45, QColor(255, 255, 255, 6))
        reflejo.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(path, reflejo)

        # Borde iluminado desde arriba
        p.setClipping(False)
        borde = QLinearGradient(0, rect.top(), 0, rect.bottom())
        borde.setColorAt(0.0, QColor(255, 255, 255, 58))
        borde.setColorAt(0.35, QColor(148, 163, 184, 28))
        borde.setColorAt(1.0, QColor(148, 163, 184, 14))
        p.setPen(QPen(borde, 1.1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

        p.end()


class MetricCard(QFrame):
    """Subtarjeta biometrica de telemetria con acento lateral de color."""

    def __init__(self, titulo, valor_inicial, condicion, icono_nombre, accent_color, parent=None):
        super().__init__(parent)
        self._accent = QColor(accent_color)
        self.setMinimumHeight(76)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 7, 10, 7)
        layout.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(6)
        top.addWidget(crear_label_icono(icono_nombre, accent_color, 15))

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setObjectName("metric-title")
        top.addWidget(lbl_titulo, 1)
        layout.addLayout(top)

        self.value_label = QLabel(valor_inicial)
        self.value_label.setObjectName("metric-value")
        self.value_label.setMinimumHeight(24)
        layout.addWidget(self.value_label)

        self.condition_label = QLabel(condicion)
        self.condition_label.setObjectName("metric-condition")
        layout.addWidget(self.condition_label)

    def paintEvent(self, event):
        rect = QRectF(self.rect()).adjusted(0.6, 0.6, -0.6, -0.6)
        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setClipPath(path)

        # Fondo cristal interno
        p.fillPath(path, QColor(12, 19, 34, 170))

        # Sutil tinte superior del color de acento
        tinte = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
        c1 = QColor(self._accent)
        c1.setAlpha(24)
        tinte.setColorAt(0.0, c1)
        tinte.setColorAt(0.6, QColor(0, 0, 0, 0))
        p.fillPath(path, tinte)

        # Barra de acento izquierda (como en el boceto final)
        barra = QRectF(rect.left() + 3.0, rect.top() + 8.0, 3.2, max(8.0, rect.height() - 16.0))
        p.setPen(Qt.NoPen)
        p.setBrush(self._accent)
        p.drawRoundedRect(barra, 1.6, 1.6)

        p.setClipping(False)
        p.setPen(QPen(QColor(148, 163, 184, 34), 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.end()


class StatusBadgeIcon(QWidget):
    """Insignia circular luminosa del estado del conductor."""

    def __init__(self, size=48, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._color = QColor("#22C55E")
        self._tipo = "check"

    def set_estado(self, color_hex, tipo="check"):
        nuevo_color = QColor(color_hex)
        if self._color != nuevo_color or self._tipo != tipo:
            self._color = nuevo_color
            self._tipo = tipo
            self.update()

    def paintEvent(self, event):
        s = float(min(self.width(), self.height()))
        cx = self.width() / 2.0
        cy = self.height() / 2.0

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Resplandor exterior
        halo = QRadialGradient(cx, cy, s * 0.50)
        c_halo = QColor(self._color)
        c_halo.setAlpha(95)
        halo.setColorAt(0.45, c_halo)
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(halo)
        p.drawEllipse(QPointF(cx, cy), s * 0.50, s * 0.50)

        # Circulo principal
        radio = s * 0.37
        grad = QLinearGradient(cx, cy - radio, cx, cy + radio)
        grad.setColorAt(0.0, self._color.lighter(115))
        grad.setColorAt(1.0, self._color.darker(115))
        p.setBrush(grad)
        p.drawEllipse(QPointF(cx, cy), radio, radio)

        # Simbolo interior
        pen = QPen(QColor("#07111F"), max(2.2, s * 0.065), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)

        if self._tipo == "check":
            path = QPainterPath()
            path.moveTo(cx - radio * 0.42, cy + radio * 0.04)
            path.lineTo(cx - radio * 0.10, cy + radio * 0.36)
            path.lineTo(cx + radio * 0.45, cy - radio * 0.30)
            p.drawPath(path)
        elif self._tipo == "alert":
            p.drawLine(QPointF(cx, cy - radio * 0.40), QPointF(cx, cy + radio * 0.12))
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#07111F"))
            p.drawEllipse(QPointF(cx, cy + radio * 0.36), radio * 0.11, radio * 0.11)
        else:
            p.drawEllipse(QPointF(cx, cy), radio * 0.34, radio * 0.34)

        p.end()