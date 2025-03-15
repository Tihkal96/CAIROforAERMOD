# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CAIRO
                                 A QGIS plugin
 AERMOD, AERMAP, and AERPLOT input file compiler and analysis tool with an risk assessment module
                              -------------------
        begin                : 2025-02-23
        git sha              : $Format:%H$
        copyright            : (C) 2025 by MSc Dominik Subotić
        email                : suboticdominik@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt, QThread, pyqtSignal, QProcess, QVariant
from qgis.PyQt.QtGui import QIcon, QPixmap, QFont, QEnterEvent, QColor
from qgis.PyQt.QtWidgets import (QAction, QDialog, QCheckBox, QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout,
                                 QHBoxLayout, QApplication,
                                 QFileDialog, QComboBox, QLineEdit, QFrame, QScrollArea, QGridLayout, QMessageBox)
from qgis._core import QgsLineSymbol
from qgis.core import (QgsProject, QgsVectorLayer, QgsCoordinateReferenceSystem, QgsFeature, QgsGeometry, QgsPointXY,
                       QgsSingleSymbolRenderer, QgsFillSymbol, Qgis, QgsWkbTypes, QgsLineSymbol, QgsVectorLayer,
                       QgsProject, QgsWkbTypes)
from qgis.gui import QgsMapToolEmitPoint, QgsMapTool, QgsRubberBand
from qgis.utils import iface
from qgis.core import Qgis, QgsFields, QgsField, QgsSimpleFillSymbolLayer, QgsSymbol
import os.path
import os
import math

from shutil import copyfile
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import QUrl, QEventLoop

from .resources import *




class Tooltip(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.ToolTip)
        self.setStyleSheet("""
            QLabel {
                background-color: #ffffe0;  /* Light yellow background */
                border: 1px solid black;   /* Black border */
                padding: 2px;              /* Padding for text */
                font: 10pt "Arial";        /* Font size and family */
            }
        """)
        self.hide()


class TooltipMixin:
    def setTooltip(self, widget, text):
        tooltip = Tooltip(iface.mainWindow())
        tooltip.setText(text)
        tooltip_text = text

        def enterEvent(event):
            if isinstance(event, QEnterEvent):
                pos = widget.mapToGlobal(widget.rect().bottomLeft())
                tooltip.move(pos.x() + 15, pos.y() + 15)
                tooltip.setText(tooltip_text)
                tooltip.show()

        def leaveEvent(event):
            tooltip.hide()

        widget.enterEvent = enterEvent
        widget.leaveEvent = leaveEvent


def create_aermap_app(parent=None):
    if not os.path.exists("AERMAP_def.txt"):
        raise FileNotFoundError("AERMAP_def.txt not found. Please select a receptor grid type first.")
    with open("AERMAP_def.txt", "r") as file:
        content = file.read().strip()
    if content == "RECT":
        return RECTApp(parent)
    elif content == "POLAR":
        return POLARApp(parent)
    elif content.startswith("DISCRETE"):
        return DISCRETEApp(parent)
    else:
        raise ValueError(f"Invalid content in AERMAP_def.txt: {content}")


class RECTApp(QMainWindow, TooltipMixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plugin_dir = os.path.dirname(__file__)
        self.datafile_entries = []
        self.clipboard_thread = None
        self.central_widget = None
        self.map_tool = None
        self.title_entry = None
        self.datatype_combo = None
        self.browse_button = None
        self.datafile_frame = None
        self.datafile_layout = None
        self.map_button = None
        self.anchor_long_entry = None
        self.anchor_lat_entry = None
        self.utm_zone_entry = None
        self.utm_datum_entry = None
        self.flagpole_entry = None
        self.x_spacing_entry = None
        self.x_length_entry = None
        self.y_spacing_entry = None
        self.y_length_entry = None
        self.visualize_button = None
        self.visualize_grid_button = None
        self.compile_button = None

        self.initUI()

    def initUI(self):
        self.setWindowTitle("CAIRO © ~ AERMAP Input File Generator © (Rectangular Receptor Grid)")
        self.setGeometry(100, 100, 600, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QGridLayout()
        central_widget.setLayout(layout)

        icon_label = QLabel()
        try:
            icon_pixmap = QPixmap(os.path.join(self.plugin_dir, "CAIRO.png"))
            icon_label.setPixmap(icon_pixmap)
        except Exception as e:
            print(f"Error loading icon: {e}")

        icon_label.setAlignment(Qt.AlignCenter)

        text_label = QLabel(
            "AERMAP Input File Generator ©\nCAIRO © for AERMOD, 2025.\nMSc Dominik Subotić @UNIVPM\n\n"
            "Hover over labels for information \nTab for next, Shift+Tab for back\nRequires 3rd party elevation data"
        )
        text_label.setFont(QFont('Arial', 8))
        text_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(icon_label, 0, 0)
        layout.addWidget(text_label, 0, 2, 1, 1)

        title_label = QLabel("Title")
        title_label.setFont(QFont('Arial', 8))
        self.title_entry = QLineEdit()
        self.title_entry.setFont(QFont('Arial', 8))
        layout.addWidget(title_label, 1, 0)
        layout.addWidget(self.title_entry, 1, 1)
        self.setTooltip(title_label, "Repeat title throughout analysis")

        datatype_label = QLabel("Data Type")
        datatype_label.setFont(QFont('Arial', 8))
        self.datatype_combo = QComboBox()
        self.datatype_combo.addItems(["NED", "DEM1", "DEM7"])
        self.datatype_combo.setFont(QFont('Arial', 8))
        layout.addWidget(datatype_label, 2, 0)
        layout.addWidget(self.datatype_combo, 2, 1)
        self.setTooltip(datatype_label, "NED includes .tiff files")

        self.browse_button = QPushButton("Elevation Data 📂")
        self.browse_button.clicked.connect(self.browse_files)
        layout.addWidget(self.browse_button, 3, 0)
        self.setTooltip(self.browse_button, "Elevation data will be automatically copied into the Project folder")

        self.datafile_frame = QFrame()
        self.datafile_layout = QVBoxLayout()
        self.datafile_frame.setLayout(self.datafile_layout)
        layout.addWidget(self.datafile_frame, 3, 1)

        self.map_button = QPushButton("Anchor Map Input ✜")
        self.map_button.clicked.connect(self.capture_anchor_point)
        layout.addWidget(self.map_button, 4, 1)
        self.setTooltip(self.map_button, "Click to select anchor point (SW/bottom left corner) on the QGIS map")

        anchor_long_label = QLabel("Anchor Easting")
        self.anchor_long_entry = QLineEdit()
        layout.addWidget(anchor_long_label, 5, 0)
        layout.addWidget(self.anchor_long_entry, 5, 1)
        self.setTooltip(anchor_long_label, "Specifies X coordinate of bottom left grid corner (SW corner)")

        anchor_lat_label = QLabel("Anchor Northing")
        self.anchor_lat_entry = QLineEdit()
        layout.addWidget(anchor_lat_label, 6, 0)
        layout.addWidget(self.anchor_lat_entry, 6, 1)
        self.setTooltip(anchor_lat_label, "Specifies Y coordinate of bottom left grid corner (SW corner)")

        utm_zone_label = QLabel("UTM Zone (0-60)")
        self.utm_zone_entry = QLineEdit()
        layout.addWidget(utm_zone_label, 7, 0)
        layout.addWidget(self.utm_zone_entry, 7, 1)

        utm_datum_label = QLabel("UTM Datum")
        self.utm_datum_entry = QLineEdit("0")
        layout.addWidget(utm_datum_label, 8, 0)
        layout.addWidget(self.utm_datum_entry, 8, 1)
        self.setTooltip(utm_datum_label, "0=No conversion")

        flagpole_label = QLabel("Flagpole (m)")
        self.flagpole_entry = QLineEdit("1.5")
        layout.addWidget(flagpole_label, 9, 0)
        layout.addWidget(self.flagpole_entry, 9, 1)
        self.setTooltip(flagpole_label, "Flagpole/Receptor height")

        x_spacing_label = QLabel("N°of X Columns")
        self.x_spacing_entry = QLineEdit()
        layout.addWidget(x_spacing_label, 10, 0)
        layout.addWidget(self.x_spacing_entry, 10, 1)

        x_length_label = QLabel("ΔX (m)")
        self.x_length_entry = QLineEdit()
        layout.addWidget(x_length_label, 11, 0)
        layout.addWidget(self.x_length_entry, 11, 1)

        y_spacing_label = QLabel("N°of Y Rows")
        self.y_spacing_entry = QLineEdit()
        layout.addWidget(y_spacing_label, 12, 0)
        layout.addWidget(self.y_spacing_entry, 12, 1)

        y_length_label = QLabel("ΔY (m)")
        self.y_length_entry = QLineEdit()
        layout.addWidget(y_length_label, 13, 0)
        layout.addWidget(self.y_length_entry, 13, 1)

        self.visualize_grid_button = QPushButton("Visualize Grid")
        self.visualize_grid_button.clicked.connect(self.visualize_grid)
        layout.addWidget(self.visualize_grid_button, 14, 1)
        self.setTooltip(self.visualize_grid_button, "Visualize the receptor grid as a rectangle on the QGIS map")

        self.compile_button = QPushButton("Compile 📝")
        self.compile_button.clicked.connect(self.compile_output)
        self.compile_button.setFont(QFont('Serif', 10))
        layout.addWidget(self.compile_button, 0, 1)
        self.setTooltip(self.compile_button, "Generate AERMAP input file;\nChoose folder "
                                             "where the aermap.inp will be created")

    def browse_files(self):
        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files",
            "",
            "All Files (*.*)"
        )

        for filename in filenames:
            if filename:
                file_name = os.path.basename(filename)
                entry = QLineEdit(file_name)
                self.datafile_layout.addWidget(entry)
                self.datafile_entries.append((entry, filename))

    def capture_anchor_point(self):
        self.map_tool = QgsMapToolEmitPoint(iface.mapCanvas())
        self.map_tool.canvasClicked.connect(self.set_anchor_coordinates)
        iface.mapCanvas().setMapTool(self.map_tool)

    def set_anchor_coordinates(self, point, button):
        easting = point.x()
        northing = point.y()
        self.anchor_long_entry.setText(str(easting))
        self.anchor_lat_entry.setText(str(northing))
        iface.mapCanvas().unsetMapTool(self.map_tool)
        self.map_tool = None

    def visualize_anchor_point(self):
        try:
            easting = float(self.anchor_long_entry.text())
            northing = float(self.anchor_lat_entry.text())
        except ValueError:
            iface.messageBar().pushMessage("Error", "Invalid coordinates. Please enter valid numbers.",
                                           level=3)
            return

        crs = QgsProject.instance().crs()
        if not crs.isValid():
            iface.messageBar().pushMessage("Error", "No valid CRS set in QGIS project.",
                                           level=3)
            return

        crs = QgsProject.instance().crs()
        if not crs.isValid():
            iface.messageBar().pushMessage("Error", "No valid CRS set in QGIS project.", level=3)
            return

        layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "Anchor Point", "memory")
        QgsProject.instance().addMapLayer(layer)

        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(easting, northing)))
        layer.dataProvider().addFeatures([feature])
        layer.updateExtents()

        iface.mapCanvas().setExtent(layer.extent())
        iface.mapCanvas().refresh()

    def visualize_grid(self):
        try:
            anchor_easting = float(self.anchor_long_entry.text())
            anchor_northing = float(self.anchor_lat_entry.text())
            x_spacing = int(self.x_spacing_entry.text())
            x_length = float(self.x_length_entry.text())
            y_spacing = int(self.y_spacing_entry.text())
            y_length = float(self.y_length_entry.text())
        except ValueError:
            iface.messageBar().pushMessage("Error", "Invalid input. Please enter valid numbers for all fields.",
                                           level=3)
            return

        width = x_spacing * x_length
        height = y_spacing * y_length

        points = [
            QgsPointXY(anchor_easting, anchor_northing),
            QgsPointXY(anchor_easting + width, anchor_northing),
            QgsPointXY(anchor_easting + width, anchor_northing + height),
            QgsPointXY(anchor_easting, anchor_northing + height)
        ]

        crs = QgsProject.instance().crs()
        if not crs.isValid():
            iface.messageBar().pushMessage("Error", "No valid CRS set in QGIS project.", level=3)
            return

        layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "Receptor Grid", "memory")
        QgsProject.instance().addMapLayer(layer)

        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPolygonXY([points]))
        layer.dataProvider().addFeatures([feature])
        layer.updateExtents()

        symbol = QgsFillSymbol()
        symbol.setColor(QColor(255, 0, 0, 100))
        renderer = QgsSingleSymbolRenderer(symbol)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

        iface.mapCanvas().setExtent(layer.extent())
        iface.mapCanvas().refresh()

    def generate_output(self):
        output = "CO STARTING\n"

        if self.title_entry.text():
            output += f"CO TITLEONE  {self.title_entry.text()}\n"

        if self.datafile_entries:
            output += f"CO DATATYPE  {self.datatype_combo.currentText()}"
            if self.datatype_combo.currentText() in ["DEM1", "DEM7"]:
                output += "     FILLGAPS\n"
            else:
                output += "\n"

            for entry, full_path in self.datafile_entries:
                filename = os.path.basename(full_path)
                output += f"CO DATAFILE  {filename}\n"

        if all([self.anchor_lat_entry.text(), self.anchor_long_entry.text(),
                self.utm_zone_entry.text(), self.utm_datum_entry.text()]):
            output += (f"CO ANCHORXY  {self.anchor_long_entry.text()} "
                       f"{self.anchor_lat_entry.text()} "
                       f"{self.anchor_long_entry.text()} "
                       f"{self.anchor_lat_entry.text()} "
                       f"{self.utm_zone_entry.text()} "
                       f"{self.utm_datum_entry.text()}\n")

        if self.flagpole_entry.text():
            output += f"CO FLAGPOLE  {self.flagpole_entry.text()}\n"

        output += "CO RUNORNOT  RUN\n"
        output += "CO FINISHED\n"
        output += "RE STARTING\n"

        if all([self.anchor_lat_entry.text(), self.anchor_long_entry.text(),
                self.x_spacing_entry.text(), self.x_length_entry.text(),
                self.y_spacing_entry.text(), self.y_length_entry.text()]):
            output += "   GRIDCART CART01 STA\n"
            output += (f"                    XYINC {self.anchor_long_entry.text()} "
                       f"{self.x_spacing_entry.text()} {self.x_length_entry.text()} "
                       f"{self.anchor_lat_entry.text()} {self.y_spacing_entry.text()} "
                       f"{self.y_length_entry.text()}\n")
            output += "   GRIDCART CART01 END\n"

        output += "RE FINISHED\n"
        output += "OU STARTING\n"
        output += "   RECEPTOR  RECEPT.ROU\n"
        output += "OU FINISHED\n"

        return output

    def compile_output(self):
        output_text = self.generate_output()
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            ""
        )

        if folder_path:
            file_path = os.path.join(folder_path, "aermap.inp")
            try:
                with open(file_path, "w") as file:
                    file.write(output_text)

                for entry, full_path in self.datafile_entries:
                    file_name = os.path.basename(full_path)
                    destination = os.path.join(folder_path, file_name)
                    if not os.path.exists(destination):
                        copyfile(full_path, destination)

                iface.messageBar().pushMessage("Success", "AERMAP input file generated successfully.", level=0)
                self.close()
            except Exception as e:
                iface.messageBar().pushMessage("Error", f"Failed to generate file: {str(e)}", level=2)

    def closeEvent(self, event):
        if self.map_tool:
            iface.mapCanvas().unsetMapTool(self.map_tool)
            self.map_tool = None
        if self.clipboard_thread:
            self.clipboard_thread.stop()
            self.clipboard_thread.wait()
        event.accept()


class POLARApp(QMainWindow, TooltipMixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plugin_dir = os.path.dirname(__file__)
        self.datafile_entries = []
        self.clipboard_thread = None
        self.central_widget = None
        self.map_tool = None
        self.title_entry = None
        self.datatype_combo = None
        self.browse_button = None
        self.datafile_frame = None
        self.datafile_layout = None
        self.map_button = None
        self.anchor_long_entry = None
        self.anchor_lat_entry = None
        self.utm_zone_entry = None
        self.utm_datum_entry = None
        self.flagpole_entry = None
        self.n_radial_entry = None
        self.n_rings_entry = None
        self.ring_spacing_entry = None
        self.visualize_button = None
        self.visualize_grid_button = None
        self.compile_button = None

        self.initUI()

    def initUI(self):
        self.setWindowTitle("CAIRO © ~ AERMAP Input File Generator © (Polar Receptor Grid)")
        self.setGeometry(100, 100, 600, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QGridLayout()
        central_widget.setLayout(layout)

        icon_label = QLabel()
        try:
            icon_pixmap = QPixmap(os.path.join(self.plugin_dir, "CAIRO.png"))
            icon_label.setPixmap(icon_pixmap)
        except Exception as e:
            print(f"Error loading icon: {e}")

        icon_label.setAlignment(Qt.AlignCenter)

        text_label = QLabel(
            "AERMAP Input File Generator ©\nCAIRO © for AERMOD, 2025.\nMSc Dominik Subotić @UNIVPM\n\n"
            "Hover over labels for information \nTab for next, Shift+Tab for back\nRequires 3rd party elevation data"
        )
        text_label.setFont(QFont('Arial', 8))
        text_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(icon_label, 0, 0)
        layout.addWidget(text_label, 0, 2, 1, 1)

        title_label = QLabel("Title")
        title_label.setFont(QFont('Arial', 8))
        self.title_entry = QLineEdit()
        self.title_entry.setFont(QFont('Arial', 8))
        layout.addWidget(title_label, 1, 0)
        layout.addWidget(self.title_entry, 1, 1)
        self.setTooltip(title_label, "Repeat title throughout analysis")

        datatype_label = QLabel("Data Type")
        datatype_label.setFont(QFont('Arial', 8))
        self.datatype_combo = QComboBox()
        self.datatype_combo.addItems(["NED", "DEM1", "DEM7"])
        self.datatype_combo.setFont(QFont('Arial', 8))
        layout.addWidget(datatype_label, 2, 0)
        layout.addWidget(self.datatype_combo, 2, 1)
        self.setTooltip(datatype_label, "NED includes .tiff files")

        self.browse_button = QPushButton("Elevation Data 📂")
        self.browse_button.clicked.connect(self.browse_files)
        layout.addWidget(self.browse_button, 3, 0)
        self.setTooltip(self.browse_button, "Elevation data will be automatically copied into the Project folder")

        self.datafile_frame = QFrame()
        self.datafile_layout = QVBoxLayout()
        self.datafile_frame.setLayout(self.datafile_layout)
        layout.addWidget(self.datafile_frame, 3, 1)

        self.map_button = QPushButton("Origin Map Input ✜")
        self.map_button.clicked.connect(self.capture_anchor_point)
        layout.addWidget(self.map_button, 4, 1)
        self.setTooltip(self.map_button, "Click to select origin point (center point) on the QGIS map")

        anchor_long_label = QLabel("Origin Easting")
        self.anchor_long_entry = QLineEdit()
        layout.addWidget(anchor_long_label, 5, 0)
        layout.addWidget(self.anchor_long_entry, 5, 1)
        self.setTooltip(anchor_long_label, "Specifies X coordinate of the grid center)")

        anchor_lat_label = QLabel("Origin Northing")
        self.anchor_lat_entry = QLineEdit()
        layout.addWidget(anchor_lat_label, 6, 0)
        layout.addWidget(self.anchor_lat_entry, 6, 1)
        self.setTooltip(anchor_lat_label, "Specifies Y coordinate of the grid center")

        utm_zone_label = QLabel("UTM Zone (0-60)")
        self.utm_zone_entry = QLineEdit()
        layout.addWidget(utm_zone_label, 7, 0)
        layout.addWidget(self.utm_zone_entry, 7, 1)

        utm_datum_label = QLabel("UTM Datum")
        self.utm_datum_entry = QLineEdit("0")
        layout.addWidget(utm_datum_label, 8, 0)
        layout.addWidget(self.utm_datum_entry, 8, 1)
        self.setTooltip(utm_datum_label, "0=No conversion")

        flagpole_label = QLabel("Flagpole (m)")
        self.flagpole_entry = QLineEdit("1.5")
        layout.addWidget(flagpole_label, 9, 0)
        layout.addWidget(self.flagpole_entry, 9, 1)
        self.setTooltip(flagpole_label, "Flagpole/Receptor height")

        n_radial_label = QLabel("N°of Radial Grid Directions")
        self.n_radial_entry = QLineEdit()
        layout.addWidget(n_radial_label, 10, 0)
        layout.addWidget(self.n_radial_entry, 10, 1)

        n_rings_label = QLabel("N°of Concentric Rings")
        self.n_rings_entry = QLineEdit()
        layout.addWidget(n_rings_label, 11, 0)
        layout.addWidget(self.n_rings_entry, 11, 1)

        ring_spacing_label = QLabel("Δ Rings (m)")
        self.ring_spacing_entry = QLineEdit()
        layout.addWidget(ring_spacing_label, 12, 0)
        layout.addWidget(self.ring_spacing_entry, 12, 1)
        self.setTooltip(ring_spacing_label, "Distance between concentric grid rings in meters")

        self.visualize_grid_button = QPushButton("Visualize Grid")
        self.visualize_grid_button.clicked.connect(self.visualize_grid)
        layout.addWidget(self.visualize_grid_button, 13, 1)
        self.setTooltip(self.visualize_grid_button, "Visualize the receptor grid as a circle on the QGIS map")

        self.compile_button = QPushButton("Compile 📝")
        self.compile_button.clicked.connect(self.compile_output)
        self.compile_button.setFont(QFont('Serif', 10))
        layout.addWidget(self.compile_button, 0, 1)
        self.setTooltip(self.compile_button, "Generate AERMAP input file;\nChoose folder "
                                             "where the aermap.inp will be created")

    def browse_files(self):
        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files",
            "",
            "All Files (*.*)"
        )

        for filename in filenames:
            if filename:
                file_name = os.path.basename(filename)
                entry = QLineEdit(file_name)
                self.datafile_layout.addWidget(entry)
                self.datafile_entries.append((entry, filename))

    def capture_anchor_point(self):
        self.map_tool = QgsMapToolEmitPoint(iface.mapCanvas())
        self.map_tool.canvasClicked.connect(self.set_anchor_coordinates)
        iface.mapCanvas().setMapTool(self.map_tool)

    def set_anchor_coordinates(self, point, button):
        easting = point.x()
        northing = point.y()
        self.anchor_long_entry.setText(str(easting))
        self.anchor_lat_entry.setText(str(northing))
        iface.mapCanvas().unsetMapTool(self.map_tool)
        self.map_tool = None

    def visualize_anchor_point(self):
        try:
            easting = float(self.anchor_long_entry.text())
            northing = float(self.anchor_lat_entry.text())
        except ValueError:
            iface.messageBar().pushMessage("Error", "Invalid coordinates. Please enter valid numbers.",
                                           level=3)
            return

        crs = QgsProject.instance().crs()
        if not crs.isValid():
            iface.messageBar().pushMessage("Error", "No valid CRS set in QGIS project.",
                                           level=3)
            return

        layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "Anchor Point", "memory")
        QgsProject.instance().addMapLayer(layer)

        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(easting, northing)))
        layer.dataProvider().addFeatures([feature])
        layer.updateExtents()

        iface.mapCanvas().setExtent(layer.extent())
        iface.mapCanvas().refresh()

    def visualize_grid(self):
        try:
            anchor_easting = float(self.anchor_long_entry.text())
            anchor_northing = float(self.anchor_lat_entry.text())
            n_rings = int(self.n_rings_entry.text())
            ring_spacing = float(self.ring_spacing_entry.text())
        except ValueError:
            iface.messageBar().pushMessage("Error", "Invalid input. Please enter valid numbers for all fields.",
                                           level=3)
            return

        radius = n_rings * ring_spacing

        crs = QgsProject.instance().crs()
        if not crs.isValid():
            iface.messageBar().pushMessage("Error", "No valid CRS set in QGIS project.", level=3)
            return

        points = []
        num_points = 360
        for i in range(num_points):
            angle = math.radians(i * (360 / num_points))
            x = anchor_easting + radius * math.cos(angle)
            y = anchor_northing + radius * math.sin(angle)
            points.append(QgsPointXY(x, y))
        points.append(points[0])

        layer = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "Polar Receptor Grid", "memory")
        QgsProject.instance().addMapLayer(layer)

        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPolygonXY([points]))
        layer.dataProvider().addFeatures([feature])
        layer.updateExtents()

        symbol = QgsFillSymbol()
        symbol.setColor(QColor(255, 0, 0, 100))
        renderer = QgsSingleSymbolRenderer(symbol)
        layer.setRenderer(renderer)
        layer.triggerRepaint()

        iface.mapCanvas().setExtent(layer.extent())
        iface.mapCanvas().refresh()

    def generate_output(self):
        output = "CO STARTING\n"

        if self.title_entry.text():
            output += f"CO TITLEONE  {self.title_entry.text()}\n"

        if self.datafile_entries:
            output += f"CO DATATYPE  {self.datatype_combo.currentText()}"
            if self.datatype_combo.currentText() in ["DEM1", "DEM7"]:
                output += "     FILLGAPS\n"
            else:
                output += "\n"

            for entry, full_path in self.datafile_entries:
                filename = os.path.basename(full_path)
                output += f"CO DATAFILE  {filename}\n"

        if all([self.anchor_lat_entry.text(), self.anchor_long_entry.text(),
                self.utm_zone_entry.text(), self.utm_datum_entry.text()]):
            output += (f"   ANCHORXY  {self.anchor_long_entry.text()} "
                       f"{self.anchor_lat_entry.text()} "
                       f"{self.anchor_long_entry.text()} "
                       f"{self.anchor_lat_entry.text()} "
                       f"{self.utm_zone_entry.text()} "
                       f"{self.utm_datum_entry.text()}\n")

        if self.flagpole_entry.text():
            output += f"   FLAGPOLE  {self.flagpole_entry.text()}\n"

        output += "CO RUNORNOT  RUN\n"
        output += "CO FINISHED\n"
        output += "RE STARTING\n"

        if all([self.anchor_lat_entry.text(), self.anchor_long_entry.text(),
                self.n_radial_entry.text(), self.n_rings_entry.text(),
                self.ring_spacing_entry.text()]):
            output += "   GRIDPOLR POL1 STA\n"
            output += (f"                    ORIG {self.anchor_long_entry.text()} "
                       f"{self.anchor_lat_entry.text()}\n")

            try:
                n_rings = int(self.n_rings_entry.text())
                ring_spacing = float(self.ring_spacing_entry.text())
                distances = [str(ring_spacing * (i + 1)) for i in range(n_rings)]
                output += f"                    DIST {' '.join(distances)}\n"
            except ValueError:
                output += "                    DIST 0\n"

            try:
                n_radial = int(self.n_radial_entry.text())
                angle_increment = 360 / n_radial
                output += f"                    GDIR {n_radial} 0 {angle_increment}\n"
            except ValueError:
                output += "                    GDIR 0 0 0\n"

            output += "   GRIDPOLR POL1 END\n"

        output += "RE FINISHED\n"
        output += "OU STARTING\n"
        output += "   RECEPTOR  RECEPT.ROU\n"
        output += "OU FINISHED\n"

        return output

    def compile_output(self):
        output_text = self.generate_output()
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            ""
        )

        if folder_path:
            file_path = os.path.join(folder_path, "aermap.inp")
            try:
                with open(file_path, "w") as file:
                    file.write(output_text)

                for entry, full_path in self.datafile_entries:
                    file_name = os.path.basename(full_path)
                    destination = os.path.join(folder_path, file_name)
                    if not os.path.exists(destination):
                        copyfile(full_path, destination)

                iface.messageBar().pushMessage("Success", "AERMAP input file generated successfully.", level=0)
                self.close()
            except Exception as e:
                iface.messageBar().pushMessage("Error", f"Failed to generate file: {str(e)}", level=2)

    def closeEvent(self, event):
        if self.map_tool:
            iface.mapCanvas().unsetMapTool(self.map_tool)
            self.map_tool = None
        if self.clipboard_thread:
            self.clipboard_thread.stop()
            self.clipboard_thread.wait()
        event.accept()


class DISCRETEApp(QMainWindow, TooltipMixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plugin_dir = os.path.dirname(__file__)
        self.datafile_entries = []
        self.clipboard_thread = None
        self.central_widget = None
        self.map_tool = None
        self.title_entry = None
        self.datatype_combo = None
        self.browse_button = None
        self.datafile_frame = None
        self.datafile_layout = None
        self.receptor_frame = None
        self.receptor_widgets = []
        self.map_button = None
        self.e_entry = None
        self.n_entry = None
        self.h_entry = None
        self.utm_zone_entry = None
        self.utm_datum_entry = None
        self.flagpole_entry = None
        self.visualize_button = None
        self.visualize_grid_button = None
        self.num_receptors = self.get_num_receptors()
        self.compile_button = None

        self.initUI()

    def get_num_receptors(self):
        try:
            with open("AERMAP_def.txt", "r") as file:
                content = file.read().strip()
                if content.startswith("DISCRETE"):
                    return int(content.split()[1])
                else:
                    raise ValueError("File does not indicate DISCRETE receptors")
        except (FileNotFoundError, IndexError, ValueError) as e:
            iface.messageBar().pushMessage("Error", f"Failed to read AERMAP_def.txt: {str(e)}", level=2)
            return 0

    def initUI(self):
        self.setWindowTitle("CAIRO © ~ AERMAP Input File Generator © (Discrete Receptors)")
        self.setGeometry(100, 100, 600, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QGridLayout()
        central_widget.setLayout(layout)

        icon_label = QLabel()
        try:
            icon_pixmap = QPixmap(os.path.join(self.plugin_dir, "CAIRO.png"))
            icon_label.setPixmap(icon_pixmap)
        except Exception as e:
            print(f"Error loading icon: {e}")

        icon_label.setAlignment(Qt.AlignCenter)

        text_label = QLabel(
            "AERMAP Input File Generator ©\nCAIRO © for AERMOD, 2025.\nMSc Dominik Subotić @UNIVPM\n\n"
            "Hover over labels for information \nTab for next, Shift+Tab for back\nRequires 3rd party elevation data"
        )
        text_label.setFont(QFont('Arial', 8))
        text_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(icon_label, 0, 0)
        layout.addWidget(text_label, 0, 2, 1, 1)

        title_label = QLabel("Title")
        title_label.setFont(QFont('Arial', 8))
        self.title_entry = QLineEdit()
        self.title_entry.setFont(QFont('Arial', 8))
        layout.addWidget(title_label, 1, 0)
        layout.addWidget(self.title_entry, 1, 1)
        self.setTooltip(title_label, "Repeat title throughout analysis")

        datatype_label = QLabel("Data Type")
        datatype_label.setFont(QFont('Arial', 8))
        self.datatype_combo = QComboBox()
        self.datatype_combo.addItems(["NED", "DEM1", "DEM7"])
        self.datatype_combo.setFont(QFont('Arial', 8))
        layout.addWidget(datatype_label, 2, 0)
        layout.addWidget(self.datatype_combo, 2, 1)
        self.setTooltip(datatype_label, "NED includes .tiff files")

        self.browse_button = QPushButton("Elevation Data 📂")
        self.browse_button.clicked.connect(self.browse_files)
        layout.addWidget(self.browse_button, 3, 0)
        self.setTooltip(self.browse_button, "Elevation data will be automatically copied into the Project folder")

        self.datafile_frame = QFrame()
        self.datafile_layout = QVBoxLayout()
        self.datafile_frame.setLayout(self.datafile_layout)
        layout.addWidget(self.datafile_frame, 3, 1)

        self.receptor_frame = QFrame()
        receptor_layout = QVBoxLayout()
        self.receptor_frame.setLayout(receptor_layout)

        for i in range(self.num_receptors):
            receptor_row = QWidget()
            row_layout = QGridLayout()
            receptor_row.setLayout(row_layout)

            visualize_button = QPushButton(f"Visualize Receptor{i + 1}")
            visualize_button.clicked.connect(lambda checked, idx=i: self.visualize_anchor_point(idx))
            row_layout.addWidget(visualize_button, 0, 0)
            self.setTooltip(visualize_button, f"Visualize manually entered receptor {i + 1} on the QGIS map")

            map_button = QPushButton(f"Map {i + 1} ✜")
            map_button.clicked.connect(lambda checked, idx=i: self.capture_anchor_point(idx))
            row_layout.addWidget(map_button, 1, 0)
            self.setTooltip(map_button, f"Click to select receptor {i + 1} on the QGIS map")

            e_label = QLabel(f"Easting {i + 1}")
            e_entry = QLineEdit()
            row_layout.addWidget(e_label, 0, 1)
            row_layout.addWidget(e_entry, 1, 1)
            self.setTooltip(e_label, f"Specifies X coordinate of receptor {i + 1}")

            n_label = QLabel(f"Northing {i + 1}")
            n_entry = QLineEdit()
            row_layout.addWidget(n_label, 0, 2)
            row_layout.addWidget(n_entry, 1, 2)
            self.setTooltip(n_label, f"Specifies Y coordinate of receptor {i + 1}")

            h_label = QLabel(f"Height {i + 1}")
            h_entry = QLineEdit("0")
            row_layout.addWidget(h_label, 0, 3)
            row_layout.addWidget(h_entry, 1, 3)
            self.setTooltip(h_label, f"Receptor {i + 1} Height (m)")

            receptor_layout.addWidget(receptor_row)

            self.receptor_widgets.append({
                "visualize_button": visualize_button,
                "map_button": map_button,
                "e_entry": e_entry,
                "n_entry": n_entry,
                "h_entry": h_entry
            })

        layout.addWidget(self.receptor_frame, 4, 0, 2, 3)

        utm_zone_label = QLabel("UTM Zone (0-60)")
        self.utm_zone_entry = QLineEdit()
        layout.addWidget(utm_zone_label, 5, 0)
        layout.addWidget(self.utm_zone_entry, 5, 1)

        utm_datum_label = QLabel("UTM Datum")
        self.utm_datum_entry = QLineEdit("0")
        layout.addWidget(utm_datum_label, 6, 0)
        layout.addWidget(self.utm_datum_entry, 6, 1)
        self.setTooltip(utm_datum_label, "0=No conversion")

        flagpole_label = QLabel("Flagpole (m)")
        self.flagpole_entry = QLineEdit("1.5")
        layout.addWidget(flagpole_label, 7, 0)
        layout.addWidget(self.flagpole_entry, 7, 1)
        self.setTooltip(flagpole_label, "Flagpole/Receptor height")

        self.visualize_grid_button = QPushButton("Visualize Receptors")
        self.visualize_grid_button.clicked.connect(self.visualize_grid)
        layout.addWidget(self.visualize_grid_button, 8, 1)
        self.setTooltip(self.visualize_grid_button, "Visualize all discrete receptors in the QGIS map")

        self.compile_button = QPushButton("Compile 📝")
        self.compile_button.clicked.connect(self.compile_output)
        self.compile_button.setFont(QFont('Serif', 10))
        layout.addWidget(self.compile_button, 0, 1)
        self.setTooltip(self.compile_button, "Generate AERMAP input file;\nChoose folder "
                                             "where the aermap.inp will be created")

    def browse_files(self):
        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files",
            "",
            "All Files (*.*)"
        )

        for filename in filenames:
            if filename:
                file_name = os.path.basename(filename)
                entry = QLineEdit(file_name)
                self.datafile_layout.addWidget(entry)
                self.datafile_entries.append((entry, filename))

    def capture_anchor_point(self, receptor_idx):
        self.map_tool = QgsMapToolEmitPoint(iface.mapCanvas())
        self.map_tool.canvasClicked.connect(
            lambda point, button, idx=receptor_idx: self.set_anchor_coordinates(point, button, idx))
        iface.mapCanvas().setMapTool(self.map_tool)

    def set_anchor_coordinates(self, point, button, receptor_idx):
        easting = point.x()
        northing = point.y()
        if not (0 <= receptor_idx < len(self.receptor_widgets)):
            iface.messageBar().pushMessage("Error", f"Invalid receptor index: {receptor_idx}", level=2)
            iface.mapCanvas().unsetMapTool(self.map_tool)
            self.map_tool = None
            return

        receptor = self.receptor_widgets[receptor_idx]
        if not isinstance(receptor, dict):
            iface.messageBar().pushMessage("Error",
                                           f"Expected dict at receptor_widgets[{receptor_idx}], got {type(receptor)}",
                                           level=2)
            iface.mapCanvas().unsetMapTool(self.map_tool)
            self.map_tool = None
            return

        if "e_entry" not in receptor or "n_entry" not in receptor:
            iface.messageBar().pushMessage("Error",
                                           f"Missing 'e_entry' or 'n_entry' in receptor {receptor_idx}: "
                                           f"{receptor.keys()}",
                                           level=2)
            iface.mapCanvas().unsetMapTool(self.map_tool)
            self.map_tool = None
            return

        e_entry = receptor["e_entry"]
        n_entry = receptor["n_entry"]
        if not isinstance(e_entry, QLineEdit) or not isinstance(n_entry, QLineEdit):
            iface.messageBar().pushMessage("Error",
                                           f"Invalid widget types at receptor {receptor_idx}: e_entry={type(e_entry)}, n_entry={type(n_entry)}",
                                           level=2)
            iface.mapCanvas().unsetMapTool(self.map_tool)
            self.map_tool = None
            return

        e_entry.setText(str(easting))
        n_entry.setText(str(northing))

        iface.mapCanvas().unsetMapTool(self.map_tool)
        self.map_tool = None

    def visualize_anchor_point(self, receptor_idx):
        try:
            easting = float(self.receptor_widgets[receptor_idx]["e_entry"].text())
            northing = float(self.receptor_widgets[receptor_idx]["n_entry"].text())
        except ValueError:
            iface.messageBar().pushMessage("Error", f"Invalid coordinates for receptor {receptor_idx + 1}.", level=3)
            return

        crs = QgsProject.instance().crs()
        if not crs.isValid():
            iface.messageBar().pushMessage("Error", "No valid CRS set in QGIS project.", level=3)
            return

        layer = QgsVectorLayer(f"Point?crs={crs.authid()}",
                               f"Receptor {receptor_idx + 1}", "memory")
        QgsProject.instance().addMapLayer(layer)

        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(easting, northing)))
        layer.dataProvider().addFeatures([feature])
        layer.updateExtents()

        iface.mapCanvas().setExtent(layer.extent())
        iface.mapCanvas().refresh()

    def visualize_grid(self):
        crs = QgsProject.instance().crs()
        if not crs.isValid():
            iface.messageBar().pushMessage("Error", "No valid CRS set in QGIS project.", level=3)
            return

        layer = QgsVectorLayer(f"Point?crs={crs.authid()}", "All Discrete Receptors", "memory")

        fields = QgsFields()
        fields.append(QgsField("Receptor_ID", QVariant.Int))  # Add a field for receptor ID
        layer.dataProvider().addAttributes(fields)  # Add the fields to the layer
        layer.updateFields()

        QgsProject.instance().addMapLayer(layer)

        features = []
        for i, receptor in enumerate(self.receptor_widgets):
            try:
                easting = float(receptor["e_entry"].text())
                northing = float(receptor["n_entry"].text())
            except ValueError:
                iface.messageBar().pushMessage("Warning", f"Invalid coordinates for receptor {i + 1}, skipping.",
                                               level=3)
                continue

            feature = QgsFeature(layer.fields())
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(easting, northing)))
            feature.setAttributes([i + 1])
            features.append(feature)

        if not features:
            iface.messageBar().pushMessage("Error", "No valid receptor coordinates to visualize.", level=3)
            QgsProject.instance().removeMapLayer(layer)
            return

        layer.dataProvider().addFeatures(features)
        layer.updateExtents()

        iface.mapCanvas().setExtent(layer.extent())
        iface.mapCanvas().refresh()

    def generate_output(self):
        output = "CO STARTING\n"

        if self.title_entry.text():
            output += f"CO TITLEONE  {self.title_entry.text()}\n"

        if self.datafile_entries:
            output += f"CO DATATYPE  {self.datatype_combo.currentText()}"
            if self.datatype_combo.currentText() in ["DEM1", "DEM7"]:
                output += "     FILLGAPS\n"
            else:
                output += "\n"

            for entry, full_path in self.datafile_entries:
                filename = os.path.basename(full_path)
                output += f"CO DATAFILE  {filename}\n"

            if (self.receptor_widgets and
                    self.receptor_widgets[0]["e_entry"].text() and
                    self.receptor_widgets[0]["n_entry"].text() and
                    self.utm_zone_entry.text() and
                    self.utm_datum_entry.text()):
                first_easting = self.receptor_widgets[0]["e_entry"].text()
                first_northing = self.receptor_widgets[0]["n_entry"].text()
                output += (f"   ANCHORXY  {first_easting} "
                           f"{first_northing} "
                           f"{first_easting} "
                           f"{first_northing} "
                           f"{self.utm_zone_entry.text()} "
                           f"{self.utm_datum_entry.text()}\n")

            if self.flagpole_entry.text():
                output += f"   FLAGPOLE  {self.flagpole_entry.text()}\n"

            output += "CO RUNORNOT  RUN\n"
            output += "CO FINISHED\n"
            output += "RE STARTING\n"

            for receptor in self.receptor_widgets:
                e = receptor["e_entry"].text()
                n = receptor["n_entry"].text()
                h = receptor["h_entry"].text() or "0.0"
                if e and n:
                    output += f"   DISCCART     {e}    {n}     {h}     {h}\n"

        output += "RE FINISHED\n"
        output += "OU STARTING\n"
        output += "   RECEPTOR  RECEPT.ROU\n"
        output += "OU FINISHED\n"

        return output

    def compile_output(self):
        output_text = self.generate_output()
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            ""
        )

        if folder_path:
            file_path = os.path.join(folder_path, "aermap.inp")
            try:
                with open(file_path, "w") as file:
                    file.write(output_text)

                for entry, full_path in self.datafile_entries:
                    file_name = os.path.basename(full_path)
                    destination = os.path.join(folder_path, file_name)
                    if not os.path.exists(destination):
                        copyfile(full_path, destination)

                iface.messageBar().pushMessage("Success", "AERMAP input file generated successfully.", level=0)
                self.close()
            except Exception as e:
                iface.messageBar().pushMessage("Error", f"Failed to generate file: {str(e)}", level=2)

    def closeEvent(self, event):
        if self.map_tool:
            iface.mapCanvas().unsetMapTool(self.map_tool)
            self.map_tool = None
        if self.clipboard_thread:
            self.clipboard_thread.stop()
            self.clipboard_thread.wait()
        event.accept()


class ReceptorGridDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Receptor Grid Type")
        self.setGeometry(200, 200, 300, 200)
        self.rect_checkbox = None
        self.polar_checkbox = None
        self.discrete_checkbox = None
        self.discrete_input = None
        self.ok_button = None
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        self.rect_checkbox = QCheckBox("Rectangular receptor grid")
        layout.addWidget(self.rect_checkbox)

        self.polar_checkbox = QCheckBox("Polar receptor grid")
        layout.addWidget(self.polar_checkbox)

        self.discrete_checkbox = QCheckBox("Discrete receptors")
        layout.addWidget(self.discrete_checkbox)

        self.discrete_input = QLineEdit()
        self.discrete_input.setPlaceholderText("Enter N° of receptors")
        self.discrete_input.setEnabled(False)
        layout.addWidget(self.discrete_input)

        self.rect_checkbox.stateChanged.connect(self.on_rect_checkbox_changed)
        self.polar_checkbox.stateChanged.connect(self.on_polar_checkbox_changed)
        self.discrete_checkbox.stateChanged.connect(self.on_discrete_checkbox_changed)

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.on_ok_clicked)
        layout.addWidget(self.ok_button)

        self.setLayout(layout)

    def on_rect_checkbox_changed(self, state):
        if state == Qt.Checked:
            self.polar_checkbox.setChecked(False)
            self.discrete_checkbox.setChecked(False)
            self.discrete_input.setEnabled(False)

    def on_polar_checkbox_changed(self, state):
        if state == Qt.Checked:
            self.rect_checkbox.setChecked(False)
            self.discrete_checkbox.setChecked(False)
            self.discrete_input.setEnabled(False)

    def on_discrete_checkbox_changed(self, state):
        if state == Qt.Checked:
            self.rect_checkbox.setChecked(False)
            self.polar_checkbox.setChecked(False)
            self.discrete_input.setEnabled(True)
        else:
            self.discrete_input.setEnabled(False)

    def on_ok_clicked(self):
        if self.rect_checkbox.isChecked():
            option = "RECT"
        elif self.polar_checkbox.isChecked():
            option = "POLAR"
        elif self.discrete_checkbox.isChecked():
            num_receptors = self.discrete_input.text().strip()
            if not num_receptors.isdigit():
                QMessageBox.warning(self, "Invalid Input", "Please enter a valid number for discrete receptors.")
                return
            option = f"DISCRETE {num_receptors}"
        else:
            QMessageBox.warning(self, "No Selection", "Please select a receptor grid type.")
            return

        with open("AERMAP_def.txt", "w") as file:
            file.write(option)

        self.accept()
        try:
            aermap_app = create_aermap_app(self.parent())
            aermap_app.show()
        except (FileNotFoundError, ValueError) as e:
            QMessageBox.critical(self, "Error", str(e))


class AERMODApp(QMainWindow, TooltipMixin):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plugin_dir = os.path.dirname(__file__)
        self.source_counts = self.read_aermod_def()

        self.pointsource_entries = []
        self.polygon_area_source_entries = []
        self.map_entries = []
        self.sfc_entries = []
        self.prof_entries = []

        self.central_widget = None
        self.layout = None
        self.title_entry = None
        self.utmcopy_entry = None
        self.utmzonecopy_combo = None
        self.pollutant_entry = None
        self.flagpole_entry = None
        self.base_elevation_entry = None
        self.browse_button = None
        self.datafile_frame = None
        self.datafile_layout = None
        self.chosen_file_entry_map_output = None
        self.chosen_file_entry_sfc_output = None
        self.chosen_file_entry_prof_output = None
        self.compile_button = None
        self.avg_periods = self.read_aermod_def()
        self.avg_period_widgets = []
        self.urban_count = None
        self.normal_count = None
        self.normal_pointsource_entries = []
        self.urban_pointsource_entries = []
        self.station_num_entry = None
        self.upper_air_station_num_entry = None
        self.start_year_entry = None
        self.start_year_upper_air_entry = None
        self.start_date_entry = None
        self.end_date_entry = None
        self.rec_table_entry = None
        self.max_table_entry = None
        self.avg_period_frame = None
        self.capture_point_source = None
        self.avg_entry = None
        self.polygon_area_source_frame = None
        self.map_tool = None
        self.set_point_source_coordinates = None
        self.normal_area_source_entries = []
        self.urban_area_source_entries = []
        self.normal_area_source_frame = None
        self.urban_area_source_frame = None
        self.polygon_entry = []
        self.normal_area_count = None
        self.capture_area_source = None
        self.visualize_area_source = None
        self.normal_volume_source_frame = None
        self.urban_volume_source_frame = None
        self.normal_volume_source_entries = []
        self.urban_volume_source_entries = []
        self.normal_pointsource_entries = []
        self.urban_pointsource_entries = []
        self.temp_layer = None
        self.normal_line_source_frame = None
        self.urban_line_source_frame = None
        self.normal_line_source_entries = []
        self.urban_line_source_entries = []
        self.visualize_line_source = None
        self.capture_line_source = None
        self.normal_group_frame = None
        self.normal_group_entries = []
        self.urban_areas_frame = None
        self.urban_areas_entries = []

        self.initUI()

    class TwoPointMapTool(QgsMapTool):

        def __init__(self, canvas, callback):
            super().__init__(canvas)
            self.canvas = canvas
            self.callback = callback
            self.points = []
            self.click_count = 0

        def canvasPressEvent(self, event):
            point = self.toMapCoordinates(event.pos())
            self.points.append(point)
            self.click_count += 1
            if self.click_count == 2:
                self.callback(self.points[0], self.points[1])
                self.canvas.unsetMapTool(self)
                self.points = []
                self.click_count = 0

    class MultiPointMapTool(QgsMapTool):

        def __init__(self, canvas, callback, max_points):
            super().__init__(canvas)
            self.canvas = canvas
            self.callback = callback
            self.max_points = max_points
            self.points = []
            self.click_count = 0

        def canvasPressEvent(self, event):
            point = self.toMapCoordinates(event.pos())
            self.points.append(point)
            self.click_count += 1
            if self.click_count == self.max_points:
                self.callback(self.points)
                self.canvas.unsetMapTool(self)
                self.points = []
                self.click_count = 0

    def read_aermod_def(self):
        try:
            file_path = "AERMOD_def.txt"
            print(f"Looking for AERMOD_def.txt in: {os.getcwd()}")
            with open(file_path, "r") as file:
                lines = file.readlines()
            source_counts = {}
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 2:
                    if parts[0] in ["POINT", "LINE", "AREA", "VOLUME"]:
                        if len(parts) == 3:
                            source_counts[parts[0]] = (parts[1], parts[2])
                        else:
                            print(f"Invalid format for {parts[0]}: {line.strip()}")
                    elif parts[0] in ["GROUPS", "URBAN_AREAS", "AVG"]:
                        source_counts[parts[0]] = parts[1]
            print(f"Parsed source_counts: {source_counts}")
            return source_counts
        except (FileNotFoundError, IndexError) as e:
            print(f"Error reading AERMOD_def.txt: {str(e)}")
            iface.messageBar().pushMessage("Error", f"Failed to read AERMOD_def.txt: {str(e)}", level=2)
            return {}

    def read_area_def(self):
        vertex_counts = {}
        try:
            with open("AREA_def.txt", "r") as file:
                for line in file:
                    name, count = line.strip().split()
                    vertex_counts[name] = int(count)
            return vertex_counts
        except FileNotFoundError:
            print("AREA_def.txt not found.")
            return {}

    def open_file_dialog_map_output(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Receptor File (RECEPT.ROU)",
                                                   "", "All Files (*.*)")
        if file_path:
            self.chosen_file_entry_map_output.setText(os.path.basename(file_path))
            self.map_entries.append((self.chosen_file_entry_map_output, file_path))

    def open_file_dialog_sfc_output(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Surface Meteorological File",
                                                   "", "All Files (*.*)")
        if file_path:
            self.chosen_file_entry_sfc_output.setText(os.path.basename(file_path))
            self.sfc_entries.append((self.chosen_file_entry_sfc_output, file_path))

    def open_file_dialog_prof_output(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Upper Air Meteorological File",
                                                   "", "All Files (*.*)")
        if file_path:
            self.chosen_file_entry_prof_output.setText(os.path.basename(file_path))
            self.prof_entries.append((self.chosen_file_entry_prof_output, file_path))

    def setTooltip(self, widget, text):
        widget.setToolTip(text)

    def initUI(self):
        self.setWindowTitle("CAIRO © ~ AERMOD Input File Generator ©")
        self.setGeometry(100, 100, 1200, 1000)

        central_widget = QWidget()
        if central_widget is None:
            raise ValueError("central_widget is None")
        scroll = QScrollArea()
        scroll.setWidget(central_widget)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setCentralWidget(scroll)

        layout = QGridLayout()
        self.layout = QGridLayout()
        central_widget.setLayout(layout)

        icon_label = QLabel()
        if icon_label is None:
            raise ValueError("icon_label is None")
        try:
            icon_path = os.path.join(self.plugin_dir, "CAIRO.png")
            icon_pixmap = QPixmap(icon_path)
            if icon_pixmap.isNull():
                print("Icon pixmap is null")
            else:
                icon_label.setPixmap(icon_pixmap)
        except Exception as e:
            print(f"Error loading icon: {e}")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label, 0, 0)

        text_label = QLabel(
            "AERMOD Input File Generator\nCAIRO © for AERMOD, 2025.\nMSc Dominik Subotić @UNIVPM\n\n"
            "Tab for next, Shift+Tab for back, Alt+Scroll Wheel for horizontal scroll"
        )
        if text_label is None:
            raise ValueError("text_label is None")
        text_label.setFont(QFont('Arial', 8))
        text_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(text_label, 0, 2, 1, 6)

        title_label = QLabel("Title")
        title_label.setFont(QFont('Arial', 8))
        self.title_entry = QLineEdit()
        self.title_entry.setFixedWidth(100)
        self.title_entry.setFont(QFont('Arial', 8))
        layout.addWidget(title_label, 1, 0)
        layout.addWidget(self.title_entry, 1, 1)
        self.setTooltip(title_label, "Repeat title throughout analysis")

        utmcopy_label = QLabel("UTM zone")
        utmcopy_label.setFont(QFont('Arial', 8))
        utmcopy_label.setFixedWidth(100)
        self.utmcopy_entry = QLineEdit()
        self.utmcopy_entry.setFont(QFont('Arial', 8))
        self.utmcopy_entry.setFixedWidth(100)
        layout.addWidget(utmcopy_label, 1, 2)
        layout.addWidget(self.utmcopy_entry, 1, 3)
        self.setTooltip(utmcopy_label, "UTM zone for coordinate reference")

        utmzonecopy_label = QLabel("UTM letter")
        utmzonecopy_label.setFont(QFont('Arial', 8))
        utmzonecopy_label.setFixedWidth(100)
        self.utmzonecopy_combo = QComboBox()
        self.utmzonecopy_combo.addItems(["N", "S"])
        self.utmzonecopy_combo.setFont(QFont('Arial', 8))
        self.utmzonecopy_combo.setFixedWidth(100)
        layout.addWidget(utmzonecopy_label, 1, 4)
        layout.addWidget(self.utmzonecopy_combo, 1, 5)
        self.setTooltip(utmzonecopy_label, "Hemisphere (N or S) for UTM coordinates")

        pollutant_label = QLabel("Pollutant")
        pollutant_label.setFixedWidth(100)
        self.pollutant_entry = QLineEdit()
        self.pollutant_entry.setFixedWidth(100)
        layout.addWidget(pollutant_label, 2, 0)
        layout.addWidget(self.pollutant_entry, 2, 1)
        self.setTooltip(pollutant_label, "SO2, SOX, CO, NOX, NO2, TSP, PM10, PM2.5, LEAD, OTHER")

        flagpole_label = QLabel("Flagpole (m)")
        flagpole_label.setFixedWidth(100)
        self.flagpole_entry = QLineEdit("1.5")
        self.flagpole_entry.setFixedWidth(100)
        layout.addWidget(flagpole_label, 2, 2)
        layout.addWidget(self.flagpole_entry, 2, 3)
        self.setTooltip(flagpole_label, "Flagpole/Receptor Height (m)")

        base_elevation_label = QLabel("Base (m)")
        base_elevation_label.setFixedWidth(100)
        self.base_elevation_entry = QLineEdit()
        self.base_elevation_entry.setFixedWidth(100)
        layout.addWidget(base_elevation_label, 2, 4)
        layout.addWidget(self.base_elevation_entry, 2, 5)
        self.setTooltip(base_elevation_label, "Base elevation (m)")

        self.chosen_file_entry_map_output = QLineEdit()
        self.chosen_file_entry_map_output.setFixedWidth(100)
        self.chosen_file_entry_sfc_output = QLineEdit()
        self.chosen_file_entry_sfc_output.setFixedWidth(100)
        self.chosen_file_entry_prof_output = QLineEdit()
        self.chosen_file_entry_prof_output.setFixedWidth(100)

        map_button = QPushButton("Receptor File 📂")
        map_button.clicked.connect(self.open_file_dialog_map_output)
        map_button.setFixedWidth(100)
        layout.addWidget(map_button, 3, 4)
        layout.addWidget(self.chosen_file_entry_map_output, 3, 5)
        self.setTooltip(map_button, "Select Receptor file (e.g., RECEPT.ROU)")

        sfc_button = QPushButton("SFC File 📂")
        sfc_button.clicked.connect(self.open_file_dialog_sfc_output)
        sfc_button.setFixedWidth(100)
        layout.addWidget(sfc_button, 3, 0)
        layout.addWidget(self.chosen_file_entry_sfc_output, 3, 1)
        self.setTooltip(sfc_button, "Select Surface meteorological data (.sfc file)")

        prof_button = QPushButton("PFL File 📂")
        prof_button.clicked.connect(self.open_file_dialog_prof_output)
        prof_button.setFixedWidth(100)
        layout.addWidget(prof_button, 3, 2)
        layout.addWidget(self.chosen_file_entry_prof_output, 3, 3)
        self.setTooltip(prof_button, "Select Upper-Air meteorological data (.pfl file)")

        self.add_additional_fields(layout)

        compile_button = QPushButton("Compile 📝")
        compile_button.setFixedWidth(100)
        compile_button.setFixedHeight(60)
        compile_button.clicked.connect(self.compile_output)
        compile_button.setFont(QFont('Serif', 10))
        layout.addWidget(compile_button, 0, 1, 1, 1)
        self.setTooltip(compile_button, "Generate AERMOD Input File;\n"
                                        "Choose folder where aermod.inp will be created")

    def add_additional_fields(self, layout):
        station_num_label = QLabel("Station N° (.sfc)")
        station_num_label.setFixedWidth(100)
        self.station_num_entry = QLineEdit()
        self.station_num_entry.setFixedWidth(100)
        layout.addWidget(station_num_label, 4, 0)
        layout.addWidget(self.station_num_entry, 4, 1)

        upper_air_station_num_label = QLabel("Station N° (.pfl)")
        upper_air_station_num_label.setFixedWidth(100)
        self.upper_air_station_num_entry = QLineEdit()
        self.upper_air_station_num_entry.setFixedWidth(100)
        layout.addWidget(upper_air_station_num_label, 4, 2)
        layout.addWidget(self.upper_air_station_num_entry, 4, 3)

        start_year_label = QLabel("Start Year (.sfc)")
        start_year_label.setFixedWidth(100)
        self.start_year_entry = QLineEdit()
        self.start_year_entry.setFixedWidth(100)
        layout.addWidget(start_year_label, 5, 0)
        layout.addWidget(self.start_year_entry, 5, 1)
        self.setTooltip(start_year_label, "Starting year of the Surface Meteorological data")

        start_year_upper_air_label = QLabel("Start Year (.pfl)")
        start_year_upper_air_label.setFixedWidth(100)
        self.start_year_upper_air_entry = QLineEdit()
        self.start_year_upper_air_entry.setFixedWidth(100)
        layout.addWidget(start_year_upper_air_label, 5, 2)
        layout.addWidget(self.start_year_upper_air_entry, 5, 3)
        self.setTooltip(start_year_upper_air_label, "Starting year of the Upper Air Meteorological data")

        start_date_label = QLabel("Start Date")
        start_date_label.setFixedWidth(100)
        self.start_date_entry = QLineEdit()
        self.start_date_entry.setFixedWidth(100)
        layout.addWidget(start_date_label, 6, 0)
        layout.addWidget(self.start_date_entry, 6, 1)
        self.setTooltip(start_date_label, "Starting date of analysis (YYYY MM DD)")

        end_date_label = QLabel("End Date")
        end_date_label.setFixedWidth(100)
        self.end_date_entry = QLineEdit()
        self.end_date_entry.setFixedWidth(100)
        layout.addWidget(end_date_label, 6, 2)
        layout.addWidget(self.end_date_entry, 6, 3)
        self.setTooltip(end_date_label, "End date of analysis (YYYY MM DD)")

        rec_table_label = QLabel("Rec Table N°")
        rec_table_label.setFixedWidth(100)
        self.rec_table_entry = QLineEdit()
        self.rec_table_entry.setFixedWidth(100)
        layout.addWidget(rec_table_label, 7, 0)
        layout.addWidget(self.rec_table_entry, 7, 1)
        self.setTooltip(rec_table_label, "Option to specify value(s) by receptor for output (1ST, 2ND, 3RD...)")

        max_table_label = QLabel("Max Table N°")
        max_table_label.setFixedWidth(100)
        self.max_table_entry = QLineEdit()
        self.max_table_entry.setFixedWidth(100)
        layout.addWidget(max_table_label, 7, 2)
        layout.addWidget(self.max_table_entry, 7, 3)
        self.setTooltip(max_table_label, "Number of summarized overall maximum values (10, 20, 50)")

        num_urban_areas = int(self.source_counts.get("URBAN_AREAS", "0"))
        self.urban_areas_entries = []
        if num_urban_areas > 0:
            for i in range(num_urban_areas):
                col_offset = i * 6

                urban_area_label = QLabel(f"Urban Area {i + 1}")
                urban_area_label.setFont(QFont('Arial', 8))
                urban_area_label.setFixedWidth(100)
                urban_area_entry = QLineEdit(f"City{i + 1}")
                urban_area_entry.setFixedWidth(100)
                layout.addWidget(urban_area_label, 8, col_offset)
                layout.addWidget(urban_area_entry, 8, col_offset + 1)
                self.setTooltip(urban_area_label, f"Name of urban area {i + 1} (e.g., City1, up to 8 characters)")

                population_label = QLabel(f"Population {i + 1}")
                population_label.setFont(QFont('Arial', 8))
                population_label.setFixedWidth(100)
                population_entry = QLineEdit()
                population_entry.setFixedWidth(100)
                layout.addWidget(population_label, 8, col_offset + 2)
                layout.addWidget(population_entry, 8, col_offset + 3)
                self.setTooltip(population_label, f"Population of urban area {i + 1} (e.g., 100000)")

                urban_rough_label = QLabel(f"Roughness (m) {i + 1}")
                urban_rough_label.setFont(QFont('Arial', 8))
                urban_rough_label.setFixedWidth(100)
                urban_rough_entry = QLineEdit(f"1")
                urban_rough_entry.setFixedWidth(100)
                layout.addWidget(urban_rough_label, 8, col_offset + 4)
                layout.addWidget(urban_rough_entry, 8, col_offset + 5)
                self.setTooltip(urban_rough_label, f"Urban surface roughness length.{i + 1}")

                self.urban_areas_entries.append((urban_area_entry, population_entry, urban_rough_entry))

        normal_group_count = int(self.source_counts.get("GROUPS", "0"))
        self.normal_group_entries = []

        if normal_group_count > 0:
            for i in range(normal_group_count):
                col_offset = i * 4

                gname_label = QLabel("Group Name")
                gname_label.setFont(QFont('Arial', 8))
                gname_label.setFixedWidth(75)
                gname_label.setAlignment(Qt.AlignLeft)
                gname_entry = QLineEdit(f"GROUP{i + 1}")
                gname_entry.setFixedWidth(100)
                layout.addWidget(gname_label, 9, col_offset)
                layout.addWidget(gname_entry, 9, col_offset + 1)
                self.setTooltip(gname_label, "Group Name")

                sources_label = QLabel("Sources")
                sources_label.setFont(QFont('Arial', 8))
                sources_label.setFixedWidth(75)
                sources_label.setAlignment(Qt.AlignLeft)
                sources_entry = QLineEdit()
                sources_entry.setFixedWidth(100)
                layout.addWidget(sources_label, 9, col_offset + 2)
                layout.addWidget(sources_entry, 9, col_offset + 3)
                self.setTooltip(sources_label,
                                "Names of sources in this group, space-separated\n"
                                "(e.g., POINT1 VOL1 LINE1;\n keyword ALL to include all sources,\n"
                                "ALLRURAL to include all regular sources and \nALLURBAN to include all urban sources)")

                self.normal_group_entries.append((gname_entry, sources_entry))

        num_periods = int(self.source_counts.get("AVG", "0"))
        self.avg_period_widgets = []
        for i in range(num_periods):
            col_offset = i * 2

            time_label = QLabel(f"Avg. Period {i + 1} (h)")
            time_label.setFont(QFont('Arial', 8))
            time_label.setFixedWidth(100)
            time_entry = QLineEdit()
            time_entry.setFixedWidth(100)
            layout.addWidget(time_label, 10, col_offset)
            layout.addWidget(time_entry, 10, col_offset + 1)
            self.setTooltip(time_label, f"Defines the {i + 1}. averaging period, 1, 24, MONTH, ANNUAL, PERIOD...")

            rank_label = QLabel(f"Rank {i + 1}")
            rank_label.setFont(QFont('Arial', 8))
            rank_label.setFixedWidth(100)
            rank_entry = QLineEdit()
            rank_entry.setFixedWidth(100)
            layout.addWidget(rank_label, 11, col_offset)
            layout.addWidget(rank_entry, 11, col_offset + 1)
            self.setTooltip(rank_label, f"Output for {i + 1}. averaging period; \nOutput values by rank "
                                        "for use in Q-Q (quantile) plots;"
                                        "\nNumber of high-ranked values (e.g., top 5, 10)")

            max_label = QLabel(f"Threshold {i + 1}")
            max_label.setFont(QFont('Arial', 8))
            max_label.setFixedWidth(100)
            max_entry = QLineEdit()
            max_entry.setFixedWidth(100)
            layout.addWidget(max_label, 12, col_offset)
            layout.addWidget(max_entry, 12, col_offset + 1)
            self.setTooltip(max_label, f"Output for {i + 1}. averaging period; \nViolations recorded in maxitable")

            plot_label = QLabel(f"Plot Rank {i + 1}")
            plot_label.setFont(QFont('Arial', 8))
            plot_label.setFixedWidth(100)
            plot_entry = QLineEdit()
            plot_entry.setFixedWidth(100)
            layout.addWidget(plot_label, 13, col_offset)
            layout.addWidget(plot_entry, 13, col_offset + 1)
            self.setTooltip(plot_label, f"Rank for PLOTFILE output for period {i + 1}.\n"
                                        f"(e.g., FIRST, SECOND, THIRD or 1ST, 2ND, 3RD...)\n"
                                        f"Isn't applicable for YEAR or PERIOD avg.period")

            self.avg_period_widgets.append({
                "time_entry": time_entry,
                "rank_entry": rank_entry,
                "max_entry": max_entry,
                "plot_entry": plot_entry
            })

        point_normal_count = int(self.source_counts.get("POINT", ("0", "0"))[0])
        point_urban_count = int(self.source_counts.get("POINT", ("0", "0"))[1])

        base_row = 14
        if point_normal_count > 0:
            for i in range(point_normal_count):
                col_offset = i * 4
                name_entry = QLineEdit(f"POINT{i + 1}")
                name_entry.setFixedWidth(75)
                lat_entry = QLineEdit()
                lat_entry.setFixedWidth(75)
                lon_entry = QLineEdit()
                lon_entry.setFixedWidth(75)
                base_entry = QLineEdit("0")
                base_entry.setFixedWidth(50)
                rate_entry = QLineEdit()
                rate_entry.setFixedWidth(50)
                height_entry = QLineEdit()
                height_entry.setFixedWidth(50)
                temp_entry = QLineEdit()
                temp_entry.setFixedWidth(50)
                vel_entry = QLineEdit()
                vel_entry.setFixedWidth(50)
                diam_entry = QLineEdit()
                diam_entry.setFixedWidth(50)

                viz_button = QPushButton("Visualize")
                viz_button.setFixedWidth(50)
                viz_button.clicked.connect(lambda checked, idx=i: self.visualize_normal_point_source(idx))
                layout.addWidget(viz_button, base_row, col_offset)
                self.setTooltip(viz_button, f"Visualize point source {i + 1} on QGIS map")

                map_button = QPushButton("Map  ✜")
                map_button.setFixedWidth(50)
                map_button.clicked.connect(lambda checked, idx=i: self.capture_normal_point_source(idx))
                layout.addWidget(map_button, base_row, col_offset + 1)
                self.setTooltip(map_button,
                                f"Select point source {i + 1} coordinates on QGIS map")

                name_label = QLabel("Name")
                name_label.setFont(QFont('Arial', 8))
                name_label.setAlignment(Qt.AlignCenter)
                name_label.setFixedWidth(50)
                layout.addWidget(name_label, base_row, col_offset + 2)
                layout.addWidget(name_entry, base_row, col_offset + 3)
                self.setTooltip(name_label, "Source name; Srcid")

                lon_label = QLabel("E")
                lon_label.setFont(QFont('Arial', 8))
                lon_label.setAlignment(Qt.AlignCenter)
                lon_label.setFixedWidth(50)
                layout.addWidget(lon_label, base_row + 1, col_offset)
                layout.addWidget(lon_entry, base_row + 1, col_offset + 1)
                self.setTooltip(lon_label, "Easting coordinate; Xs")

                lat_label = QLabel("N")
                lat_label.setFont(QFont('Arial', 8))
                lat_label.setAlignment(Qt.AlignCenter)
                lat_label.setFixedWidth(50)
                layout.addWidget(lat_label, base_row + 1, col_offset + 2)
                layout.addWidget(lat_entry, base_row + 1, col_offset + 3)
                self.setTooltip(lat_label, "Northing coordinate; Ys")

                base_label = QLabel("Base (m)")
                base_label.setFont(QFont('Arial', 8))
                base_label.setFixedWidth(50)
                base_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(base_label, base_row + 2, col_offset)
                layout.addWidget(base_entry, base_row + 2, col_offset + 1)
                self.setTooltip(base_label, "Base elevation; Zs")

                rate_label = QLabel("Load (g/s)")
                rate_label.setFont(QFont('Arial', 8))
                rate_label.setFixedWidth(50)
                rate_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(rate_label, base_row + 2, col_offset + 2)
                layout.addWidget(rate_entry, base_row + 2, col_offset + 3)
                self.setTooltip(rate_label, "Emission rate; Ptemis")

                height_label = QLabel("Height")
                height_label.setFont(QFont('Arial', 8))
                height_label.setFixedWidth(50)
                height_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(height_label, base_row + 3, col_offset)
                layout.addWidget(height_entry, base_row + 3, col_offset + 1)
                self.setTooltip(height_label, "Stack height; Stkhgt")

                temp_label = QLabel("Temp (K)")
                temp_label.setFont(QFont('Arial', 8))
                temp_label.setFixedWidth(50)
                temp_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(temp_label, base_row + 3, col_offset + 2)
                layout.addWidget(temp_entry, base_row + 3, col_offset + 3)
                self.setTooltip(temp_label, "Exit temperature; Stktmp")

                vel_label = QLabel("Vel (m/s)")
                vel_label.setFont(QFont('Arial', 8))
                vel_label.setFixedWidth(50)
                vel_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(vel_label, base_row + 4, col_offset)
                layout.addWidget(vel_entry, base_row + 4, col_offset + 1)
                self.setTooltip(vel_label, "Exit velocity; Stkvel")

                diam_label = QLabel("Diam (m)")
                diam_label.setFont(QFont('Arial', 8))
                diam_label.setFixedWidth(50)
                diam_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(diam_label, base_row + 4, col_offset + 2)
                layout.addWidget(diam_entry, base_row + 4, col_offset + 3)
                self.setTooltip(diam_label, "Stack diameter; Stkdia")

                if i < point_normal_count - 1:
                    separator = QFrame()
                    separator.setFrameShape(QFrame.VLine)
                    separator.setFrameShadow(QFrame.Sunken)
                    separator.setLineWidth(1)
                    total_rows = 5
                    layout.addWidget(separator, base_row, col_offset + 4, total_rows, 1, alignment=Qt.AlignLeft)

                h_separator = QFrame()
                h_separator.setFrameShape(QFrame.HLine)
                h_separator.setFrameShadow(QFrame.Sunken)
                h_separator.setLineWidth(1)
                layout.addWidget(h_separator, base_row + 5, 0, 1, point_normal_count * 4,
                                 alignment=Qt.AlignTop)

                self.normal_pointsource_entries.append(
                    (name_entry, lon_entry, lat_entry, base_entry, rate_entry, height_entry, temp_entry, vel_entry,
                     diam_entry)
                )

        if point_normal_count > 0:
            ubase_row = 19
        else:
            ubase_row = 14
        if point_urban_count > 0:
            for i in range(point_urban_count):
                ucol_offset = i * 4
                name_entry = QLineEdit(f"UPOINT{i + 1}")
                name_entry.setFixedWidth(75)
                area_entry = QLineEdit("City1")
                area_entry.setFixedWidth(75)
                lat_entry = QLineEdit()
                lat_entry.setFixedWidth(75)
                lon_entry = QLineEdit()
                lon_entry.setFixedWidth(75)
                base_entry = QLineEdit("0")
                base_entry.setFixedWidth(50)
                rate_entry = QLineEdit()
                rate_entry.setFixedWidth(50)
                height_entry = QLineEdit()
                height_entry.setFixedWidth(50)
                temp_entry = QLineEdit()
                temp_entry.setFixedWidth(50)
                vel_entry = QLineEdit()
                vel_entry.setFixedWidth(50)
                diam_entry = QLineEdit()
                diam_entry.setFixedWidth(50)

                viz_button = QPushButton("Visualize")
                viz_button.setFixedWidth(50)
                viz_button.clicked.connect(lambda checked, idx=i: self.visualize_urban_point_source(idx))
                layout.addWidget(viz_button, ubase_row, ucol_offset + 1)
                self.setTooltip(viz_button, f"Visualize urban point source {i + 1} on QGIS map")

                map_button = QPushButton("Map ✜")
                map_button.setFixedWidth(50)
                map_button.clicked.connect(lambda checked, idx=i: self.capture_urban_point_source(idx))
                layout.addWidget(map_button, ubase_row, ucol_offset + 2)
                self.setTooltip(map_button,
                                f"Select urban point source {i + 1} coordinates on QGIS map")

                name_label = QLabel("Name")
                name_label.setFont(QFont('Arial', 8))
                name_label.setAlignment(Qt.AlignCenter)
                name_label.setFixedWidth(50)
                layout.addWidget(name_label, ubase_row + 1, ucol_offset)
                layout.addWidget(name_entry, ubase_row + 1, ucol_offset + 1)
                self.setTooltip(name_label, "Urban source name; Srcid")

                area_label = QLabel("Urb Area")
                area_label.setFont(QFont('Arial', 8))
                area_label.setAlignment(Qt.AlignCenter)
                area_label.setFixedWidth(50)
                layout.addWidget(area_label, ubase_row + 1, ucol_offset + 2)
                layout.addWidget(area_entry, ubase_row + 1, ucol_offset + 3)
                self.setTooltip(area_label, "Urban area name\n"
                                            "Add name of urban area to add to specify area affiliation")

                lon_label = QLabel("E")
                lon_label.setFont(QFont('Arial', 8))
                lon_label.setAlignment(Qt.AlignCenter)
                lon_label.setFixedWidth(50)
                layout.addWidget(lon_label, ubase_row + 2, ucol_offset)
                layout.addWidget(lon_entry, ubase_row + 2, ucol_offset + 1)
                self.setTooltip(lon_label, "Easting coordinate; Xs")

                lat_label = QLabel("N")
                lat_label.setFont(QFont('Arial', 8))
                lat_label.setAlignment(Qt.AlignCenter)
                lat_label.setFixedWidth(50)
                layout.addWidget(lat_label, ubase_row + 2, ucol_offset + 2)
                layout.addWidget(lat_entry, ubase_row + 2, ucol_offset + 3)
                self.setTooltip(lat_label, "Northing coordinate; Ys")

                base_label = QLabel("Base (m)")
                base_label.setFont(QFont('Arial', 8))
                base_label.setFixedWidth(50)
                base_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(base_label, ubase_row + 3, ucol_offset)
                layout.addWidget(base_entry, ubase_row + 3, ucol_offset + 1)
                self.setTooltip(base_label, "Base elevation; Zs")

                rate_label = QLabel("Load (g/s)")
                rate_label.setFont(QFont('Arial', 8))
                rate_label.setFixedWidth(50)
                rate_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(rate_label, ubase_row + 3, ucol_offset + 2)
                layout.addWidget(rate_entry, ubase_row + 3, ucol_offset + 3)
                self.setTooltip(rate_label, "Emission rate; Ptemis")

                height_label = QLabel("Height (m)")
                height_label.setFont(QFont('Arial', 8))
                height_label.setFixedWidth(50)
                height_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(height_label, ubase_row + 4, ucol_offset)
                layout.addWidget(height_entry, ubase_row + 4, ucol_offset + 1)
                self.setTooltip(height_label, "Stack height; Stkhgt")

                temp_label = QLabel("Temp (K)")
                temp_label.setFont(QFont('Arial', 8))
                temp_label.setFixedWidth(50)
                temp_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(temp_label, ubase_row + 4, ucol_offset + 2)
                layout.addWidget(temp_entry, ubase_row + 4, ucol_offset + 3)
                self.setTooltip(temp_label, "Exit temperature; Stktmp")

                vel_label = QLabel("Vel (m/s)")
                vel_label.setFont(QFont('Arial', 8))
                vel_label.setFixedWidth(50)
                vel_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(vel_label, ubase_row + 5, ucol_offset)
                layout.addWidget(vel_entry, ubase_row + 5, ucol_offset + 1)
                self.setTooltip(vel_label, "Exit velocity; Stkvel")

                diam_label = QLabel("Diam (m)")
                diam_label.setFont(QFont('Arial', 8))
                diam_label.setFixedWidth(50)
                diam_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(diam_label, ubase_row + 5, ucol_offset + 2)
                layout.addWidget(diam_entry, ubase_row + 5, ucol_offset + 3)
                self.setTooltip(diam_label, "Stack diameter; Stkdia")

                if i < point_urban_count - 1:
                    separator = QFrame()
                    separator.setFrameShape(QFrame.VLine)
                    separator.setFrameShadow(QFrame.Sunken)
                    separator.setLineWidth(1)
                    total_rows = 6
                    layout.addWidget(separator, ubase_row, ucol_offset + 4, total_rows, 1, alignment=Qt.AlignLeft)

                h_separator = QFrame()
                h_separator.setFrameShape(QFrame.HLine)
                h_separator.setFrameShadow(QFrame.Sunken)
                h_separator.setLineWidth(1)
                layout.addWidget(h_separator, ubase_row + 6, 0, 1, point_urban_count * 4,
                                 alignment=Qt.AlignTop)

                self.urban_pointsource_entries.append(
                    (name_entry, area_entry, lon_entry, lat_entry, base_entry, rate_entry, height_entry, temp_entry,
                     vel_entry, diam_entry)
                )

        normal_line_count = int(self.source_counts.get("LINE", ("0", "0"))[0])
        urban_line_count = int(self.source_counts.get("LINE", ("0", "0"))[1])
        self.normal_line_source_entries = []
        self.urban_line_source_entries = []

        if normal_line_count > 0:

            for i in range(normal_line_count):
                col_offset = i * 4
                if point_normal_count and point_urban_count > 0:
                    lbase_row = 25
                elif point_normal_count > 0 and point_urban_count == 0:
                    lbase_row = 20
                elif point_normal_count == 0 and point_urban_count > 0:
                    lbase_row = 21
                else:
                    lbase_row = 14

                viz_button = QPushButton("Visualize")
                viz_button.setFixedWidth(50)
                viz_button.clicked.connect(lambda checked, idx=i: self.visualize_normal_line_source(idx))
                layout.addWidget(viz_button, lbase_row, col_offset)
                self.setTooltip(viz_button, f"Visualize line source {i + 1} from coordinates")

                map_button = QPushButton("Map ✜")
                map_button.setFixedWidth(50)
                map_button.clicked.connect(lambda checked, idx=i: self.capture_normal_line_source(idx))
                layout.addWidget(map_button, lbase_row, col_offset + 1)
                self.setTooltip(map_button, f"Draw line source {i + 1} on QGIS map (select start and end point)")

                name_label = QLabel("Name")
                name_label.setFont(QFont('Arial', 8))
                name_label.setFixedWidth(50)
                name_label.setAlignment(Qt.AlignCenter)
                name_entry = QLineEdit(f"LINE{i + 1}")
                name_entry.setFixedWidth(75)
                layout.addWidget(name_label, lbase_row, col_offset + 2)
                layout.addWidget(name_entry, lbase_row, col_offset + 3)
                self.setTooltip(name_label, "Line source name; Srcid")

                easting_start_label = QLabel("E Start")
                easting_start_label.setFont(QFont('Arial', 8))
                easting_start_label.setFixedWidth(50)
                easting_start_label.setAlignment(Qt.AlignCenter)
                easting_start_entry = QLineEdit()
                easting_start_entry.setFixedWidth(75)
                layout.addWidget(easting_start_label, lbase_row + 1, col_offset)
                layout.addWidget(easting_start_entry, lbase_row + 1, col_offset + 1)
                self.setTooltip(easting_start_label, "Starting point UTM easting coordinate, "
                                                     "up to 4 decimal places; Xs1")

                northing_start_label = QLabel("N Start")
                northing_start_label.setFont(QFont('Arial', 8))
                northing_start_label.setFixedWidth(50)
                northing_start_label.setAlignment(Qt.AlignCenter)
                northing_start_entry = QLineEdit()
                northing_start_entry.setFixedWidth(75)
                layout.addWidget(northing_start_label, lbase_row + 1, col_offset + 2)
                layout.addWidget(northing_start_entry, lbase_row + 1, col_offset + 3)
                self.setTooltip(northing_start_label, "Starting point UTM northing coordinate, "
                                                      "up to 4 decimal places; Ys1")

                easting_end_label = QLabel("E End")
                easting_end_label.setFont(QFont('Arial', 8))
                easting_end_label.setFixedWidth(50)
                easting_end_label.setAlignment(Qt.AlignCenter)
                easting_end_entry = QLineEdit()
                easting_end_entry.setFixedWidth(75)
                layout.addWidget(easting_end_label, lbase_row + 2, col_offset)
                layout.addWidget(easting_end_entry, lbase_row + 2, col_offset + 1)
                self.setTooltip(easting_end_label, "Ending point UTM easting coordinate, "
                                                   "up to 4 decimal places; Xs2")

                northing_end_label = QLabel("N End")
                northing_end_label.setFont(QFont('Arial', 8))
                northing_end_label.setFixedWidth(50)
                northing_end_label.setAlignment(Qt.AlignCenter)
                northing_end_entry = QLineEdit()
                northing_end_entry.setFixedWidth(75)
                layout.addWidget(northing_end_label, lbase_row + 2, col_offset + 2)
                layout.addWidget(northing_end_entry, lbase_row + 2, col_offset + 3)
                self.setTooltip(northing_end_label, "Ending point UTM northing coordinate, "
                                                    "up to 4 decimal places; Ys2")

                lnemis_label = QLabel("Load (g/s-m²)")
                lnemis_label.setFont(QFont('Arial', 8))
                lnemis_label.setFixedWidth(70)
                lnemis_label.setAlignment(Qt.AlignCenter)
                lnemis_entry = QLineEdit()
                lnemis_entry.setFixedWidth(50)
                layout.addWidget(lnemis_label, lbase_row + 3, col_offset)
                layout.addWidget(lnemis_entry, lbase_row + 3, col_offset + 1)
                self.setTooltip(lnemis_label, "Line source emission rate (g/(s-m²)); Lnemis")

                relhgt_label = QLabel("Release (m)")
                relhgt_label.setFont(QFont('Arial', 8))
                relhgt_label.setFixedWidth(75)
                relhgt_label.setAlignment(Qt.AlignCenter)
                relhgt_entry = QLineEdit()
                relhgt_entry.setFixedWidth(50)
                layout.addWidget(relhgt_label, lbase_row + 3, col_offset + 2)
                layout.addWidget(relhgt_entry, lbase_row + 3, col_offset + 3)
                self.setTooltip(relhgt_label, "Average release height above ground (m); Relhgt")

                width_label = QLabel("Width (m)")
                width_label.setFont(QFont('Arial', 8))
                width_label.setFixedWidth(50)
                width_label.setAlignment(Qt.AlignCenter)
                width_entry = QLineEdit()
                width_entry.setFixedWidth(50)
                layout.addWidget(width_label, lbase_row + 4, col_offset)
                layout.addWidget(width_entry, lbase_row + 4, col_offset + 1)
                self.setTooltip(width_label, "Width of the source (m, minimum 1m); Width")

                szinit_label = QLabel("Initial (m)")
                szinit_label.setFont(QFont('Arial', 8))
                szinit_label.setFixedWidth(50)
                szinit_label.setAlignment(Qt.AlignCenter)
                szinit_entry = QLineEdit()
                szinit_entry.setFixedWidth(50)
                layout.addWidget(szinit_label, lbase_row + 4, col_offset + 2)
                layout.addWidget(szinit_entry, lbase_row + 4, col_offset + 3)
                self.setTooltip(szinit_label, "Initial vertical dimension of the line source (m); Szinit")

                if i < normal_line_count - 1:
                    separator = QFrame()
                    separator.setFrameShape(QFrame.VLine)
                    separator.setFrameShadow(QFrame.Sunken)
                    separator.setLineWidth(1)
                    total_rows = 5
                    layout.addWidget(separator, lbase_row, col_offset + 4, total_rows, 1, alignment=Qt.AlignLeft)

                h_separator = QFrame()
                h_separator.setFrameShape(QFrame.HLine)
                h_separator.setFrameShadow(QFrame.Sunken)
                h_separator.setLineWidth(1)
                layout.addWidget(h_separator, lbase_row + 5, 0, 1, normal_line_count * 4,
                                 alignment=Qt.AlignTop)

                self.normal_line_source_entries.append(
                    (name_entry, easting_start_entry, northing_start_entry, easting_end_entry, northing_end_entry,
                     lnemis_entry, relhgt_entry, width_entry, szinit_entry)
                )

        if urban_line_count > 0:
            for i in range(urban_line_count):
                col_offset = i * 4
                if point_normal_count and point_urban_count and normal_line_count > 0:
                    ulbase_row = 31
                elif point_normal_count > 0 and point_urban_count == 0 and normal_line_count == 0:
                    ulbase_row = 20
                elif point_normal_count == 0 and point_urban_count > 0 and normal_line_count == 0:
                    ulbase_row = 21
                elif point_normal_count == 0 and point_urban_count == 0 and normal_line_count > 0:
                    ulbase_row = 20
                elif point_normal_count == 0 and point_urban_count > 0 and normal_line_count > 0:
                    ulbase_row = 26
                elif point_normal_count > 0 and point_urban_count == 0 and normal_line_count > 0:
                    ulbase_row = 25
                elif point_normal_count > 0 and point_urban_count > 0 and normal_line_count == 0:
                    ulbase_row = 26
                else:
                    ulbase_row = 14

                viz_button = QPushButton("Visualize")
                viz_button.setFixedWidth(50)
                viz_button.clicked.connect(lambda checked, idx=i: self.visualize_urban_line_source(idx))
                layout.addWidget(viz_button, ulbase_row, col_offset + 1)
                self.setTooltip(viz_button, f"Visualize urban line source {i + 1} from coordinates")

                map_button = QPushButton("Map ✜")
                map_button.setFixedWidth(50)
                map_button.clicked.connect(lambda checked, idx=i: self.capture_urban_line_source(idx))
                layout.addWidget(map_button, ulbase_row, col_offset + 2)
                self.setTooltip(map_button, f"Draw urban line source {i + 1} on QGIS map "
                                            f"(select start and end point)")

                name_label = QLabel("Name")
                name_label.setFont(QFont('Arial', 8))
                name_label.setFixedWidth(50)
                name_label.setAlignment(Qt.AlignCenter)
                name_entry = QLineEdit(f"ULINE{i + 1}")
                name_entry.setFixedWidth(75)
                layout.addWidget(name_label, ulbase_row + 1, col_offset)
                layout.addWidget(name_entry, ulbase_row + 1, col_offset + 1)
                self.setTooltip(name_label, "Urban line source name; Srcid")

                area_label = QLabel("Urb Area")
                area_label.setFont(QFont('Arial', 8))
                area_label.setFixedWidth(50)
                area_label.setAlignment(Qt.AlignCenter)
                area_entry = QLineEdit("City1")
                area_entry.setFixedWidth(75)
                layout.addWidget(area_label, ulbase_row + 1, col_offset + 2)
                layout.addWidget(area_entry, ulbase_row + 1, col_offset + 3)
                self.setTooltip(area_label, "Urban area identifier for this line source (e.g., City1)\n"
                                            "Add name of urban area to add to specify area affiliation ")

                easting_start_label = QLabel("E Start")
                easting_start_label.setFont(QFont('Arial', 8))
                easting_start_label.setFixedWidth(50)
                easting_start_label.setAlignment(Qt.AlignCenter)
                easting_start_entry = QLineEdit()
                easting_start_entry.setFixedWidth(75)
                layout.addWidget(easting_start_label, ulbase_row + 2, col_offset)
                layout.addWidget(easting_start_entry, ulbase_row + 2, col_offset + 1)
                self.setTooltip(easting_start_label, "Starting UTM easting coordinate, "
                                                     "up to 4 decimal places; Xs1")

                northing_start_label = QLabel("N Start")
                northing_start_label.setFont(QFont('Arial', 8))
                northing_start_label.setFixedWidth(50)
                northing_start_label.setAlignment(Qt.AlignCenter)
                northing_start_entry = QLineEdit()
                northing_start_entry.setFixedWidth(75)
                layout.addWidget(northing_start_label, ulbase_row + 2, col_offset + 2)
                layout.addWidget(northing_start_entry, ulbase_row + 2, col_offset + 3)
                self.setTooltip(northing_start_label,
                                "Starting UTM northing coordinate, up to 4 decimal places; Ys1")

                easting_end_label = QLabel("E End")
                easting_end_label.setFont(QFont('Arial', 8))
                easting_end_label.setFixedWidth(50)
                easting_end_label.setAlignment(Qt.AlignCenter)
                easting_end_entry = QLineEdit()
                easting_end_entry.setFixedWidth(75)
                layout.addWidget(easting_end_label, ulbase_row + 3, col_offset)
                layout.addWidget(easting_end_entry, ulbase_row + 3, col_offset + 1)
                self.setTooltip(easting_end_label, "Ending UTM easting coordinate, "
                                                   "up to 4 decimal places; Xs2")

                northing_end_label = QLabel("N End")
                northing_end_label.setFont(QFont('Arial', 8))
                northing_end_label.setFixedWidth(50)
                northing_end_label.setAlignment(Qt.AlignCenter)
                northing_end_entry = QLineEdit()
                northing_end_entry.setFixedWidth(75)
                layout.addWidget(northing_end_label, ulbase_row + 3, col_offset + 2)
                layout.addWidget(northing_end_entry, ulbase_row + 3, col_offset + 3)
                self.setTooltip(northing_end_label, "Ending UTM northing coordinate, "
                                                    "up to 4 decimal places; Ys2")

                lnemis_label = QLabel("Load (g/s-m²)")
                lnemis_label.setFont(QFont('Arial', 8))
                lnemis_label.setFixedWidth(70)
                lnemis_label.setAlignment(Qt.AlignCenter)
                lnemis_entry = QLineEdit()
                lnemis_entry.setFixedWidth(50)
                layout.addWidget(lnemis_label, ulbase_row + 4, col_offset)
                layout.addWidget(lnemis_entry, ulbase_row + 4, col_offset + 1)
                self.setTooltip(lnemis_label, "Line source emission rate (g/(s-m²)); Lnemis")

                relhgt_label = QLabel("Release (m)")
                relhgt_label.setFont(QFont('Arial', 8))
                relhgt_label.setFixedWidth(75)
                relhgt_label.setAlignment(Qt.AlignCenter)
                relhgt_entry = QLineEdit()
                relhgt_entry.setFixedWidth(50)
                layout.addWidget(relhgt_label, ulbase_row + 4, col_offset + 2)
                layout.addWidget(relhgt_entry, ulbase_row + 4, col_offset + 3)
                self.setTooltip(relhgt_label, "Average release height above ground (m); Relhgt")

                width_label = QLabel("Width (m)")
                width_label.setFont(QFont('Arial', 8))
                width_label.setFixedWidth(50)
                width_label.setAlignment(Qt.AlignCenter)
                width_entry = QLineEdit()
                width_entry.setFixedWidth(50)
                layout.addWidget(width_label, ulbase_row + 5, col_offset)
                layout.addWidget(width_entry, ulbase_row + 5, col_offset + 1)
                self.setTooltip(width_label, "Width of the source (m, minimum 1m); Width")

                szinit_label = QLabel("Initial (m)")
                szinit_label.setFont(QFont('Arial', 8))
                szinit_label.setFixedWidth(50)
                szinit_label.setAlignment(Qt.AlignCenter)
                szinit_entry = QLineEdit()
                szinit_entry.setFixedWidth(50)
                layout.addWidget(szinit_label, ulbase_row + 5, col_offset + 2)
                layout.addWidget(szinit_entry, ulbase_row + 5, col_offset + 3)
                self.setTooltip(szinit_label, "Initial vertical dimension of the line source (m); Sziniz")

                if i < urban_line_count - 1:
                    separator = QFrame()
                    separator.setFrameShape(QFrame.VLine)
                    separator.setFrameShadow(QFrame.Sunken)
                    separator.setLineWidth(1)
                    total_rows = 6
                    layout.addWidget(separator, ulbase_row, col_offset + 4, total_rows, 1, alignment=Qt.AlignLeft)

                h_separator = QFrame()
                h_separator.setFrameShape(QFrame.HLine)
                h_separator.setFrameShadow(QFrame.Sunken)
                h_separator.setLineWidth(1)
                layout.addWidget(h_separator, ulbase_row + 6, 0, 1, urban_line_count * 4,
                                 alignment=Qt.AlignTop)

                self.urban_line_source_entries.append(
                    (name_entry, area_entry, easting_start_entry, northing_start_entry, easting_end_entry, northing_end_entry,
                     lnemis_entry, relhgt_entry, width_entry, szinit_entry)
                )

        normal_area_count = int(self.source_counts.get("AREA", ("0", "0"))[0])
        urban_area_count = int(self.source_counts.get("AREA", ("0", "0"))[1])
        self.normal_area_source_entries = []
        self.urban_area_source_entries = []
        vertex_counts = self.read_area_def()

        if normal_area_count > 0:
            for i in range(normal_area_count):
                col_offset = i * 4

                def calculate_abase_row():
                    koffset = 15
                    if point_normal_count > 0:
                        koffset += 5
                    if point_urban_count > 0:
                        koffset += 6
                    if normal_line_count > 0:
                        koffset += 5
                    if urban_line_count > 0:
                        koffset += 6
                    return koffset

                abase_row = calculate_abase_row()

                name_label = QLabel("Name")
                name_label.setFont(QFont('Arial', 8))
                name_label.setFixedWidth(50)
                name_label.setAlignment(Qt.AlignCenter)
                name_entry = QLineEdit(f"POLY{i + 1}")
                name_entry.setFixedWidth(75)
                layout.addWidget(name_label, abase_row + 1, col_offset)
                layout.addWidget(name_entry, abase_row + 1, col_offset + 1)
                self.setTooltip(name_label, "Name for the area polygon source; Srcid")

                rate_label = QLabel("Load g/(s-m²)")
                rate_label.setFont(QFont('Arial', 8))
                rate_label.setFixedWidth(75)
                rate_label.setAlignment(Qt.AlignCenter)
                rate_entry = QLineEdit()
                rate_entry.setFixedWidth(60)
                layout.addWidget(rate_label, abase_row + 1, col_offset + 2)
                layout.addWidget(rate_entry, abase_row + 1, col_offset + 3)
                self.setTooltip(rate_label, "Pollutant Load/Emission Rate g/(s-m²); Aremis")

                rheight_label = QLabel("Release(m)")
                rheight_label.setFont(QFont('Arial', 8))
                rheight_label.setFixedWidth(75)
                rheight_label.setAlignment(Qt.AlignCenter)
                rheight_entry = QLineEdit()
                rheight_entry.setFixedWidth(60)
                layout.addWidget(rheight_label, abase_row + 2, col_offset)
                layout.addWidget(rheight_entry, abase_row + 2, col_offset + 1)
                self.setTooltip(rheight_label, "Release Height (m); Relhgt")

                iheight_label = QLabel("Initial(m)")
                iheight_label.setFont(QFont('Arial', 8))
                iheight_label.setFixedWidth(50)
                iheight_label.setAlignment(Qt.AlignCenter)
                iheight_entry = QLineEdit()
                iheight_entry.setFixedWidth(60)
                layout.addWidget(iheight_label, abase_row + 2, col_offset + 2)
                layout.addWidget(iheight_entry, abase_row + 2, col_offset + 3)
                self.setTooltip(iheight_label, "Initial Release Height (m); Szinit")

                normal_polygon_entry = {
                    "vertices": [],
                    "rate_entry": rate_entry,
                    "rheight_entry": rheight_entry,
                    "iheight_entry": iheight_entry,
                    "name_entry": name_entry,
                    "row": None
                }
                self.normal_area_source_entries.append(normal_polygon_entry)

                vertex_count = vertex_counts.get(f"NAREA{i + 1}", 3)
                for j in range(vertex_count):
                    easting_label = QLabel(f"E {j + 1}")
                    easting_label.setFont(QFont('Arial', 8))
                    easting_label.setAlignment(Qt.AlignCenter)
                    easting_label.setFixedWidth(50)
                    easting_entry = QLineEdit()
                    easting_entry.setFixedWidth(75)
                    northing_label = QLabel(f"N {j + 1}")
                    northing_label.setFont(QFont('Arial', 8))
                    northing_label.setAlignment(Qt.AlignCenter)
                    northing_label.setFixedWidth(50)
                    northing_entry = QLineEdit()
                    northing_entry.setFixedWidth(75)
                    vertex_row = abase_row + 3 + j
                    layout.addWidget(easting_label, vertex_row, col_offset)
                    layout.addWidget(easting_entry, vertex_row, col_offset + 1)
                    layout.addWidget(northing_label, vertex_row, col_offset + 2)
                    layout.addWidget(northing_entry, vertex_row, col_offset + 3)
                    normal_polygon_entry["vertices"].append((northing_entry, easting_entry))

                viz_button = QPushButton("Visualize")
                viz_button.setFixedWidth(60)
                viz_button.clicked.connect(
                    lambda checked, idx=i: self.visualize_normal_area_source(idx))
                layout.addWidget(viz_button, abase_row, col_offset + 1)
                self.setTooltip(viz_button, f"Visualize area polygon source {i + 1} on QGIS map")

                map_button = QPushButton("Map ✜")
                map_button.setFixedWidth(60)
                map_button.clicked.connect(
                    lambda checked, idx=i: self.capture_normal_area_source(idx))
                layout.addWidget(map_button, abase_row, col_offset + 2)
                self.setTooltip(map_button, f"Draw area polygon source {i + 1} polygon on QGIS map\n"
                                            f"Click on map to add vertices, "
                                            f"polygon appears after last vertice is added")

                if i < normal_area_count - 1:
                    separator = QFrame()
                    separator.setFrameShape(QFrame.VLine)
                    separator.setFrameShadow(QFrame.Sunken)
                    separator.setLineWidth(1)
                    total_rows = 3 + vertex_count
                    layout.addWidget(separator, abase_row, col_offset + 4, total_rows,
                                     1, alignment=Qt.AlignLeft)
                max_vertex_count = max([vertex_counts.get(f"NAREA{i + 1}", 3) for i in range(normal_area_count)])
                total_rows = 3 + max_vertex_count
                last_row = abase_row + total_rows - 1

                h_separator = QFrame()
                h_separator.setFrameShape(QFrame.HLine)
                h_separator.setFrameShadow(QFrame.Sunken)
                h_separator.setLineWidth(1)
                layout.addWidget(h_separator, last_row + 1, 0, 1, normal_area_count * 4, alignment=Qt.AlignTop)

        if urban_area_count > 0:
            for i in range(urban_area_count):
                col_offset = i * 4

                vertex_counts = self.read_area_def()
                if normal_area_count > 0:
                    nvertex_count = max([vertex_counts.get(f"NAREA{i + 1}", 3) for i in range(normal_area_count)])
                else:
                    nvertex_count = 0

                def calculate_row_offset():
                    roffset = 15
                    if point_normal_count > 0:
                        roffset += 5
                    if point_urban_count > 0:
                        roffset += 6
                    if normal_line_count > 0:
                        roffset += 5
                    if urban_line_count > 0:
                        roffset += 6
                    if normal_area_count > 0:
                        roffset += 3 + nvertex_count
                    return roffset

                row_offset = calculate_row_offset()

                name_label = QLabel("Name")
                name_label.setFont(QFont('Arial', 8))
                name_label.setFixedWidth(50)
                name_label.setAlignment(Qt.AlignCenter)
                name_entry = QLineEdit(f"UPOLY{i + 1}")
                name_entry.setFixedWidth(75)
                layout.addWidget(name_label, row_offset, col_offset + 2)
                layout.addWidget(name_entry, row_offset, col_offset + 3)
                self.setTooltip(name_label, "Name for the urban area polygon source; Srcid")

                area_label = QLabel("Urb Area")
                area_label.setFont(QFont('Arial', 8))
                area_label.setAlignment(Qt.AlignCenter)
                area_label.setFixedWidth(50)
                area_entry = QLineEdit(f"City1")
                area_entry.setFixedWidth(75)
                layout.addWidget(area_label, row_offset + 1, col_offset)
                layout.addWidget(area_entry, row_offset + 1, col_offset + 1)
                self.setTooltip(area_label, "Urban area name; add to specify urban area affiliation")

                rate_label = QLabel("Load g/(s-m²)")
                rate_label.setFont(QFont('Arial', 8))
                rate_label.setFixedWidth(75)
                rate_label.setAlignment(Qt.AlignCenter)
                rate_entry = QLineEdit()
                rate_entry.setFixedWidth(60)
                layout.addWidget(rate_label, row_offset + 1, col_offset + 2)
                layout.addWidget(rate_entry, row_offset + 1, col_offset + 3)
                self.setTooltip(rate_label, "Pollutant Load/Emission Rate (g/(s-m²)); Aremis")

                rheight_label = QLabel("Release(m)")
                rheight_label.setFont(QFont('Arial', 8))
                rheight_label.setFixedWidth(75)
                rheight_label.setAlignment(Qt.AlignCenter)
                rheight_entry = QLineEdit()
                rheight_entry.setFixedWidth(60)
                layout.addWidget(rheight_label, row_offset + 2, col_offset)
                layout.addWidget(rheight_entry, row_offset + 2, col_offset + 1)
                self.setTooltip(rheight_label, "Release Height (m); Relhgt")

                iheight_label = QLabel("Initial(m)")
                iheight_label.setFont(QFont('Arial', 8))
                iheight_label.setFixedWidth(50)
                iheight_label.setAlignment(Qt.AlignCenter)
                iheight_entry = QLineEdit()
                iheight_entry.setFixedWidth(60)
                layout.addWidget(iheight_label, row_offset + 2, col_offset + 2)
                layout.addWidget(iheight_entry, row_offset + 2, col_offset + 3)
                self.setTooltip(iheight_label, "Initial Release Height (m); Szinit")

                urban_polygon_entry = {
                    "vertices": [],
                    "rate_entry": rate_entry,
                    "rheight_entry": rheight_entry,
                    "iheight_entry": iheight_entry,
                    "name_entry": name_entry,
                    "area_entry": area_entry,
                    "row": None
                }
                self.urban_area_source_entries.append(urban_polygon_entry)

                vertex_count = vertex_counts.get(f"UAREA{i + 1}", 3)
                for j in range(vertex_count):
                    easting_label = QLabel(f"E {j + 1}")
                    easting_label.setFont(QFont('Arial', 8))
                    easting_label.setAlignment(Qt.AlignCenter)
                    easting_label.setFixedWidth(50)
                    easting_entry = QLineEdit()
                    easting_entry.setFixedWidth(75)
                    northing_label = QLabel(f"N {j + 1}")
                    northing_label.setFont(QFont('Arial', 8))
                    northing_label.setAlignment(Qt.AlignCenter)
                    northing_label.setFixedWidth(50)
                    northing_entry = QLineEdit()
                    northing_entry.setFixedWidth(75)
                    vertex_row = row_offset + 4 + j
                    layout.addWidget(easting_label, vertex_row, col_offset)
                    layout.addWidget(easting_entry, vertex_row, col_offset + 1)
                    layout.addWidget(northing_label, vertex_row, col_offset + 2)
                    layout.addWidget(northing_entry, vertex_row, col_offset + 3)
                    urban_polygon_entry["vertices"].append((northing_entry, easting_entry))

                viz_button = QPushButton("Visualize")
                viz_button.setFixedWidth(60)
                viz_button.clicked.connect(
                    lambda checked, idx=i: self.visualize_urban_area_source(idx))
                layout.addWidget(viz_button, row_offset, col_offset)
                self.setTooltip(viz_button, f"Visualize urban area polygon source {i + 1} on QGIS map")

                map_button = QPushButton("Map ✜")
                map_button.setFixedWidth(60)
                map_button.clicked.connect(
                    lambda checked, idx=i: self.capture_urban_area_source(idx))
                layout.addWidget(map_button, row_offset, col_offset + 1)
                self.setTooltip(map_button, f"Draw urban area polygon source {i + 1} on QGIS map\n"
                                            f"Click on map to add vertices, "
                                            f"polygon appears when the last vertice is added")

                if i < urban_area_count - 1:
                    separator = QFrame()
                    separator.setFrameShape(QFrame.VLine)
                    separator.setFrameShadow(QFrame.Sunken)
                    separator.setLineWidth(1)

                    total_rows = 4 + vertex_count
                    layout.addWidget(separator, row_offset, col_offset + 4, total_rows,
                                     1, alignment=Qt.AlignLeft)
                max_vertex_count = max([vertex_counts.get(f"UAREA{i + 1}", 3) for i in range(urban_area_count)])
                total_rows = 3 + max_vertex_count
                last_row = row_offset + total_rows

                h_separator = QFrame()
                h_separator.setFrameShape(QFrame.HLine)
                h_separator.setFrameShadow(QFrame.Sunken)
                h_separator.setLineWidth(1)
                layout.addWidget(h_separator, last_row + 1, 0, 1, urban_area_count * 4, alignment=Qt.AlignTop)

        normal_volume_count = int(self.source_counts.get("VOLUME", ("0", "0"))[0])
        urban_volume_count = int(self.source_counts.get("VOLUME", ("0", "0"))[1])
        self.normal_volume_source_entries = []
        self.urban_volume_source_entries = []

        if normal_volume_count > 0:
            for i in range(normal_volume_count):
                col_offset = i * 4

                try:
                    vertex_counts = self.read_area_def()
                    if vertex_counts is None or not isinstance(vertex_counts, dict):
                        raise ValueError("self.read_area_def() returned an invalid result")
                    if normal_area_count > 0:
                        nvertex_count = max([vertex_counts.get(f"NAREA{i + 1}", 3) for i in range(normal_area_count)])
                    else:
                        nvertex_count = 0
                except (FileNotFoundError, ValueError, AttributeError, TypeError) as e:
                    nvertex_count = 0

                try:
                    vertex_counts = self.read_area_def()
                    if vertex_counts is None or not isinstance(vertex_counts, dict):
                        raise ValueError("self.read_area_def() returned an invalid result")
                    if urban_area_count > 0:
                        uvertex_count = max([vertex_counts.get(f"UAREA{i + 1}", 3) for i in range(urban_area_count)])
                    else:
                        uvertex_count = 0
                except (FileNotFoundError, ValueError, AttributeError, TypeError) as e:
                    uvertex_count = 0

                def calculate_n_row_offset():
                    noffset = 15
                    if point_normal_count > 0:
                        noffset += 5
                    if point_urban_count > 0:
                        noffset += 6
                    if normal_line_count > 0:
                        noffset += 5
                    if urban_line_count > 0:
                        noffset += 6
                    if normal_area_count > 0:
                        noffset += 3 + nvertex_count
                    if urban_area_count > 0:
                        noffset += 4 + uvertex_count
                    return noffset

                n_row_offset = calculate_n_row_offset()

                viz_button = QPushButton("Visualize")
                viz_button.setFixedWidth(50)
                viz_button.clicked.connect(lambda checked, idx=i: self.visualize_normal_volume_source(idx))
                layout.addWidget(viz_button, n_row_offset, col_offset)
                self.setTooltip(viz_button, f"Visualize volume source {i + 1} on QGIS map")

                map_button = QPushButton("Map ✜")
                map_button.setFixedWidth(50)
                map_button.clicked.connect(lambda checked, idx=i: self.capture_normal_volume_source(idx))
                layout.addWidget(map_button, n_row_offset, col_offset + 1)
                self.setTooltip(map_button, f"Select volume source {i + 1} center on QGIS map")

                name_label = QLabel("Name")
                name_label.setFont(QFont('Arial', 8))
                name_label.setFixedWidth(50)
                name_label.setAlignment(Qt.AlignCenter)
                name_entry = QLineEdit(f"VOLUME{i + 1}")
                name_entry.setFixedWidth(75)
                layout.addWidget(name_label, n_row_offset, col_offset + 2)
                layout.addWidget(name_entry, n_row_offset, col_offset + 3)
                self.setTooltip(name_label, "Volume source name; Srcid")

                lon_label = QLabel("Easting")
                lon_label.setFont(QFont('Arial', 8))
                lon_label.setFixedWidth(50)
                lon_label.setAlignment(Qt.AlignCenter)
                lon_entry = QLineEdit()
                lon_entry.setFixedWidth(75)
                layout.addWidget(lon_label, n_row_offset + 1, col_offset)
                layout.addWidget(lon_entry, n_row_offset + 1, col_offset + 1)
                self.setTooltip(lon_label, "UTM easting coordinate, up to 4 decimal places; Xs")

                lat_label = QLabel("Northing")
                lat_label.setFont(QFont('Arial', 8))
                lat_label.setFixedWidth(50)
                lat_label.setAlignment(Qt.AlignCenter)
                lat_entry = QLineEdit()
                lat_entry.setFixedWidth(75)
                layout.addWidget(lat_label, n_row_offset + 1, col_offset + 2)
                layout.addWidget(lat_entry, n_row_offset + 1, col_offset + 3)
                self.setTooltip(lat_label, "UTM northing coordinate, up to 4 decimal places; Ys")

                vlemis_label = QLabel("Load (g/s)")
                vlemis_label.setFont(QFont('Arial', 8))
                vlemis_label.setFixedWidth(50)
                vlemis_label.setAlignment(Qt.AlignCenter)
                vlemis_entry = QLineEdit()
                vlemis_entry.setFixedWidth(50)
                layout.addWidget(vlemis_label, n_row_offset + 2, col_offset)
                layout.addWidget(vlemis_entry, n_row_offset + 2, col_offset + 1)
                self.setTooltip(vlemis_label, "Volume emission rate (g/s); Vlemis")

                relhgt_label = QLabel("Release (m)")
                relhgt_label.setFont(QFont('Arial', 8))
                relhgt_label.setFixedWidth(75)
                relhgt_label.setAlignment(Qt.AlignCenter)
                relhgt_entry = QLineEdit()
                relhgt_entry.setFixedWidth(50)
                layout.addWidget(relhgt_label, n_row_offset + 2, col_offset + 2)
                layout.addWidget(relhgt_entry, n_row_offset + 2, col_offset + 3)
                self.setTooltip(relhgt_label, "Release height (center of volume) above ground (m); Relhgt")

                syinit_label = QLabel("Y Initial (m)")
                syinit_label.setFont(QFont('Arial', 8))
                syinit_label.setFixedWidth(75)
                syinit_label.setAlignment(Qt.AlignCenter)
                syinit_entry = QLineEdit()
                syinit_entry.setFixedWidth(50)
                layout.addWidget(syinit_label, n_row_offset + 3, col_offset)
                layout.addWidget(syinit_entry, n_row_offset + 3, col_offset + 1)
                self.setTooltip(syinit_label, "Initial lateral dimension of the volume (m); Syinit\n"
                                              "Single Volume Source = length of side divided by 4.3\n"
                                              "Line Source Represented by Adjacent Volume Sources "
                                              "= length of side divided by 2.15\n"
                                              "Line Source Represented by Separated Volume Sources "
                                              "= center to center distance divided by 2.15")

                szinit_label = QLabel("Z Inital (m)")
                szinit_label.setFont(QFont('Arial', 8))
                szinit_label.setFixedWidth(50)
                szinit_label.setAlignment(Qt.AlignCenter)
                szinit_entry = QLineEdit()
                szinit_entry.setFixedWidth(50)
                layout.addWidget(szinit_label, n_row_offset + 3, col_offset + 2)
                layout.addWidget(szinit_entry, n_row_offset + 3, col_offset + 3)
                self.setTooltip(szinit_label, "Initial vertical dimension of the volume (m); Sziniz\n"
                                              "Surface-Based Source (he ~ 0) "
                                              "= vertical dimension of source divided by 2.15\n"
                                              "Elevated Source (he > 0) on or Adjacent to a Building "
                                              "= building height divided by 2.15\n"
                                              "Elevated Source (he > 0) not on or Adjacent to a Building "
                                              "= vertical dimension of source divided by 4.3")

                if i < normal_volume_count - 1:
                    separator = QFrame()
                    separator.setFrameShape(QFrame.VLine)
                    separator.setFrameShadow(QFrame.Sunken)
                    separator.setLineWidth(1)
                    total_rows = 4
                    layout.addWidget(separator, n_row_offset, col_offset + 4, total_rows, 1, alignment=Qt.AlignLeft)

                h_separator = QFrame()
                h_separator.setFrameShape(QFrame.HLine)
                h_separator.setFrameShadow(QFrame.Sunken)
                h_separator.setLineWidth(1)
                layout.addWidget(h_separator, n_row_offset + 4, 0, 1, normal_volume_count * 4,
                                 alignment=Qt.AlignTop)

                self.normal_volume_source_entries.append(
                    (name_entry, lat_entry, lon_entry, vlemis_entry, relhgt_entry, syinit_entry, szinit_entry)
                )

        # Urban Volume Sources
        if urban_volume_count > 0:
            for i in range(urban_volume_count):
                col_offset = i * 4

                try:
                    vertex_counts = self.read_area_def()
                    if vertex_counts is None or not isinstance(vertex_counts, dict):
                        raise ValueError("self.read_area_def() returned an invalid result")
                    if normal_area_count > 0:
                        nvertex_count = max([vertex_counts.get(f"NAREA{i + 1}", 3) for i in range(normal_area_count)])
                    else:
                        nvertex_count = 0
                except (FileNotFoundError, ValueError, AttributeError, TypeError) as e:
                    nvertex_count = 0

                try:
                    vertex_counts = self.read_area_def()
                    if vertex_counts is None or not isinstance(vertex_counts, dict):
                        raise ValueError("self.read_area_def() returned an invalid result")
                    if urban_area_count > 0:
                        uvertex_count = max([vertex_counts.get(f"UAREA{i + 1}", 3) for i in range(urban_area_count)])
                    else:
                        uvertex_count = 0
                except (FileNotFoundError, ValueError, AttributeError, TypeError) as e:
                    uvertex_count = 0

                def calculate_u_row_offset():
                    offset = 15
                    if point_normal_count > 0:
                        offset += 5
                    if point_urban_count > 0:
                        offset += 6
                    if normal_line_count > 0:
                        offset += 5
                    if urban_line_count > 0:
                        offset += 6
                    if normal_area_count > 0:
                        offset += 3 + nvertex_count
                    if urban_area_count > 0:
                        offset += 4 + uvertex_count
                    if normal_volume_count > 0:
                        offset += 4
                    return offset

                u_row_offset = calculate_u_row_offset()

                viz_button = QPushButton("Visualize")
                viz_button.setFixedWidth(50)
                viz_button.clicked.connect(lambda checked, idx=i: self.visualize_urban_volume_source(idx))
                layout.addWidget(viz_button, u_row_offset, col_offset + 1)
                self.setTooltip(viz_button, f"Visualize urban volume source {i + 1} on QGIS map")

                map_button = QPushButton("Map ✜")
                map_button.setFixedWidth(50)
                map_button.clicked.connect(lambda checked, idx=i: self.capture_urban_volume_source(idx))
                layout.addWidget(map_button, u_row_offset, col_offset + 2)
                self.setTooltip(map_button, f"Select urban volume source {i + 1} center on QGIS map")

                name_label = QLabel("Name")
                name_label.setFont(QFont('Arial', 8))
                name_label.setFixedWidth(50)
                name_label.setAlignment(Qt.AlignCenter)
                name_entry = QLineEdit(f"UVOL{i + 1}")
                name_entry.setFixedWidth(75)
                layout.addWidget(name_label, u_row_offset + 1, col_offset)
                layout.addWidget(name_entry, u_row_offset + 1, col_offset + 1)
                self.setTooltip(name_label, "Urban volume source name; Srcid")

                area_label = QLabel("Area")
                area_label.setFont(QFont('Arial', 8))
                area_label.setAlignment(Qt.AlignCenter)
                area_label.setFixedWidth(50)
                area_entry = QLineEdit(f"City1")
                area_entry.setFixedWidth(75)
                layout.addWidget(area_label, u_row_offset + 1, col_offset + 2)
                layout.addWidget(area_entry, u_row_offset + 1, col_offset + 3)
                self.setTooltip(area_label, "Urban area name; Add to specify urban area affiliation")

                lon_label = QLabel("Easting")
                lon_label.setFont(QFont('Arial', 8))
                lon_label.setFixedWidth(50)
                lon_label.setAlignment(Qt.AlignCenter)
                lon_entry = QLineEdit()
                lon_entry.setFixedWidth(75)
                layout.addWidget(lon_label, u_row_offset + 2, col_offset)
                layout.addWidget(lon_entry, u_row_offset + 2, col_offset + 1)
                self.setTooltip(lon_label, "UTM easting coordinate, up to 4 decimal places (Urban); Xs")

                lat_label = QLabel("Northing")
                lat_label.setFont(QFont('Arial', 8))
                lat_label.setFixedWidth(50)
                lat_label.setAlignment(Qt.AlignCenter)
                lat_entry = QLineEdit()
                lat_entry.setFixedWidth(75)
                layout.addWidget(lat_label, u_row_offset + 2, col_offset + 2)
                layout.addWidget(lat_entry, u_row_offset + 2, col_offset + 3)
                self.setTooltip(lat_label, "UTM northing coordinate, up to 4 decimal places (Urban); Yd")

                vlemis_label = QLabel("Load (g/s)")
                vlemis_label.setFont(QFont('Arial', 8))
                vlemis_label.setFixedWidth(50)
                vlemis_label.setAlignment(Qt.AlignCenter)
                vlemis_entry = QLineEdit()
                vlemis_entry.setFixedWidth(50)
                layout.addWidget(vlemis_label, u_row_offset + 3, col_offset)
                layout.addWidget(vlemis_entry, u_row_offset + 3, col_offset + 1)
                self.setTooltip(vlemis_label, "Volume emission rate (g/s); Vlemis")

                relhgt_label = QLabel("Release (m)")
                relhgt_label.setFont(QFont('Arial', 8))
                relhgt_label.setFixedWidth(75)
                relhgt_label.setAlignment(Qt.AlignCenter)
                relhgt_entry = QLineEdit()
                relhgt_entry.setFixedWidth(50)
                layout.addWidget(relhgt_label, u_row_offset + 3, col_offset + 2)
                layout.addWidget(relhgt_entry, u_row_offset + 3, col_offset + 3)
                self.setTooltip(relhgt_label, "Release height (center of volume) above ground (m); Relhgt")

                syinit_label = QLabel("Y Inital (m)")
                syinit_label.setFont(QFont('Arial', 8))
                syinit_label.setFixedWidth(75)
                syinit_label.setAlignment(Qt.AlignCenter)
                syinit_entry = QLineEdit()
                syinit_entry.setFixedWidth(50)
                layout.addWidget(syinit_label, u_row_offset + 4, col_offset)
                layout.addWidget(syinit_entry, u_row_offset + 4, col_offset + 1)
                self.setTooltip(syinit_label, "Initial lateral dimension of the volume (m); Syinit\n"
                                              "Single Volume Source = length of side divided by 4.3\n"
                                              "Line Source Represented by Adjacent Volume Sources "
                                              "= length of side divided by 2.15\n"
                                              "Line Source Represented by Separated Volume Sources "
                                              "= center to center distance divided by 2.15")

                szinit_label = QLabel("Z Inital (m)")
                szinit_label.setFont(QFont('Arial', 8))
                szinit_label.setFixedWidth(50)
                szinit_label.setAlignment(Qt.AlignCenter)
                szinit_entry = QLineEdit()
                szinit_entry.setFixedWidth(50)
                layout.addWidget(szinit_label, u_row_offset + 4, col_offset + 2)
                layout.addWidget(szinit_entry, u_row_offset + 4, col_offset + 3)
                self.setTooltip(szinit_label, "Initial vertical dimension of the volume (m); Sziniz\n"
                                              "Surface-Based Source (he ~ 0) "
                                              "= vertical dimension of source divided by 2.15\n"
                                              "Elevated Source (he > 0) on or Adjacent to a Building "
                                              "= building height divided by 2.15\n"
                                              "Elevated Source (he > 0) not on or Adjacent to a Building "
                                              "= vertical dimension of source divided by 4.3")

                if i < urban_volume_count - 1:
                    separator = QFrame()
                    separator.setFrameShape(QFrame.VLine)
                    separator.setFrameShadow(QFrame.Sunken)
                    separator.setLineWidth(1)
                    total_rows = 5
                    layout.addWidget(separator, u_row_offset, col_offset + 4, total_rows, 1, alignment=Qt.AlignLeft)

                h_separator = QFrame()
                h_separator.setFrameShape(QFrame.HLine)
                h_separator.setFrameShadow(QFrame.Sunken)
                h_separator.setLineWidth(1)
                layout.addWidget(h_separator, u_row_offset + 5, 0, 1, urban_volume_count * 4,
                                 alignment=Qt.AlignTop)

                self.urban_volume_source_entries.append(
                    (name_entry, area_entry, lat_entry, lon_entry, vlemis_entry, relhgt_entry, syinit_entry, szinit_entry)
                )

    def generate_output(self):
        output = ""

        # CO Section
        output += "CO STARTING\n"
        if self.title_entry.text():
            output += f"CO TITLEONE  {self.title_entry.text()}\n"
        averaging_periods = [period["time_entry"].text() for period in self.avg_period_widgets if
                             period["time_entry"].text()]
        if averaging_periods:
            output += f"CO AVERTIME {' '.join(averaging_periods)}\n"
        output += "CO MODELOPT DFAULT CONC\n"
        if self.pollutant_entry.text():
            output += f"CO POLLUTID  {self.pollutant_entry.text()}\n"
        if self.flagpole_entry.text():
            output += f"CO FLAGPOLE  {self.flagpole_entry.text()}\n"
        output += "CO RUNORNOT RUN\n"
        urban_source_types = ["POINT", "LINE", "AREA", "VOLUME"]
        has_urban_sources = any(
            int(self.source_counts.get(src_type, ("0", "0"))[1]) > 0 for src_type in urban_source_types
        )
        if has_urban_sources:
            num_urban_areas = len(self.urban_areas_entries)
            for urban_area_entry, population_entry, urban_rough_entry in self.urban_areas_entries:
                urban_area = urban_area_entry.text().strip()
                population = population_entry.text().strip()
                roughness = urban_rough_entry.text().strip()
                if population:
                    if num_urban_areas == 1:
                        output += f"CO URBANOPT {population} {urban_area} {roughness}\n"
                    else:
                        output += f"CO URBANOPT {urban_area} {population} {urban_area} {roughness}\n"
        output += "CO FINISHED\n\n"
        # SO Section
        output += "SO STARTING\n"
        output += "SO ELEVUNIT METERS\n"

        # 1. All SO LOCATION lines
        for point in self.normal_pointsource_entries:
            name, lon, lat, base, rate, height, temp, vel, diam = point
            if lon.text() and lat.text():
                output += f"SO LOCATION {name.text()} POINT {lon.text()} {lat.text()} {base.text() or '0.0'}\n"

        for point in self.urban_pointsource_entries:
            name, area, lon, lat, base, rate, height, temp, vel, diam = point
            if lon.text() and lat.text():
                output += f"SO LOCATION {name.text()} POINT {lon.text()} {lat.text()} {base.text() or '0.0'}\n"

        for area in self.normal_area_source_entries:
            name = area["name_entry"].text()
            vertices = [(n.text(), e.text()) for n, e in area["vertices"] if n.text() and e.text()]
            if vertices:
                output += f"SO LOCATION {name} AREAPOLY {vertices[0][1]} {vertices[0][0]}\n"

        for area in self.urban_area_source_entries:
            name = area["name_entry"].text()
            vertices = [(n.text(), e.text()) for n, e in area["vertices"] if n.text() and e.text()]
            if vertices:
                output += f"SO LOCATION {name} AREAPOLY {vertices[0][1]} {vertices[0][0]}\n"

        for volume in self.normal_volume_source_entries:
            name, lat, lon, vlemis, relhgt, syinit, szinit = volume
            if lat.text() and lon.text():
                output += f"SO LOCATION {name.text()} VOLUME {lon.text()} {lat.text()} 0.0\n"

        for volume in self.urban_volume_source_entries:
            name, area, lat, lon, vlemis, relhgt, syinit, szinit = volume
            if lat.text() and lon.text():
                output += f"SO LOCATION {name.text()} VOLUME {lon.text()} {lat.text()} 0.0\n"

        for line in self.normal_line_source_entries:
            name, easting_start, northing_start, easting_end, northing_end, lnemis, relhgt, width, szinit = line
            if easting_start.text() and northing_start.text() and easting_end.text() and northing_end.text():
                output += f"SO LOCATION {name.text()} LINE {easting_start.text()} {northing_start.text()} {easting_end.text()} {northing_end.text()}\n"

        for line in self.urban_line_source_entries:
            name, area, easting_start, northing_start, easting_end, northing_end, lnemis, relhgt, width, szinit = line
            if easting_start.text() and northing_start.text() and easting_end.text() and northing_end.text():
                output += f"SO LOCATION {name.text()} LINE {easting_start.text()} {northing_start.text()} {easting_end.text()} {northing_end.text()}\n"

        # 2. All SO URBANSRC lines for urban sources
        urban_sources = (
                [(point[0].text(), point[1].text()) for point in self.urban_pointsource_entries if
                 point[2].text() and point[3].text()] +
                [(area["name_entry"].text(), area["area_entry"].text()) for area in self.urban_area_source_entries if
                 area["vertices"]] +
                [(volume[0].text(), volume[1].text()) for volume in self.urban_volume_source_entries if
                 volume[2].text() and volume[3].text()] +
                [(line[0].text(), line[1].text()) for line in self.urban_line_source_entries if
                 line[2].text() and line[3].text() and line[4].text() and line[5].text()]
        )

        # Check number of urban areas from the earlier section
        num_urban_areas = len(self.urban_areas_entries) if hasattr(self, 'urban_areas_entries') else 0

        for source_name, area_name in urban_sources:
            if source_name and area_name:
                if num_urban_areas == 1:
                    output += f"SO URBANSRC {source_name}\n"
                else:
                    output += f"SO URBANSRC {area_name} {source_name}\n"

        # 3. All SO SRCPARAM lines
        for point in self.normal_pointsource_entries:
            name, lat, lon, base, rate, height, temp, vel, diam = point
            if lat.text() and lon.text():
                output += f"SO SRCPARAM {name.text()} {rate.text()} {height.text()} {temp.text()} {vel.text()} {diam.text()}\n"

        for point in self.urban_pointsource_entries:
            name, area, lat, lon, base, rate, height, temp, vel, diam = point
            if lat.text() and lon.text():
                output += f"SO SRCPARAM {name.text()} {rate.text()} {height.text()} {temp.text()} {vel.text()} {diam.text()}\n"

        for area in self.normal_area_source_entries:
            name = area["name_entry"].text()
            rate = area["rate_entry"].text()
            rheight = area["rheight_entry"].text()
            iheight = area["iheight_entry"].text()
            vertices = [(n.text(), e.text()) for n, e in area["vertices"] if n.text() and e.text()]
            if vertices:
                output += f"SO SRCPARAM {name} {rate} {rheight} {len(vertices)} {iheight}\n"

        for area in self.urban_area_source_entries:
            name = area["name_entry"].text()
            rate = area["rate_entry"].text()
            rheight = area["rheight_entry"].text()
            iheight = area["iheight_entry"].text()
            vertices = [(n.text(), e.text()) for n, e in area["vertices"] if n.text() and e.text()]
            if vertices:
                output += f"SO SRCPARAM {name} {rate} {rheight} {len(vertices)} {iheight}\n"

        for volume in self.normal_volume_source_entries:
            name, lat, lon, vlemis, relhgt, syinit, szinit = volume
            if lat.text() and lon.text():
                output += f"SO SRCPARAM {name.text()} {vlemis.text()} {relhgt.text()} {syinit.text()} {szinit.text()}\n"

        for volume in self.urban_volume_source_entries:
            name, area, lat, lon, vlemis, relhgt, syinit, szinit = volume
            if lat.text() and lon.text():
                output += f"SO SRCPARAM {name.text()} {vlemis.text()} {relhgt.text()} {syinit.text()} {szinit.text()}\n"

        for line in self.normal_line_source_entries:
            name, easting_start, northing_start, easting_end, northing_end, lnemis, relhgt, width, szinit = line
            if easting_start.text() and northing_start.text() and easting_end.text() and northing_end.text():
                output += f"SO SRCPARAM {name.text()} {lnemis.text()} {relhgt.text()} {width.text()} {szinit.text()}\n"

        for line in self.urban_line_source_entries:
            name, area, easting_start, northing_start, easting_end, northing_end, lnemis, relhgt, width, szinit = line
            if easting_start.text() and northing_start.text() and easting_end.text() and northing_end.text():
                output += f"SO SRCPARAM {name.text()} {lnemis.text()} {relhgt.text()} {width.text()} {szinit.text()}\n"

        # 4. All SO AREAVERT lines
        for area in self.normal_area_source_entries:
            name = area["name_entry"].text()
            vertices = [(n.text(), e.text()) for n, e in area["vertices"] if n.text() and e.text()]
            if vertices:
                num_vertices = len(vertices)
                coords = [coord for vertex in vertices for coord in (vertex[1], vertex[0])]  # east, north order
                output += f"SO AREAVERT {name} {' '.join(coords)}\n"

        for area in self.urban_area_source_entries:
            name = area["name_entry"].text()
            vertices = [(n.text(), e.text()) for n, e in area["vertices"] if n.text() and e.text()]
            if vertices:
                num_vertices = len(vertices)
                coords = [coord for vertex in vertices for coord in (vertex[1], vertex[0])]  # east, north order
                output += f"SO AREAVERT {name} {' '.join(coords)}\n"

        for group in self.normal_group_entries:
            gname_entry, sources_entry = group
            if sources_entry.text():
                source_text = sources_entry.text().strip().upper()

                if source_text == "ALL":
                    all_sources = (
                            [point[0].text() for point in self.normal_pointsource_entries if
                             point[1].text() and point[2].text()] +
                            [point[0].text() for point in self.urban_pointsource_entries if
                             point[2].text() and point[3].text()] +
                            [area["name_entry"].text() for area in self.normal_area_source_entries if
                             area["vertices"]] +
                            [area["name_entry"].text() for area in self.urban_area_source_entries if area["vertices"]] +
                            [line[0].text() for line in self.normal_line_source_entries if
                             line[1].text() and line[2].text() and line[3].text() and line[4].text()] +
                            [line[0].text() for line in self.urban_line_source_entries if
                             line[2].text() and line[3].text() and line[4].text() and line[5].text()] +
                            [volume[0].text() for volume in self.normal_volume_source_entries if
                             volume[1].text() and volume[2].text()] +
                            [volume[0].text() for volume in self.urban_volume_source_entries if
                             volume[2].text() and volume[3].text()]
                    )
                    if all_sources:
                        output += f"SO SRCGROUP {gname_entry.text()} {' '.join(all_sources)}\n"

                elif source_text == "ALLRURAL":
                    rural_sources = (
                            [point[0].text() for point in self.normal_pointsource_entries if
                             point[1].text() and point[2].text()] +
                            [area["name_entry"].text() for area in self.normal_area_source_entries if
                             area["vertices"]] +
                            [line[0].text() for line in self.normal_line_source_entries if
                             line[1].text() and line[2].text() and line[3].text() and line[4].text()] +
                            [volume[0].text() for volume in self.normal_volume_source_entries if
                             volume[1].text() and volume[2].text()]
                    )
                    if rural_sources:
                        output += f"SO SRCGROUP {gname_entry.text()} {' '.join(rural_sources)}\n"

                elif source_text == "ALLURB":
                    urban_sources = (
                            [point[0].text() for point in self.urban_pointsource_entries if
                             point[2].text() and point[3].text()] +
                            [area["name_entry"].text() for area in self.urban_area_source_entries if area["vertices"]] +
                            [line[0].text() for line in self.urban_line_source_entries if
                             line[2].text() and line[3].text() and line[4].text() and line[5].text()] +
                            [volume[0].text() for volume in self.urban_volume_source_entries if
                             volume[2].text() and volume[3].text()]
                    )
                    if urban_sources:
                        output += f"SO SRCGROUP {gname_entry.text()} {' '.join(urban_sources)}\n"

                else:
                    output += f"SO SRCGROUP {gname_entry.text()} {sources_entry.text()}\n"

        output += "SO FINISHED\n\n"

        # RE Section
        output += "RE STARTING\n"
        if self.map_entries:
            output += f"RE INCLUDED {os.path.basename(self.map_entries[0][1])}\n"
        output += "RE FINISHED\n\n"

        # ME Section
        output += "ME STARTING\n"
        if self.sfc_entries:
            output += f"ME SURFFILE {os.path.basename(self.sfc_entries[0][1])}\n"
        if self.prof_entries:
            output += f"ME PROFFILE {os.path.basename(self.prof_entries[0][1])}\n"
        if self.station_num_entry.text():
            output += f"ME SURFDATA {self.station_num_entry.text()} {self.start_year_entry.text()}\n"
        if self.upper_air_station_num_entry.text():
            output += f"ME UAIRDATA {self.upper_air_station_num_entry.text()} {self.start_year_upper_air_entry.text()} \n"
        if self.start_date_entry.text():
            if self.base_elevation_entry.text():
                output += f"ME PROFBASE {self.base_elevation_entry.text()} METERS\n"
            output += (f"ME STARTEND {self.start_date_entry.text()} "
                       f"{self.end_date_entry.text() if self.end_date_entry.text()
                       else self.start_date_entry.text()}\n")
        output += "ME FINISHED\n\n"

        # OU Section
        output += "OU STARTING\n"

        rec_table = self.rec_table_entry.text().strip()
        max_table = self.max_table_entry.text().strip()
        output += f"OU RECTABLE ALLAVE {rec_table}\n"
        output += f"OU MAXTABLE ALLAVE {max_table}\n"

        if self.avg_period_widgets:
            valid_groups = [(gname_entry, sources_entry) for gname_entry, sources_entry in self.normal_group_entries if
                            sources_entry.text()]
            if valid_groups:
                rankfile_lines = []
                for period in self.avg_period_widgets:
                    time = period["time_entry"].text().strip()
                    rank = period["rank_entry"].text().strip()
                    if time and rank and time.upper() not in ["PERIOD", "YEAR"]:
                        rectable_line = f"OU RANKFILE {time} {rank} RANK{time}.RNK"
                        rankfile_lines.append(rectable_line + "\n")
                output += "".join(rankfile_lines)

                maxifile_lines = []
                for period in self.avg_period_widgets:
                    time = period["time_entry"].text().strip()
                    thresh = period["max_entry"].text().strip()
                    if time and thresh:
                        for gname_entry, _ in valid_groups:
                            if gname_entry.text():
                                maxifile_lines.append(
                                    f"OU MAXIFILE {time} {gname_entry.text()} {thresh} MAX{time}H_{gname_entry.text()}.OUT\n"
                                )
                output += "".join(maxifile_lines)

                plotfile_lines = []
                for period in self.avg_period_widgets:
                    time = period["time_entry"].text().strip()
                    plot = period["plot_entry"].text().strip()
                    thresh = period["max_entry"].text().strip()
                    if time and thresh:
                        time_upper = time.upper()
                        for gname_entry, _ in valid_groups:
                            if gname_entry.text():
                                suffix = "" if time_upper in ["MONTH", "YEAR", "PERIOD"] else "H"
                                plot_text = "" if time_upper in ["PERIOD", "YEAR"] else f"{plot} " if plot else ""
                                plotfile_lines.append(
                                    f"OU PLOTFILE {time} {gname_entry.text()} {plot_text}PLOT{time}{suffix}_{gname_entry.text()}.PLT\n"
                                )
                output += "".join(plotfile_lines)
        output += "OU FINISHED\n"
        return output

    def compile_output(self):
        output_text_content = self.generate_output()
        folder_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")

        if folder_path:
            file_path = os.path.join(folder_path, "aermod.inp")
            try:
                with open(file_path, "w") as file:
                    file.write(output_text_content)

                files_to_copy = [
                    ("Receptor File", self.map_entries),
                    ("Surface Meteo Data File", self.sfc_entries),
                    ("Profile Data File", self.prof_entries),
                ]
                for description, entries in files_to_copy:
                    if entries:
                        for _, full_path in entries:  # Unpack tuple (entry, full_path)
                            file_name = os.path.basename(full_path)
                            destination = os.path.join(folder_path, file_name)
                            if not os.path.exists(destination):
                                try:
                                    copyfile(full_path, destination)
                                    print(f"Copied {file_name} ({description}) to {folder_path}")
                                except Exception as e:
                                    print(f"Error copying {description}: {e}")
                            else:
                                print(f"{file_name} already exists in the destination folder. Skipping.")

                iface.messageBar().pushMessage("Success", "AERMOD input file generated successfully.", level=0)
                self.close()
            except Exception as e:
                iface.messageBar().pushMessage("Error", f"Failed to generate file: {str(e)}", level=3)

    def capture_normal_point_source(self, index):
        canvas = iface.mapCanvas()
        tool = QgsMapToolEmitPoint(canvas)

        def on_point_clicked(point):
            easting, northing = point.x(), point.y()
            self.normal_pointsource_entries[index][1].setText(f"{easting:.4f}")  # lon_entry (easting)
            self.normal_pointsource_entries[index][2].setText(f"{northing:.4f}")  # lat_entry (northing)
            canvas.unsetMapTool(tool)

        tool.canvasClicked.connect(on_point_clicked)
        canvas.setMapTool(tool)

    def visualize_normal_point_source(self, index):
        try:
            name = self.normal_pointsource_entries[index][0].text() or None
            easting_text = self.normal_pointsource_entries[index][1].text()
            northing_text = self.normal_pointsource_entries[index][2].text()
            base_text = self.normal_pointsource_entries[index][3].text()
            rate_text = self.normal_pointsource_entries[index][4].text()
            height_text = self.normal_pointsource_entries[index][5].text()
            temp_text = self.normal_pointsource_entries[index][6].text()
            vel_text = self.normal_pointsource_entries[index][7].text()
            diam_text = self.normal_pointsource_entries[index][8].text()

            easting = float(easting_text) if easting_text else None
            northing = float(northing_text) if northing_text else None
            base = float(base_text) if base_text else None
            rate = float(rate_text) if rate_text else None
            height = float(height_text) if height_text else None
            temp = float(temp_text) if temp_text else None
            vel = float(vel_text) if vel_text else None
            diam = float(diam_text) if diam_text else None

            if easting is None or northing is None:
                raise ValueError("Easting and Northing are required for visualization")

            crs_name = QgsProject.instance().crs().description() or None

            if not hasattr(self, 'normal_point_layer') or not self.normal_point_layer.isValid():
                project_crs = QgsProject.instance().crs()
                self.normal_point_layer = QgsVectorLayer(f"Point?crs={project_crs.authid()}", "Normal Point Sources",
                                                         "memory")
                self.normal_point_layer.dataProvider().addAttributes([
                    QgsField("name", QVariant.String),
                    QgsField("easting", QVariant.Double),
                    QgsField("northing", QVariant.Double),
                    QgsField("base elevation", QVariant.Double),
                    QgsField("emisson rate", QVariant.Double),
                    QgsField("stack height", QVariant.Double),
                    QgsField("temperature", QVariant.Double),
                    QgsField("velocity", QVariant.Double),
                    QgsField("diameter", QVariant.Double),
                    QgsField("CRS", QVariant.String)
                ])
                self.normal_point_layer.updateFields()
                QgsProject.instance().addMapLayer(self.normal_point_layer)

            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(easting, northing)))
            feature.setAttributes([name, easting, northing, base, rate, height, temp, vel, diam, crs_name])
            self.normal_point_layer.startEditing()
            self.normal_point_layer.addFeature(feature)
            self.normal_point_layer.commitChanges()
            self.normal_point_layer.triggerRepaint()
        except ValueError as e:
            print(f"Error for normal point source {index + 1}: {str(e)}")

    def capture_urban_point_source(self, index):
        canvas = iface.mapCanvas()
        tool = QgsMapToolEmitPoint(canvas)

        def on_point_clicked(point):
            easting, northing = point.x(), point.y()
            self.urban_pointsource_entries[index][2].setText(f"{easting:.4f}")
            self.urban_pointsource_entries[index][3].setText(f"{northing:.4f}")
            canvas.unsetMapTool(tool)

        tool.canvasClicked.connect(on_point_clicked)
        canvas.setMapTool(tool)

    def visualize_urban_point_source(self, index):
        try:
            name = self.urban_pointsource_entries[index][0].text() or None
            area = self.urban_pointsource_entries[index][1].text() or None
            easting_text = self.urban_pointsource_entries[index][2].text()
            northing_text = self.urban_pointsource_entries[index][3].text()
            base_text = self.urban_pointsource_entries[index][4].text()
            rate_text = self.urban_pointsource_entries[index][5].text()
            height_text = self.urban_pointsource_entries[index][6].text()
            temp_text = self.urban_pointsource_entries[index][7].text()
            vel_text = self.urban_pointsource_entries[index][8].text()
            diam_text = self.urban_pointsource_entries[index][9].text()

            easting = float(easting_text) if easting_text else None
            northing = float(northing_text) if northing_text else None
            base = float(base_text) if base_text else None
            rate = float(rate_text) if rate_text else None
            height = float(height_text) if height_text else None
            temp = float(temp_text) if temp_text else None
            vel = float(vel_text) if vel_text else None
            diam = float(diam_text) if diam_text else None

            if easting is None or northing is None:
                raise ValueError("Easting and Northing are required for visualization")

            crs_name = QgsProject.instance().crs().description() or None

            if not hasattr(self, 'urban_point_layer') or not self.urban_point_layer.isValid():
                project_crs = QgsProject.instance().crs()
                self.urban_point_layer = QgsVectorLayer(f"Point?crs={project_crs.authid()}",
                                                        "Urban Point Sources",
                                                        "memory")
                self.urban_point_layer.dataProvider().addAttributes([
                    QgsField("name", QVariant.String),
                    QgsField("urban area", QVariant.String),
                    QgsField("easting", QVariant.Double),
                    QgsField("northing", QVariant.Double),
                    QgsField("base elevation", QVariant.Double),
                    QgsField("emission rate", QVariant.Double),
                    QgsField("stack height", QVariant.Double),
                    QgsField("temperature", QVariant.Double),
                    QgsField("velocity", QVariant.Double),
                    QgsField("diameter", QVariant.Double),
                    QgsField("CRS", QVariant.String)
                ])
                self.urban_point_layer.updateFields()
                QgsProject.instance().addMapLayer(self.urban_point_layer)

            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(easting, northing)))
            feature.setAttributes([name, area, easting, northing, base, rate, height, temp, vel, diam, crs_name])
            self.urban_point_layer.startEditing()
            self.urban_point_layer.addFeature(feature)
            self.urban_point_layer.commitChanges()
            self.urban_point_layer.triggerRepaint()
        except ValueError as e:
            print(f"Error for urban point source {index + 1}: {str(e)}")

    def capture_normal_line_source(self, index):
        canvas = iface.mapCanvas()
        tool = self.TwoPointMapTool(canvas, lambda start, end: self._set_normal_line_coords(index, start, end))
        canvas.setMapTool(tool)

    def _set_normal_line_coords(self, index, start_point, end_point):
        easting_start, northing_start = start_point.x(), start_point.y()
        easting_end, northing_end = end_point.x(), end_point.y()
        self.normal_line_source_entries[index][1].setText(f"{easting_start:.4f}")
        self.normal_line_source_entries[index][2].setText(f"{northing_start:.4f}")
        self.normal_line_source_entries[index][3].setText(f"{easting_end:.4f}")
        self.normal_line_source_entries[index][4].setText(f"{northing_end:.4f}")

    def visualize_normal_line_source(self, index):
        try:
            name = self.normal_line_source_entries[index][0].text() or None
            easting_start_text = self.normal_line_source_entries[index][1].text()
            northing_start_text = self.normal_line_source_entries[index][2].text()
            easting_end_text = self.normal_line_source_entries[index][3].text()
            northing_end_text = self.normal_line_source_entries[index][4].text()
            lnemis_text = self.normal_line_source_entries[index][5].text()
            relhgt_text = self.normal_line_source_entries[index][6].text()
            width_text = self.normal_line_source_entries[index][7].text()
            szinit_text = self.normal_line_source_entries[index][8].text()

            easting_start = float(easting_start_text) if easting_start_text else None
            northing_start = float(northing_start_text) if northing_start_text else None
            easting_end = float(easting_end_text) if easting_end_text else None
            northing_end = float(northing_end_text) if northing_end_text else None
            lnemis = float(lnemis_text) if lnemis_text else None
            relhgt = float(relhgt_text) if relhgt_text else None
            width = float(width_text) if width_text else None
            szinit = float(szinit_text) if szinit_text else None

            if any(v is None for v in [easting_start, northing_start, easting_end, northing_end]):
                raise ValueError("All start and end coordinates are required for visualization")

            crs_name = QgsProject.instance().crs().description() or None

            if not hasattr(self, 'normal_line_layer') or not self.normal_line_layer.isValid():
                project_crs = QgsProject.instance().crs()
                self.normal_line_layer = QgsVectorLayer(f"LineString?crs={project_crs.authid()}",
                                                        "Normal Line Sources",
                                                        "memory")
                self.normal_line_layer.dataProvider().addAttributes([
                    QgsField("name", QVariant.String),
                    QgsField("easting_start", QVariant.Double),
                    QgsField("northing_start", QVariant.Double),
                    QgsField("easting_end", QVariant.Double),
                    QgsField("northing_end", QVariant.Double),
                    QgsField("emission rate", QVariant.Double),
                    QgsField("relhgt", QVariant.Double),
                    QgsField("width", QVariant.Double),
                    QgsField("szinit", QVariant.Double),
                    QgsField("CRS", QVariant.String)
                ])
                self.normal_line_layer.updateFields()
                QgsProject.instance().addMapLayer(self.normal_line_layer)

                symbol = QgsLineSymbol.createSimple({
                    'line_style': 'solid',
                    'color': 'green',
                    'width': '1'
                })
                self.normal_line_layer.renderer().setSymbol(symbol)

            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPolylineXY(
                [QgsPointXY(easting_start, northing_start), QgsPointXY(easting_end, northing_end)]))
            feature.setAttributes(
                [name, easting_start, northing_start, easting_end, northing_end, lnemis, relhgt, width, szinit,
                 crs_name])
            self.normal_line_layer.startEditing()
            self.normal_line_layer.addFeature(feature)
            self.normal_line_layer.commitChanges()
            self.normal_line_layer.triggerRepaint()
        except ValueError as e:
            print(f"Error for normal line source {index + 1}: {str(e)}")

    def capture_urban_line_source(self, index):
        canvas = iface.mapCanvas()
        tool = self.TwoPointMapTool(canvas, lambda start, end: self._set_urban_line_coords(index, start, end))
        canvas.setMapTool(tool)

    def _set_urban_line_coords(self, index, start_point, end_point):
        easting_start, northing_start = start_point.x(), start_point.y()
        easting_end, northing_end = end_point.x(), end_point.y()
        self.urban_line_source_entries[index][2].setText(f"{easting_start:.4f}")
        self.urban_line_source_entries[index][3].setText(f"{northing_start:.4f}")
        self.urban_line_source_entries[index][4].setText(f"{easting_end:.4f}")
        self.urban_line_source_entries[index][5].setText(f"{northing_end:.4f}")

    def visualize_urban_line_source(self, index):
        try:
            name = self.urban_line_source_entries[index][0].text() or None
            area = self.urban_line_source_entries[index][1].text() or None
            easting_start_text = self.urban_line_source_entries[index][2].text()
            northing_start_text = self.urban_line_source_entries[index][3].text()
            easting_end_text = self.urban_line_source_entries[index][4].text()
            northing_end_text = self.urban_line_source_entries[index][5].text()
            lnemis_text = self.urban_line_source_entries[index][6].text()
            relhgt_text = self.urban_line_source_entries[index][7].text()
            width_text = self.urban_line_source_entries[index][8].text()
            szinit_text = self.urban_line_source_entries[index][9].text()

            easting_start = float(easting_start_text) if easting_start_text else None
            northing_start = float(northing_start_text) if northing_start_text else None
            easting_end = float(easting_end_text) if easting_end_text else None
            northing_end = float(northing_end_text) if northing_end_text else None
            lnemis = float(lnemis_text) if lnemis_text else None
            relhgt = float(relhgt_text) if relhgt_text else None
            width = float(width_text) if width_text else None
            szinit = float(szinit_text) if szinit_text else None

            if any(v is None for v in [easting_start, northing_start, easting_end, northing_end]):
                raise ValueError("All start and end coordinates are required for visualization")

            crs_name = QgsProject.instance().crs().description() or None

            if not hasattr(self, 'urban_line_layer') or not self.urban_line_layer.isValid():
                project_crs = QgsProject.instance().crs()
                self.urban_line_layer = QgsVectorLayer(f"LineString?crs={project_crs.authid()}", "Urban Line Sources",
                                                       "memory")
                self.urban_line_layer.dataProvider().addAttributes([
                    QgsField("name", QVariant.String),
                    QgsField("Urban area", QVariant.String),
                    QgsField("easting_start", QVariant.Double),
                    QgsField("northing_start", QVariant.Double),
                    QgsField("easting_end", QVariant.Double),
                    QgsField("northing_end", QVariant.Double),
                    QgsField("emission rate", QVariant.Double),
                    QgsField("relhgt", QVariant.Double),
                    QgsField("width", QVariant.Double),
                    QgsField("szinit", QVariant.Double),
                    QgsField("CRS", QVariant.String)
                ])
                self.urban_line_layer.updateFields()
                QgsProject.instance().addMapLayer(self.urban_line_layer)
                # Set up the line symbology (do this only when creating the layer)
                symbol = QgsLineSymbol.createSimple({
                    'line_style': 'solid',
                    'color': 'blue',  # You can change the color
                    'width': '1'  # Set line width (in millimeters), default is usually 0.26
                })
                self.urban_line_layer.renderer().setSymbol(symbol)

            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPolylineXY(
                [QgsPointXY(easting_start, northing_start), QgsPointXY(easting_end, northing_end)]))
            feature.setAttributes(
                [name, area, easting_start, northing_start, easting_end, northing_end, lnemis, relhgt, width, szinit,
                 crs_name])
            self.urban_line_layer.startEditing()
            self.urban_line_layer.addFeature(feature)
            self.urban_line_layer.commitChanges()
            self.urban_line_layer.triggerRepaint()
        except ValueError as e:
            print(f"Error for urban line source {index + 1}: {str(e)}")

    def capture_normal_area_source(self, index):
        canvas = iface.mapCanvas()
        entry = self.normal_area_source_entries[index]
        vertex_count = len(entry["vertices"])

        def set_coords(points):
            for j, point in enumerate(points):
                northing_entry, easting_entry = entry["vertices"][j]
                easting, northing = point.x(), point.y()
                easting_entry.setText(f"{easting:.4f}")
                northing_entry.setText(f"{northing:.4f}")

        tool = self.MultiPointMapTool(canvas, set_coords, vertex_count)
        canvas.setMapTool(tool)

    def visualize_normal_area_source(self, index):
        try:
            entry = self.normal_area_source_entries[index]
            name = entry["name_entry"].text() or None
            rate_text = entry["rate_entry"].text()
            rheight_text = entry["rheight_entry"].text()
            iheight_text = entry["iheight_entry"].text()

            rate = float(rate_text) if rate_text else None
            rheight = float(rheight_text) if rheight_text else None
            iheight = float(iheight_text) if iheight_text else None

            vertices = []
            for northing_entry, easting_entry in entry["vertices"]:
                easting_text = easting_entry.text()
                northing_text = northing_entry.text()
                easting = float(easting_text) if easting_text else None
                northing = float(northing_text) if northing_text else None
                if easting is None or northing is None:
                    raise ValueError(f"Vertex {len(vertices) + 1} missing coordinates")
                vertices.append(QgsPointXY(easting, northing))
            vertices.append(vertices[0])

            crs_name = QgsProject.instance().crs().description() or None

            if not hasattr(self, 'normal_area_layer') or not self.normal_area_layer.isValid():
                project_crs = QgsProject.instance().crs()
                self.normal_area_layer = QgsVectorLayer(f"Polygon?crs={project_crs.authid()}", "Normal Area Sources",
                                                        "memory")
                self.normal_area_layer.dataProvider().addAttributes([
                    QgsField("name", QVariant.String),
                    QgsField("emission_rate", QVariant.Double),
                    QgsField("rheight", QVariant.Double),
                    QgsField("iheight", QVariant.Double),
                    QgsField("CRS", QVariant.String)
                ])
                self.normal_area_layer.updateFields()
                symbol = QgsSymbol.defaultSymbol(self.normal_area_layer.geometryType())
                fill = QgsSimpleFillSymbolLayer()
                fill.setFillColor(QColor(0, 255, 0, 127))
                fill.setStrokeColor(QColor(0, 255, 0))
                fill.setStrokeWidth(0.5)
                symbol.changeSymbolLayer(0, fill)
                self.normal_area_layer.renderer().setSymbol(symbol)
                QgsProject.instance().addMapLayer(self.normal_area_layer)

            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPolygonXY([vertices]))
            feature.setAttributes([name, rate, rheight, iheight, crs_name])
            self.normal_area_layer.startEditing()
            self.normal_area_layer.addFeature(feature)
            self.normal_area_layer.commitChanges()
            self.normal_area_layer.triggerRepaint()
        except ValueError as e:
            print(f"Error for normal area source {index + 1}: {str(e)}")

    def capture_urban_area_source(self, index):
        canvas = iface.mapCanvas()
        entry = self.urban_area_source_entries[index]
        vertex_count = len(entry["vertices"])

        def set_coords(points):
            for j, point in enumerate(points):
                northing_entry, easting_entry = entry["vertices"][j]
                easting, northing = point.x(), point.y()
                easting_entry.setText(f"{easting:.4f}")
                northing_entry.setText(f"{northing:.4f}")

        tool = self.MultiPointMapTool(canvas, set_coords, vertex_count)
        canvas.setMapTool(tool)

    def visualize_urban_area_source(self, index):
        try:
            entry = self.urban_area_source_entries[index]
            name = entry["name_entry"].text() or None
            area = entry["area_entry"].text() or None
            rate_text = entry["rate_entry"].text()
            rheight_text = entry["rheight_entry"].text()
            iheight_text = entry["iheight_entry"].text()

            rate = float(rate_text) if rate_text else None
            rheight = float(rheight_text) if rheight_text else None
            iheight = float(iheight_text) if iheight_text else None

            vertices = []
            for northing_entry, easting_entry in entry["vertices"]:
                easting_text = easting_entry.text()
                northing_text = northing_entry.text()
                easting = float(easting_text) if easting_text else None
                northing = float(northing_text) if northing_text else None
                if easting is None or northing is None:
                    raise ValueError(f"Vertex {len(vertices) + 1} missing coordinates")
                vertices.append(QgsPointXY(easting, northing))
            vertices.append(vertices[0])

            crs_name = QgsProject.instance().crs().description() or None

            if not hasattr(self, 'urban_area_layer') or not self.urban_area_layer.isValid():
                project_crs = QgsProject.instance().crs()
                self.urban_area_layer = QgsVectorLayer(f"Polygon?crs={project_crs.authid()}", "Urban Area Sources",
                                                       "memory")
                self.urban_area_layer.dataProvider().addAttributes([
                    QgsField("name", QVariant.String),
                    QgsField("urban_area", QVariant.String),
                    QgsField("emission_rate", QVariant.Double),
                    QgsField("rheight", QVariant.Double),
                    QgsField("iheight", QVariant.Double),
                    QgsField("CRS", QVariant.String)
                ])
                self.urban_area_layer.updateFields()
                symbol = QgsSymbol.defaultSymbol(self.urban_area_layer.geometryType())
                fill = QgsSimpleFillSymbolLayer()
                fill.setFillColor(QColor(255, 0, 255, 127))
                fill.setStrokeColor(QColor(255, 0, 255))
                fill.setStrokeWidth(0.5)
                symbol.changeSymbolLayer(0, fill)
                self.urban_area_layer.renderer().setSymbol(symbol)
                QgsProject.instance().addMapLayer(self.urban_area_layer)

            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPolygonXY([vertices]))
            feature.setAttributes([name, area, rate, rheight, iheight, crs_name])
            self.urban_area_layer.startEditing()
            self.urban_area_layer.addFeature(feature)
            self.urban_area_layer.commitChanges()
            self.urban_area_layer.triggerRepaint()
        except ValueError as e:
            print(f"Error for urban area source {index + 1}: {str(e)}")

    def capture_normal_volume_source(self, index):
        canvas = iface.mapCanvas()
        tool = QgsMapToolEmitPoint(canvas)

        def on_point_clicked(point):
            easting, northing = point.x(), point.y()
            self.normal_volume_source_entries[index][2].setText(f"{easting:.4f}")
            self.normal_volume_source_entries[index][1].setText(f"{northing:.4f}")
            canvas.unsetMapTool(tool)

        tool.canvasClicked.connect(on_point_clicked)
        canvas.setMapTool(tool)

    def visualize_normal_volume_source(self, index):
        try:
            name = self.normal_volume_source_entries[index][0].text() or None
            northing_text = self.normal_volume_source_entries[index][1].text()
            easting_text = self.normal_volume_source_entries[index][2].text()
            vlemis_text = self.normal_volume_source_entries[index][3].text()
            relhgt_text = self.normal_volume_source_entries[index][4].text()
            syinit_text = self.normal_volume_source_entries[index][5].text()
            szinit_text = self.normal_volume_source_entries[index][6].text()

            easting = float(easting_text) if easting_text else None
            northing = float(northing_text) if northing_text else None
            vlemis = float(vlemis_text) if vlemis_text else None
            relhgt = float(relhgt_text) if relhgt_text else None
            syinit = float(syinit_text) if syinit_text else None
            szinit = float(szinit_text) if szinit_text else None

            if easting is None or northing is None:
                raise ValueError("Easting and Northing are required for visualization")
            if syinit is None:
                syinit = 1.0
                self.normal_volume_source_entries[index][5].setText("1.0")

            crs_name = QgsProject.instance().crs().description() or None

            if not hasattr(self, 'normal_volume_layer') or not self.normal_volume_layer.isValid():
                project_crs = QgsProject.instance().crs()
                self.normal_volume_layer = QgsVectorLayer(f"Polygon?crs={project_crs.authid()}",
                                                          "Normal Volume Sources", "memory")
                self.normal_volume_layer.dataProvider().addAttributes([
                    QgsField("name", QVariant.String),
                    QgsField("easting", QVariant.Double),
                    QgsField("northing", QVariant.Double),
                    QgsField("emission_rate", QVariant.Double),
                    QgsField("relhgt", QVariant.Double),
                    QgsField("syinit", QVariant.Double),
                    QgsField("szinit", QVariant.Double),
                    QgsField("CRS", QVariant.String)
                ])
                self.normal_volume_layer.updateFields()
                symbol = QgsSymbol.defaultSymbol(self.normal_volume_layer.geometryType())
                fill = QgsSimpleFillSymbolLayer()
                fill.setFillColor(QColor(0, 0, 255, 127))
                fill.setStrokeColor(QColor(0, 0, 255))
                fill.setStrokeWidth(0.5)
                symbol.changeSymbolLayer(0, fill)
                self.normal_volume_layer.renderer().setSymbol(symbol)
                QgsProject.instance().addMapLayer(self.normal_volume_layer)

            radius = syinit / 2.0
            points = []
            num_points = 32
            for i in range(num_points):
                angle = 2 * math.pi * i / num_points
                x = easting + radius * math.cos(angle)
                y = northing + radius * math.sin(angle)
                points.append(QgsPointXY(x, y))
            points.append(points[0])
            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPolygonXY([points]))
            feature.setAttributes([name, easting, northing, vlemis, relhgt, syinit, szinit, crs_name])
            self.normal_volume_layer.startEditing()
            self.normal_volume_layer.addFeature(feature)
            self.normal_volume_layer.commitChanges()
            self.normal_volume_layer.triggerRepaint()

            if not hasattr(self, 'normal_volume_center_layer') or not self.normal_volume_center_layer.isValid():
                project_crs = QgsProject.instance().crs()
                self.normal_volume_center_layer = QgsVectorLayer(f"Point?crs={project_crs.authid()}",
                                                                 "Normal Volume Centers", "memory")
                self.normal_volume_center_layer.dataProvider().addAttributes([
                    QgsField("name", QVariant.String),
                    QgsField("easting", QVariant.Double),
                    QgsField("northing", QVariant.Double),
                    QgsField("crs", QVariant.String)
                ])
                self.normal_volume_center_layer.updateFields()
                symbol = QgsSymbol.defaultSymbol(self.normal_volume_center_layer.geometryType())
                symbol.setSize(2.0)
                symbol.setColor(QColor(255, 0, 0))
                self.normal_volume_center_layer.renderer().setSymbol(symbol)
                QgsProject.instance().addMapLayer(self.normal_volume_center_layer)

            center_feature = QgsFeature()
            center_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(easting, northing)))
            center_feature.setAttributes([name, easting, northing, crs_name])
            self.normal_volume_center_layer.startEditing()
            self.normal_volume_center_layer.addFeature(center_feature)
            self.normal_volume_center_layer.commitChanges()
            self.normal_volume_center_layer.triggerRepaint()
        except ValueError as e:
            print(f"Error for normal volume source {index + 1}: {str(e)}")

    def capture_urban_volume_source(self, index):
        canvas = iface.mapCanvas()
        tool = QgsMapToolEmitPoint(canvas)

        def on_point_clicked(point):
            easting, northing = point.x(), point.y()
            self.urban_volume_source_entries[index][3].setText(f"{easting:.4f}")
            self.urban_volume_source_entries[index][2].setText(f"{northing:.4f}")
            canvas.unsetMapTool(tool)

        tool.canvasClicked.connect(on_point_clicked)
        canvas.setMapTool(tool)

    def visualize_urban_volume_source(self, index):
        try:
            name = self.urban_volume_source_entries[index][0].text() or None
            area = self.urban_volume_source_entries[index][1].text() or None
            northing_text = self.urban_volume_source_entries[index][2].text()
            easting_text = self.urban_volume_source_entries[index][3].text()
            vlemis_text = self.urban_volume_source_entries[index][4].text()
            relhgt_text = self.urban_volume_source_entries[index][5].text()
            syinit_text = self.urban_volume_source_entries[index][6].text()
            szinit_text = self.urban_volume_source_entries[index][7].text()

            easting = float(easting_text) if easting_text else None
            northing = float(northing_text) if northing_text else None
            vlemis = float(vlemis_text) if vlemis_text else None
            relhgt = float(relhgt_text) if relhgt_text else None
            syinit = float(syinit_text) if syinit_text else None
            szinit = float(szinit_text) if szinit_text else None

            if easting is None or northing is None:
                raise ValueError("Easting and Northing are required for visualization")
            if syinit is None:
                syinit = 1.0
                self.urban_volume_source_entries[index][6].setText("1.0")

            crs_name = QgsProject.instance().crs().description() or None

            if not hasattr(self, 'urban_volume_layer') or not self.urban_volume_layer.isValid():
                project_crs = QgsProject.instance().crs()
                self.urban_volume_layer = QgsVectorLayer(f"Polygon?crs={project_crs.authid()}", "Urban Volume Sources",
                                                         "memory")
                self.urban_volume_layer.dataProvider().addAttributes([
                    QgsField("name", QVariant.String),
                    QgsField("area", QVariant.String),
                    QgsField("easting", QVariant.Double),
                    QgsField("northing", QVariant.Double),
                    QgsField("emission_rate", QVariant.Double),
                    QgsField("relhgt", QVariant.Double),
                    QgsField("syinit", QVariant.Double),
                    QgsField("szinit", QVariant.Double),
                    QgsField("CRS", QVariant.String)
                ])
                self.urban_volume_layer.updateFields()
                symbol = QgsSymbol.defaultSymbol(self.urban_volume_layer.geometryType())
                fill = QgsSimpleFillSymbolLayer()
                fill.setFillColor(QColor(255, 165, 0, 127))
                fill.setStrokeColor(QColor(255, 165, 0))
                fill.setStrokeWidth(0.5)
                symbol.changeSymbolLayer(0, fill)
                self.urban_volume_layer.renderer().setSymbol(symbol)
                QgsProject.instance().addMapLayer(self.urban_volume_layer)

            radius = syinit / 2.0
            points = []
            num_points = 32
            for i in range(num_points):
                angle = 2 * math.pi * i / num_points
                x = easting + radius * math.cos(angle)
                y = northing + radius * math.sin(angle)
                points.append(QgsPointXY(x, y))
            points.append(points[0])
            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPolygonXY([points]))
            feature.setAttributes([name, area, easting, northing, vlemis, relhgt, syinit, szinit, crs_name])
            self.urban_volume_layer.startEditing()
            self.urban_volume_layer.addFeature(feature)
            self.urban_volume_layer.commitChanges()
            self.urban_volume_layer.triggerRepaint()

            if not hasattr(self, 'urban_volume_center_layer') or not self.urban_volume_center_layer.isValid():
                project_crs = QgsProject.instance().crs()
                self.urban_volume_center_layer = QgsVectorLayer(f"Point?crs={project_crs.authid()}",
                                                                "Urban Volume Centers", "memory")
                self.urban_volume_center_layer.dataProvider().addAttributes([
                    QgsField("name", QVariant.String),
                    QgsField("area", QVariant.String),
                    QgsField("easting", QVariant.Double),
                    QgsField("northing", QVariant.Double),
                    QgsField("crs", QVariant.String)
                ])
                self.urban_volume_center_layer.updateFields()
                symbol = QgsSymbol.defaultSymbol(self.urban_volume_center_layer.geometryType())
                symbol.setSize(2.0)
                symbol.setColor(QColor(0, 255, 0))
                self.urban_volume_center_layer.renderer().setSymbol(symbol)
                QgsProject.instance().addMapLayer(self.urban_volume_center_layer)

            center_feature = QgsFeature()
            center_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(easting, northing)))
            center_feature.setAttributes([name, area, easting, northing, crs_name])
            self.urban_volume_center_layer.startEditing()
            self.urban_volume_center_layer.addFeature(center_feature)
            self.urban_volume_center_layer.commitChanges()
            self.urban_volume_center_layer.triggerRepaint()
        except ValueError as e:
            print(f"Error for urban volume source {index + 1}: {str(e)}")

class SourceTypeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select AERMOD Source Types")
        self.setGeometry(500, 300, 220, 280)
        self.point_normal_entry = None
        self.point_urban_entry = None
        self.line_normal_entry = None
        self.line_urban_entry = None
        self.area_normal_entry = None
        self.area_urban_entry = None
        self.volume_normal_entry = None
        self.volume_urban_entry = None
        self.groups_normal_entry = None
        self.urban_areas_entry = None
        self.avg_entry = None
        self.ok_button = None
        self.aermod_app = None

        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        avg_row = QHBoxLayout()
        avg_label = QLabel("N° of Averaging periods:")
        self.avg_entry = QLineEdit()
        avg_row.addWidget(avg_label)
        avg_row.addWidget(self.avg_entry)
        layout.addLayout(avg_row)

        groups_row = QHBoxLayout()
        groups_label = QLabel("N° Groups                      :")
        self.groups_normal_entry = QLineEdit()
        groups_row.addWidget(groups_label)
        groups_row.addWidget(self.groups_normal_entry)
        groups_row.addStretch()
        layout.addLayout(groups_row)

        urban_areas_row = QHBoxLayout()
        urban_areas_label = QLabel("N° of Urban Areas         :")
        self.urban_areas_entry = QLineEdit()
        urban_areas_row.addWidget(urban_areas_label)
        urban_areas_row.addWidget(self.urban_areas_entry)
        urban_areas_row.addStretch()
        layout.addLayout(urban_areas_row)

        header_row = QHBoxLayout()
        header_row.addWidget(QLabel("Source types:"))
        header_row.addWidget(QLabel("  Normal"))
        header_row.addWidget(QLabel("           Urban"))
        header_row.addStretch()
        layout.addLayout(header_row)

        point_row = QHBoxLayout()
        point_label = QLabel("N° Point    :")
        self.point_normal_entry = QLineEdit()
        self.point_urban_entry = QLineEdit()
        point_row.addWidget(point_label)
        point_row.addWidget(self.point_normal_entry)
        point_row.addWidget(self.point_urban_entry)
        layout.addLayout(point_row)

        line_row = QHBoxLayout()
        line_label = QLabel("N° Line     :")
        self.line_normal_entry = QLineEdit()
        self.line_urban_entry = QLineEdit()
        line_row.addWidget(line_label)
        line_row.addWidget(self.line_normal_entry)
        line_row.addWidget(self.line_urban_entry)
        layout.addLayout(line_row)

        area_row = QHBoxLayout()
        area_label = QLabel("N° Polygon:")
        self.area_normal_entry = QLineEdit()
        self.area_urban_entry = QLineEdit()
        area_row.addWidget(area_label)
        area_row.addWidget(self.area_normal_entry)
        area_row.addWidget(self.area_urban_entry)
        layout.addLayout(area_row)

        volume_row = QHBoxLayout()
        volume_label = QLabel("N° Volume:")
        self.volume_normal_entry = QLineEdit()
        self.volume_urban_entry = QLineEdit()
        volume_row.addWidget(volume_label)
        volume_row.addWidget(self.volume_normal_entry)
        volume_row.addWidget(self.volume_urban_entry)
        layout.addLayout(volume_row)


        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.on_ok_clicked)
        layout.addWidget(self.ok_button)

        self.setLayout(layout)

    def on_ok_clicked(self):
        try:
            avg = self.avg_entry.text().strip()
            if not avg.isdigit() or int(avg) < 0:
                QMessageBox.warning(self, "Invalid Input",
                                    "Number of Averaging periods must be a non-negative integer.")
                return

            def get_value(entry):
                text = entry.text().strip()
                return text if text.isdigit() else "0"

            point_n = get_value(self.point_normal_entry)
            point_u = get_value(self.point_urban_entry)
            line_n = get_value(self.line_normal_entry)
            line_u = get_value(self.line_urban_entry)
            area_n = get_value(self.area_normal_entry)
            area_u = get_value(self.area_urban_entry)
            volume_n = get_value(self.volume_normal_entry)
            volume_u = get_value(self.volume_urban_entry)
            groups = get_value(self.groups_normal_entry)
            urban_areas = get_value(self.urban_areas_entry)

            output = (
                f"AVG {avg}\n"
                f"POINT {point_n} {point_u}\n"
                f"LINE {line_n} {line_u}\n"
                f"AREA {area_n} {area_u}\n"
                f"VOLUME {volume_n} {volume_u}\n"
                f"GROUPS {groups}\n"
                f"URBAN_AREAS {urban_areas}"
            )

            print(f"Current working directory: {os.getcwd()}")
            with open("AERMOD_def.txt", "w") as file:
                file.write(output)
            print(f"AERMOD_def.txt written to: {os.getcwd()}")

            self.accept()
            if int(area_n) == 0 and int(area_u) == 0:
                self.accept()  # Close dialog
                self.launch_aermod_app()
            else:
                polygon_dialog = PolygonDialog(self, int(area_n), int(area_u))
                if polygon_dialog.exec_() == QDialog.Accepted:
                    self.accept()
                    self.launch_aermod_app()

        except Exception as e:
            print(f"Exception in on_ok_clicked: {str(e)}")
            iface.messageBar().pushMessage("Error", f"Failed to process OK click: {str(e)}", level=3)

    def launch_aermod_app(self):
        aermod_app = AERMODApp(self.parent())
        if aermod_app is None:
            raise ValueError("AERMODApp initialization returned None")
        print("Launching AERMODApp")
        aermod_app.show()
        print("AERMODApp shown")


class PolygonDialog(QDialog):
    def __init__(self, parent=None, normal_count=0, urban_count=0):
        super().__init__(parent)
        self.setWindowTitle("Specify Area Polygon Vertices")
        self.setGeometry(250, 250, 400, 200)
        self.normal_count = normal_count
        self.urban_count = urban_count
        self.normal_entries = []
        self.urban_entries = []
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        if self.normal_count > 0:
            layout.addWidget(QLabel("NORMAL AREA POLYGON SOURCES"))
            normal_row = QHBoxLayout()
            for i in range(self.normal_count):
                entry = QLineEdit()
                entry.setPlaceholderText(f"Vertices for NAREA{i + 1}")
                entry.setFixedWidth(100)
                normal_row.addWidget(entry)
                self.normal_entries.append(entry)
            layout.addLayout(normal_row)

        if self.urban_count > 0:
            layout.addWidget(QLabel("URBAN AREA POLYGON SOURCES"))
            urban_row = QHBoxLayout()
            for i in range(self.urban_count):
                entry = QLineEdit()
                entry.setPlaceholderText(f"Vertices for UAREA{i + 1}")
                entry.setFixedWidth(100)
                urban_row.addWidget(entry)
                self.urban_entries.append(entry)
            layout.addLayout(urban_row)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.on_ok_clicked)
        layout.addWidget(ok_button)

        self.setLayout(layout)

    def on_ok_clicked(self):
        try:
            normal_vertices = []
            for i, entry in enumerate(self.normal_entries):
                value = entry.text().strip()
                if not value.isdigit() or int(value) < 3:
                    QMessageBox.warning(self, "Invalid Input", f"NAREA{i + 1} must have at least 3 vertices.")
                    return
                normal_vertices.append(int(value))

            urban_vertices = []
            for i, entry in enumerate(self.urban_entries):
                value = entry.text().strip()
                if not value.isdigit() or int(value) < 3:
                    QMessageBox.warning(self, "Invalid Input", f"UAREA{i + 1} must have at least 3 vertices.")
                    return
                urban_vertices.append(int(value))

            with open("AREA_def.txt", "w") as file:
                for i, n in enumerate(normal_vertices, 1):
                    file.write(f"NAREA{i} {n}\n")
                for i, n in enumerate(urban_vertices, 1):
                    file.write(f"UAREA{i} {n}\n")

            self.accept()  # Close dialog

        except Exception as e:
            print(f"Error in PolygonDialog: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to save AREA_def.txt: {str(e)}")


class AERPLOTApp(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plugin_dir = os.path.dirname(__file__)
        self.datafile_entries = []
        self.group_widgets = []
        self.version_entry = None
        self.initUI()

    def read_aerplot_def(self):
        try:
            with open("AERPLOT_def.txt", "r") as file:
                lines = file.readlines()
            for line in lines:
                parts = line.strip().split()
                if parts[0] == "GROUPS":
                    return int(parts[1])
            return 0
        except (FileNotFoundError, ValueError, IndexError) as e:
            iface.messageBar().pushMessage("Error", f"Failed to read AERPLOT_def.txt: {str(e)}", level=2)
            return 0

    def initUI(self):
        self.setWindowTitle("CAIRO © ~ AERPLOT Input File Generator")
        num_groups = self.read_aerplot_def()
        self.setGeometry(100, 100, max(600, 300 * num_groups), 800)

        central_widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidget(central_widget)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setCentralWidget(scroll)

        layout = QGridLayout()
        central_widget.setLayout(layout)

        icon_label = QLabel()
        try:
            icon_pixmap = QPixmap(os.path.join(self.plugin_dir, "CAIRO.png"))
            icon_label.setPixmap(icon_pixmap)
        except Exception as e:
            print(f"Error loading icon: {e}")
        icon_label.setAlignment(Qt.AlignCenter)

        text_label = QLabel("AERPLOT Input File Generator ©\nCAIRO © for AERMOD, 2025.\nMSc "
                            "Dominik Subotić @UNIVMP\n\n\n\n\n")
        text_label.setFont(QFont('Arial', 8))
        text_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(icon_label, 0, 0)
        layout.addWidget(text_label, 0, 2, 1, num_groups * 2 - 1)

        compile_button = QPushButton("Compile 📝")
        compile_button.clicked.connect(self.compile_output)
        compile_button.setFont(QFont('Serif', 10))
        layout.addWidget(compile_button, 0, 1, 3, num_groups * 2 - 1)
        self.setTooltip(compile_button, "Choose folder that includes AERMOD outputs")

        for group_idx in range(num_groups):
            col_base = group_idx * 2
            group_dict = {}

            if group_idx == 0:
                version_label = QLabel("Version")
                version_label.setFont(QFont('Arial', 8))
                self.version_entry = QLineEdit("2")
                self.version_entry.setFont(QFont('Arial', 8))
                layout.addWidget(version_label, 1, col_base)
                layout.addWidget(self.version_entry, 1, col_base + 1)
                self.setTooltip(version_label, "Default=2, AERPLOT version number")

            group_name_label = QLabel(f"Group {group_idx + 1}")
            group_name_label.setFont(QFont('Arial', 8))
            group_name_entry = QLineEdit()
            group_name_entry.setFont(QFont('Arial', 8))
            layout.addWidget(group_name_label, 2, col_base)
            layout.addWidget(group_name_entry, 2, col_base + 1)
            self.setTooltip(group_name_label, "Group name needed to define plotfile name")
            group_dict["group_name_entry"] = group_name_entry

            utm_label = QLabel("UTM zone")
            utm_label.setFont(QFont('Arial', 8))
            utm_entry = QLineEdit()
            utm_entry.setFont(QFont('Arial', 8))
            layout.addWidget(utm_label, 3, col_base)
            layout.addWidget(utm_entry, 3, col_base + 1)
            group_dict["utm_entry"] = utm_entry

            hemisphere_label = QLabel("Hemisphere")
            hemisphere_label.setFont(QFont('Arial', 8))
            hemisphere_combo = QComboBox()
            hemisphere_combo.addItems(["inNorthernHemisphere", "inSouthernHemisphere"])
            hemisphere_combo.setCurrentText("inNorthernHemisphere")
            hemisphere_combo.setFont(QFont('Arial', 8))
            layout.addWidget(hemisphere_label, 4, col_base)
            layout.addWidget(hemisphere_combo, 4, col_base + 1)
            group_dict["hemisphere_combo"] = hemisphere_combo

            altitude_choice_label = QLabel("Altitude Choice")
            altitude_choice_label.setFont(QFont('Arial', 8))
            altitude_choice_combo = QComboBox()
            altitude_choice_combo.addItems(["relativeToGround", "absolute", "flagpole"])
            altitude_choice_combo.setCurrentText("relativeToGround")
            altitude_choice_combo.setFont(QFont('Arial', 8))
            layout.addWidget(altitude_choice_label, 5, col_base)
            layout.addWidget(altitude_choice_combo, 5, col_base + 1)
            self.setTooltip(altitude_choice_label, "Altitude reference: relativeToGround, absolute, or flagpole")
            group_dict["altitude_choice_combo"] = altitude_choice_combo

            altitude_label = QLabel("Altitude")
            altitude_label.setFont(QFont('Arial', 8))
            altitude_entry = QLineEdit("0")
            altitude_entry.setFont(QFont('Arial', 8))
            layout.addWidget(altitude_label, 6, col_base)
            layout.addWidget(altitude_entry, 6, col_base + 1)
            self.setTooltip(altitude_label, "Altitude value (default 0), editable")
            group_dict["altitude_entry"] = altitude_entry

            avg_frame = QFrame()
            avg_layout = QVBoxLayout()
            avg_frame.setLayout(avg_layout)

            add_avg_button = QPushButton("Add Averaging Period")
            add_avg_button.setFont(QFont('Arial', 8))
            add_avg_button.clicked.connect(lambda _, idx=group_idx: self.add_averaging_period(idx))
            avg_layout.addWidget(add_avg_button)
            self.setTooltip(add_avg_button, "Add a new averaging period for this group")

            group_dict["avg_layout"] = avg_layout
            group_dict["time_entries"] = []
            layout.addWidget(avg_frame, 7, col_base, 1, 2)

            min_bin_label = QLabel("Minimum Bin")
            min_bin_label.setFont(QFont('Arial', 8))
            min_bin_entry = QLineEdit("data")
            min_bin_entry.setFont(QFont('Arial', 8))
            layout.addWidget(min_bin_label, 8, col_base)
            layout.addWidget(min_bin_entry, 8, col_base + 1)
            self.setTooltip(min_bin_label, "Input format = .5e-9; for defaulting to data range = data")
            group_dict["min_bin_entry"] = min_bin_entry

            max_bin_label = QLabel("Maximum Bin")
            max_bin_label.setFont(QFont('Arial', 8))
            max_bin_entry = QLineEdit("data")
            max_bin_entry.setFont(QFont('Arial', 8))
            layout.addWidget(max_bin_label, 9, col_base)
            layout.addWidget(max_bin_entry, 9, col_base + 1)
            self.setTooltip(max_bin_label, "Input format = .5e-9; for defaulting to data range = data")
            group_dict["max_bin_entry"] = max_bin_entry

            binning_label = QLabel("Binning Method")
            binning_label.setFont(QFont('Arial', 8))
            binning_combo = QComboBox()
            binning_combo.addItems(["Linear", "Log"])
            binning_combo.setFont(QFont('Arial', 8))
            layout.addWidget(binning_label, 10, col_base)
            layout.addWidget(binning_combo, 10, col_base + 1)
            group_dict["binning_combo"] = binning_combo

            icon_set_label = QLabel("Color Gradient")
            icon_set_label.setFont(QFont('Arial', 8))
            icon_set_combo = QComboBox()
            icon_set_combo.addItems(["redBlue", "redGreen"])
            icon_set_combo.setCurrentText("redBlue")
            icon_set_combo.setFont(QFont('Arial', 8))
            layout.addWidget(icon_set_label, 11, col_base)
            layout.addWidget(icon_set_combo, 11, col_base + 1)
            self.setTooltip(icon_set_label, "Color scheme for icons: redBlue or redGreen")
            group_dict["icon_set_combo"] = icon_set_combo

            custom_bin_label = QLabel("Custom Binning Levels")
            custom_bin_label.setFont(QFont('Arial', 8))
            custom_bin_entry = QLineEdit("na")
            custom_bin_entry.setFont(QFont('Arial', 8))
            layout.addWidget(custom_bin_label, 12, col_base)
            layout.addWidget(custom_bin_entry, 12, col_base + 1)
            self.setTooltip(custom_bin_label, "Custom binning levels (default 'na'), editable")
            group_dict["custom_bin_entry"] = custom_bin_entry

            gridcols_label = QLabel("N° Grid Columns")
            gridcols_label.setFont(QFont('Arial', 8))
            gridcols_entry = QLineEdit("400")
            gridcols_entry.setFont(QFont('Arial', 8))
            layout.addWidget(gridcols_label, 13, col_base)
            layout.addWidget(gridcols_entry, 13, col_base + 1)
            self.setTooltip(gridcols_label, "Default is 400, increase for larger datasets")
            group_dict["gridcols_entry"] = gridcols_entry

            gridrows_label = QLabel("N° Grid Rows")
            gridrows_label.setFont(QFont('Arial', 8))
            gridrows_entry = QLineEdit("400")
            gridrows_entry.setFont(QFont('Arial', 8))
            layout.addWidget(gridrows_label, 14, col_base)
            layout.addWidget(gridrows_entry, 14, col_base + 1)
            self.setTooltip(gridrows_label, "Default is 400, increase for larger datasets")
            group_dict["gridrows_entry"] = gridrows_entry

            smooth_label = QLabel("N° Smoothing Iterations")
            smooth_label.setFont(QFont('Arial', 8))
            smooth_entry = QLineEdit("1")
            smooth_entry.setFont(QFont('Arial', 8))
            layout.addWidget(smooth_label, 15, col_base)
            layout.addWidget(smooth_entry, 15, col_base + 1)
            self.setTooltip(smooth_label, "Default is 1, larger values distort exact locations")
            group_dict["smooth_entry"] = smooth_entry

            contour_label = QLabel("Create Contours")
            contour_label.setFont(QFont('Arial', 8))
            contour_combo = QComboBox()
            contour_combo.addItems(["true", "false"])
            contour_combo.setFont(QFont('Arial', 8))
            layout.addWidget(contour_label, 16, col_base)
            layout.addWidget(contour_combo, 16, col_base + 1)
            group_dict["contour_combo"] = contour_combo

            gradient_label = QLabel("Create Gradient")
            gradient_label.setFont(QFont('Arial', 8))
            gradient_combo = QComboBox()
            gradient_combo.addItems(["true", "false"])
            gradient_combo.setFont(QFont('Arial', 8))
            layout.addWidget(gradient_label, 17, col_base)
            layout.addWidget(gradient_combo, 17, col_base + 1)
            group_dict["gradient_combo"] = gradient_combo

            grad_binning_label = QLabel("Gradient Binning Method")
            grad_binning_label.setFont(QFont('Arial', 8))
            grad_binning_combo = QComboBox()
            grad_binning_combo.addItems(["Linear", "Log"])
            grad_binning_combo.setFont(QFont('Arial', 8))
            layout.addWidget(grad_binning_label, 18, col_base)
            layout.addWidget(grad_binning_combo, 18, col_base + 1)
            group_dict["grad_binning_combo"] = grad_binning_combo

            interpolated_grid_label = QLabel("Interpolated Grid")
            interpolated_grid_label.setFont(QFont('Arial', 8))
            interpolated_grid_combo = QComboBox()
            interpolated_grid_combo.addItems(["false", "true"])
            interpolated_grid_combo.setCurrentText("false")
            interpolated_grid_combo.setFont(QFont('Arial', 8))
            layout.addWidget(interpolated_grid_label, 19, col_base)
            layout.addWidget(interpolated_grid_combo, 19, col_base + 1)
            self.setTooltip(interpolated_grid_label, "Provide evenly spaced interpolated grid: true or false")
            group_dict["interpolated_grid_combo"] = interpolated_grid_combo

            self.group_widgets.append(group_dict)

    def setTooltip(self, widget, text):
        widget.setToolTip(text)

    def add_averaging_period(self, group_idx):
        group_dict = self.group_widgets[group_idx]
        avg_layout = group_dict["avg_layout"]

        time_widget = QWidget()
        time_layout = QGridLayout()
        time_widget.setLayout(time_layout)

        time_label = QLabel(f"Avg. Period {len(group_dict['time_entries']) + 1}(h):")
        time_label.setFont(QFont('Arial', 8))
        time_entry = QLineEdit()
        time_entry.setFont(QFont('Arial', 8))
        time_layout.addWidget(time_label, 0, 0)
        time_layout.addWidget(time_entry, 0, 1)
        self.setTooltip(time_label, "Must be identical to period stated in Aermod input")

        avg_layout.addWidget(time_widget)
        group_dict["time_entries"].append(time_entry)

    def compile_output(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if not folder_path:
            return

        try:
            for group_idx, group_dict in enumerate(self.group_widgets):
                group_name = group_dict["group_name_entry"].text().strip() or f"Group{group_idx + 1}"
                for period_idx, time_entry in enumerate(group_dict["time_entries"]):
                    period = time_entry.text().strip()
                    if not period:
                        continue

                    subfolder_name = f"aerplot_{group_name}_{period}"
                    subfolder_path = os.path.join(folder_path, subfolder_name)
                    os.makedirs(subfolder_path, exist_ok=True)

                    plot_filename = ""
                    if group_dict["group_name_entry"].text():
                        period_upper = period.upper()
                        suffix = "" if period_upper in ["MONTH", "ANNUAL", "PERIOD"] else "H"
                        plot_filename = f"PLOT{period}{suffix}_{group_dict['group_name_entry'].text()}.PLT"

                    output_text_content = (
                        f"version={self.version_entry.text()}\n"
                        "origin=UTM\n"
                        "easting=0\n"
                        "northing=0\n"
                        f"utmZone={group_dict['utm_entry'].text()}\n"
                        f"{group_dict['hemisphere_combo'].currentText()}=true\n"
                        "originLatitude =0\n"
                        "originLongitude =0\n"
                        f"altitudeChoice = {group_dict['altitude_choice_combo'].currentText()}\n"
                        f"altitude={group_dict['altitude_entry'].text()}\n"
                        f"PlotFileName ={plot_filename}\n"
                        "SourceDisplayInputFileName=aermod.inp\n"
                        f"OutputFileNameBase ={plot_filename}\n"
                        f"NameDisplayedInGoogleEarth={plot_filename}\n"
                        "sDisableProgressMeter              = false\n"
                        "sDisableEarthBrowser               = true\n"
                        "IconScale     = 0.40\n"
                        f"sIconSetChoice={group_dict['icon_set_combo'].currentText()}\n"
                        f"minbin={group_dict['min_bin_entry'].text()}\n"
                        f"maxbin={group_dict['max_bin_entry'].text()}\n"
                        f"binningChoice ={group_dict['binning_combo'].currentText()}\n"
                        f"customBinningElevenLevels={group_dict['custom_bin_entry'].text()}\n"
                        "contourLegendTitleHTML =C&nbsp;O&nbsp;N&nbsp;C&nbsp;E&nbsp;N&nbsp;T&nbsp"
                        ";R&nbsp;A&nbsp;T&nbsp;I&nbsp;O&nbsp;N&nbsp;S\n"
                        f"numberOfGridCols                   ={group_dict['gridcols_entry'].text()}\n"
                        f"numberOfGridRows                   ={group_dict['gridrows_entry'].text()}\n"
                        f"numberOfTimesToSmoothContourSurface ={group_dict['smooth_entry'].text()}\n"
                        f"makeContours                        ={group_dict['contour_combo'].currentText()}\n"
                        "contourExtension =  9999999\n"
                        f"makeGradients                       ={group_dict['gradient_combo'].currentText()}\n"
                        "gradientExtension= 9999999\n"
                        f"gradientMaxBin={group_dict['max_bin_entry'].text()}\n"
                        f"gradientMinBin={group_dict['min_bin_entry'].text()}\n"
                        f"gradientBinningChoice={group_dict['grad_binning_combo'].currentText()}\n"
                        "customGradBinElevenLevels=na\n"
                        "gradientLegendTitleHTML=Gradient&nbsp;Magnitudes\n"
                        f"provideEvenlySpacedInterpolatedGrid = {group_dict['interpolated_grid_combo'].currentText()}\n"
                    )

                    with open(os.path.join(subfolder_path, "aerplot.inp"), "w") as f:
                        f.write(output_text_content)

                    for file in ["aermod.inp", "aermod.out"]:
                        src = os.path.join(folder_path, file)
                        if os.path.exists(src):
                            copyfile(src, os.path.join(subfolder_path, file))

                    aerplot_exe_src = os.path.join(self.plugin_dir, "aerplot.exe")
                    if os.path.exists(aerplot_exe_src):
                        copyfile(aerplot_exe_src, os.path.join(subfolder_path, "aerplot.exe"))

                    plot_file = f"PLOT{period}H_{group_name}.PLT"
                    period_upper = period.upper()
                    if period_upper in ["MONTH", "YEAR", "PERIOD"]:
                        plot_file = f"PLOT{period}_{group_name}.PLT"
                    src_plot = os.path.join(folder_path, plot_file)
                    dest_plot = os.path.join(subfolder_path, plot_file)
                    if os.path.exists(src_plot):
                        copyfile(src_plot, dest_plot)

            iface.messageBar().pushMessage("Success", "Files compiled successfully!", level=0)
            self.close()
            try:
                os.startfile(folder_path)
            except Exception as e:
                print(f"Error opening folder: {str(e)}")
        except Exception as e:
            iface.messageBar().pushMessage("Error", f"An error occurred: {str(e)}", level=1)


class GroupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Define AERPLOT Scope")
        self.setGeometry(200, 200, 300, 100)
        self.groups_entry = None
        self.ok_button = None
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        groups_row = QHBoxLayout()
        groups_label = QLabel("Number of Groups:")
        self.groups_entry = QLineEdit()
        groups_row.addWidget(groups_label)
        groups_row.addWidget(self.groups_entry)
        layout.addLayout(groups_row)

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.on_ok_clicked)
        layout.addWidget(self.ok_button)

        self.setLayout(layout)

    def on_ok_clicked(self):
        try:
            groups = self.groups_entry.text().strip()
            if not groups.isdigit() or int(groups) < 0:
                QMessageBox.warning(self, "Invalid Input", "Number of Groups must be a non-negative integer.")
                return

            output = f"GROUPS {groups}"

            with open("AERPLOT_def.txt", "w") as file:
                file.write(output)

            self.accept()
            self.launch_aerplot_app()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save AERPLOT_def.txt: {str(e)}")

    def launch_aerplot_app(self):
        try:
            aerplot_app = AERPLOTApp()
            aerplot_app.show()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to launch AERPLOTApp: {str(e)}")


class ProcessMonitorThread(QThread):
    finished = pyqtSignal(str)

    def __init__(self, process, output_file_path):
        super().__init__()
        self.process = process
        self.output_file_path = output_file_path

    def run(self):
        self.process.waitForFinished()
        if os.path.exists(self.output_file_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_file_path))
            self.finished.emit(self.output_file_path)


class CAIRO:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(self.plugin_dir, 'i18n', 'CAIRO_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        self.actions = []
        self.menu = self.tr(u'&CAIRO for AERMOD')
        self.first_start = None

    def tr(self, message):
        return QCoreApplication.translate('CAIRO', message)

    def add_action(self, icon_path, text, callback, enabled_flag=True, add_to_menu=True, add_to_toolbar=True,
                   status_tip=None, whats_this=None, parent=None):
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(self.menu, action)

        self.actions.append(action)
        return action

    def initGui(self):
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.add_action(
            icon_path,
            text=self.tr(u'CAIRO for AERMOD'),
            callback=self.run,
            parent=self.iface.mainWindow())

        self.first_start = True

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.tr(u'&CAIRO for AERMOD'), action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        from .CAIRO_dialog import CAIRODialog
        if self.first_start:
            self.first_start = False
            self.dlg = CAIRODialog(self.iface.mainWindow())

        self.dlg.show()
        result = self.dlg.exec_()
        if result:
            pass
