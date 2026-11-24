import csv
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.ui.components import GlassCard, MetricCard, crear_label_icono


class ReportsPage(QWidget):
    """Vista de reportes completos de SQLite con filtros y exportación a CSV."""

    historial_limpiado = Signal()

    def __init__(self, db_connection, parent=None):
        super().__init__(parent)
        self.db = db_connection
        self.setStyleSheet("background: transparent;")
        self._construir_ui()
        self.recargar_datos()

    def _construir_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # --- FILA SUPERIOR: 4 TARJETAS KPI ---
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)

        self.kpi_total = MetricCard("TOTAL EVENTOS", "0", "Histórico acumulado", "reports", "#38BDF8")
        self.kpi_micro = MetricCard("MICROSUEÑOS", "0", "Alerta crítica (Nivel 2)", "eye", "#EF4444")
        self.kpi_bostezo = MetricCard("BOSTEZOS", "0", "Fatiga temprana (MAR)", "mouth", "#F59E0B")
        self.kpi_cabeceo = MetricCard("CABECEO", "0", "Fatiga temprana (Pitch)", "pulse", "#8B5CF6")
        # Corregir etiqueta visual de título

        for card in (self.kpi_total, self.kpi_micro, self.kpi_bostezo, self.kpi_cabeceo):
            kpi_row.addWidget(card, 1)

        layout.addLayout(kpi_row)

        # --- TARJETA PRINCIPAL: FILTROS + TABLA ---
        table_card = GlassCard(radius=14, bg_alpha=172)
        card_layout = QVBoxLayout(table_card)
        card_layout.setContentsMargins(14, 12, 14, 12)
        card_layout.setSpacing(10)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        toolbar.addWidget(crear_label_icono("history", "#93C5FD", 18))

        title = QLabel("Registro Histórico de Incidentes")
        title.setObjectName("section")
        toolbar.addWidget(title)
        toolbar.addStretch()

        lbl_filtro = QLabel("Filtrar:")
        lbl_filtro.setObjectName("muted")
        toolbar.addWidget(lbl_filtro)

        self.filter_combo = QComboBox()
        self.filter_combo.setObjectName("source-select")
        self.filter_combo.addItems(["Todos", "Microsueño", "Bostezo Prolongado", "Cabeceo"])
        self.filter_combo.currentTextChanged.connect(self.recargar_datos)
        toolbar.addWidget(self.filter_combo)

        btn_refresh = QPushButton("Actualizar")
        btn_refresh.setObjectName("secondary-button")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(self.recargar_datos)
        toolbar.addWidget(btn_refresh)

        btn_export = QPushButton("Exportar CSV")
        btn_export.setObjectName("calibration-button")
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.clicked.connect(self._exportar_csv)
        toolbar.addWidget(btn_export)

        btn_clear = QPushButton("Limpiar Todo")
        btn_clear.setObjectName("clear-button")
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.clicked.connect(self._limpiar_historial)
        toolbar.addWidget(btn_clear)

        card_layout.addLayout(toolbar)

        self.table = QTableWidget(0, 4)
        self.table.setObjectName("reports-table")
        self.table.setHorizontalHeaderLabels(["ID", "Fecha", "Hora", "Tipo de Incidente"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)

        card_layout.addWidget(self.table, 1)

        self.footer_info = QLabel("Mostrando 0 registros")
        self.footer_info.setObjectName("muted")
        card_layout.addWidget(self.footer_info)

        layout.addWidget(table_card, 1)

    def _obtener_filas(self, filtro):
        if filtro == "Todos":
            return self.db.execute(
                "SELECT id, fecha, hora, tipo FROM incidentes ORDER BY id DESC"
            ).fetchall()
        return self.db.execute(
            "SELECT id, fecha, hora, tipo FROM incidentes WHERE tipo = ? ORDER BY id DESC",
            (filtro,),
        ).fetchall()

    def recargar_datos(self):
        # 1. Actualizar contadores globales
        conteos = dict(
            self.db.execute("SELECT tipo, COUNT(*) FROM incidentes GROUP BY tipo").fetchall()
        )
        n_micro = conteos.get("Microsueño", 0)
        n_bostezo = conteos.get("Bostezo Prolongado", 0)
        n_cabeceo = conteos.get("Cabeceo", 0)
        total = sum(conteos.values())

        self.kpi_total.value_label.setText(str(total))
        self.kpi_micro.value_label.setText(str(n_micro))
        self.kpi_bostezo.value_label.setText(str(n_bostezo))
        self.kpi_cabeceo.value_label.setText(str(n_cabeceo))

        # 2. Llenar tabla filtrada
        filtro = self.filter_combo.currentText()
        filas = self._obtener_filas(filtro)

        self.table.setRowCount(len(filas))
        colores = {
            "Microsueño": QColor("#F87171"),
            "Bostezo Prolongado": QColor("#FBBF24"),
            "Cabeceo": QColor("#38BDF8"),
        }

        for r_idx, (reg_id, fecha, hora, tipo) in enumerate(filas):
            items = [
                QTableWidgetItem(f"#{reg_id}"),
                QTableWidgetItem(fecha),
                QTableWidgetItem(hora),
                QTableWidgetItem(tipo),
            ]
            for c_idx, item in enumerate(items):
                if c_idx < 3:
                    item.setTextAlignment(Qt.AlignCenter)
                if c_idx == 3 and tipo in colores:
                    item.setForeground(colores[tipo])
                self.table.setItem(r_idx, c_idx, item)

        self.footer_info.setText(f"Mostrando {len(filas)} de {total} incidentes registrados")

    def _exportar_csv(self):
        filtro = self.filter_combo.currentText()
        filas = self._obtener_filas(filtro)

        if not filas:
            QMessageBox.information(self, "Exportar CSV", "No hay incidentes para exportar.")
            return

        nombre_defecto = f"vigilant_reporte_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        ruta, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar reporte CSV",
            nombre_defecto,
            "Archivos CSV (*.csv)",
        )
        if not ruta:
            return

        try:
            with open(ruta, "w", newline="", encoding="utf-8-sig") as archivo:
                writer = csv.writer(archivo)
                writer.writerow(["ID", "Fecha", "Hora", "Tipo de Incidente"])
                writer.writerows(filas)
            QMessageBox.information(
                self,
                "Exportación exitosa",
                f"Se exportaron {len(filas)} registros en:\n{ruta}",
            )
        except OSError as exc:
            QMessageBox.critical(self, "Error al exportar", f"No se pudo guardar el archivo:\n{exc}")

    def _limpiar_historial(self):
        respuesta = QMessageBox.question(
            self,
            "Confirmar limpieza",
            "¿Deseas eliminar todos los incidentes guardados en la base de datos?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if respuesta != QMessageBox.Yes:
            return

        self.db.execute("DELETE FROM incidentes")
        self.db.commit()
        self.recargar_datos()
        self.historial_limpiado.emit()