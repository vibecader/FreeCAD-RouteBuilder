# FreeCAD-RouteBuilder by VibeCADer
# Copyright (C) 2026 VibeCADer
# Contact: korney92d1@yandex.ru
# SPDX-License-Identifier: LGPL-2.1-or-later

import FreeCAD as App
import FreeCADGui as Gui
import Part
import Sketcher

try:
    from PySide import QtGui, QtCore
except ImportError:
    from PySide6 import QtGui, QtCore


# ============================================================
# Стандартные данные
# ============================================================
PIPE_DATA = {
    "DN15":  {"outer": 21.3,  "walls": [2.5, 2.8, 3.2]},
    "DN20":  {"outer": 26.8,  "walls": [2.5, 2.8, 3.2]},
    "DN25":  {"outer": 33.5,  "walls": [2.8, 3.2, 4.0]},
    "DN32":  {"outer": 42.3,  "walls": [2.8, 3.2, 4.0]},
    "DN40":  {"outer": 48.0,  "walls": [3.0, 3.5, 4.0]},
    "DN50":  {"outer": 60.0,  "walls": [3.0, 3.5, 4.0, 4.5]},
    "DN65":  {"outer": 75.5,  "walls": [3.5, 4.0, 4.5, 5.0]},
    "DN80":  {"outer": 88.5,  "walls": [4.0, 4.5, 5.0, 6.0]},
    "DN100": {"outer": 114.0, "walls": [4.0, 4.5, 5.0, 6.0, 8.0]},
    "DN125": {"outer": 140.0, "walls": [4.5, 5.0, 6.0, 8.0]},
    "DN150": {"outer": 159.0, "walls": [4.5, 5.0, 6.0, 8.0, 10.0]},
    "DN200": {"outer": 219.0, "walls": [5.0, 6.0, 8.0, 10.0, 12.0]},
    "DN250": {"outer": 273.0, "walls": [6.0, 8.0, 10.0, 12.0]},
    "DN300": {"outer": 325.0, "walls": [6.0, 8.0, 10.0, 12.0, 14.0]},
    "DN350": {"outer": 377.0, "walls": [8.0, 10.0, 12.0, 14.0]},
    "DN400": {"outer": 426.0, "walls": [8.0, 10.0, 12.0, 14.0, 16.0]},
    "DN500": {"outer": 530.0, "walls": [8.0, 10.0, 12.0, 14.0, 16.0]},
}

SQUARE_DATA = {
    "20":   [1.5, 2.0],
    "25":   [1.5, 2.0, 2.5],
    "30":   [2.0, 2.5, 3.0],
    "40":   [2.0, 2.5, 3.0, 4.0],
    "50":   [2.5, 3.0, 3.5, 4.0],
    "60":   [3.0, 3.5, 4.0, 5.0],
    "80":   [3.5, 4.0, 5.0, 6.0],
    "100":  [4.0, 5.0, 6.0, 8.0],
}

RECT_DATA = {
    "40x20":   [2.0, 2.5, 3.0],
    "50x25":   [2.0, 2.5, 3.0, 4.0],
    "60x30":   [2.5, 3.0, 4.0],
    "60x40":   [3.0, 4.0],
    "80x40":   [3.0, 4.0, 5.0],
    "100x50":  [3.0, 4.0, 5.0, 6.0],
    "120x60":  [4.0, 5.0, 6.0],
    "140x80":  [4.0, 5.0, 6.0, 8.0],
    "160x80":  [4.0, 5.0, 6.0, 8.0],
    "180x100": [5.0, 6.0, 8.0],
}


# ============================================================
# Диалог
# ============================================================
class PipeDialog(QtGui.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Создать тело по траектории")
        self.setMinimumWidth(360)

        # === Загружаем сохранённые настройки ===
        self.params = App.ParamGet("User parameter:BaseApp/Preferences/Mod/ParametricWire")
        last_profile_idx = self.params.GetInt("LastProfileIndex", 0)
        last_dn = self.params.GetString("LastDN", "DN150")
        last_wall = self.params.GetFloat("LastWall", 5.0)
        last_square_size = self.params.GetFloat("LastSquareSize", 40.0)
        last_square_wall = self.params.GetFloat("LastSquareWall", 3.0)
        last_rect_width = self.params.GetFloat("LastRectWidth", 60.0)
        last_rect_height = self.params.GetFloat("LastRectHeight", 40.0)
        last_rect_wall = self.params.GetFloat("LastRectWall", 3.0)

        layout = QtGui.QVBoxLayout(self)
        layout.addWidget(QtGui.QLabel("Выберите параметры профиля:"))

        # Тип профиля
        type_layout = QtGui.QHBoxLayout()
        type_layout.addWidget(QtGui.QLabel("Профиль:"))
        self.type_combo = QtGui.QComboBox()
        self.type_combo.addItems(["Круг (труба)", "Квадрат", "Прямоугольник"])
        self.type_combo.setCurrentIndex(last_profile_idx)
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)

        # === Круг ===
        self.circle_group = QtGui.QGroupBox("Параметры круга")
        circle_layout = QtGui.QFormLayout(self.circle_group)

        self.dn_combo = QtGui.QComboBox()
        self.dn_combo.addItems(sorted(PIPE_DATA.keys(), key=lambda x: int(x[2:])) + ["Свой размер"])
        if last_dn in PIPE_DATA:
            self.dn_combo.setCurrentText(last_dn)
        else:
            self.dn_combo.setCurrentText("Свой размер")
        self.dn_combo.currentIndexChanged.connect(self.update_circle_walls)
        circle_layout.addRow("DN:", self.dn_combo)

        self.circle_outer = QtGui.QDoubleSpinBox()
        self.circle_outer.setRange(1.0, 5000.0)
        self.circle_outer.setValue(159.0)
        self.circle_outer.setSuffix(" мм")
        circle_layout.addRow("Наружный диаметр:", self.circle_outer)

        self.circle_wall = QtGui.QDoubleSpinBox()
        self.circle_wall.setRange(0.1, 100.0)
        self.circle_wall.setValue(last_wall)
        self.circle_wall.setSuffix(" мм")
        circle_layout.addRow("Толщина стенки:", self.circle_wall)

        layout.addWidget(self.circle_group)

        # === Квадрат ===
        self.square_group = QtGui.QGroupBox("Параметры квадрата")
        square_layout = QtGui.QFormLayout(self.square_group)

        self.square_size_combo = QtGui.QComboBox()
        self.square_size_combo.addItems(sorted(SQUARE_DATA.keys(), key=lambda x: int(x)) + ["Свой размер"])
        self.square_size_combo.currentIndexChanged.connect(self.update_square_walls)
        square_layout.addRow("Сторона:", self.square_size_combo)

        self.square_size = QtGui.QDoubleSpinBox()
        self.square_size.setRange(1.0, 2000.0)
        self.square_size.setValue(last_square_size)
        self.square_size.setSuffix(" мм")
        square_layout.addRow("Сторона (свой):", self.square_size)

        self.square_wall = QtGui.QDoubleSpinBox()
        self.square_wall.setRange(0.1, 100.0)
        self.square_wall.setValue(last_square_wall)
        self.square_wall.setSuffix(" мм")
        square_layout.addRow("Толщина стенки:", self.square_wall)

        layout.addWidget(self.square_group)

        # === Прямоугольник ===
        self.rect_group = QtGui.QGroupBox("Параметры прямоугольника")
        rect_layout = QtGui.QFormLayout(self.rect_group)

        self.rect_size_combo = QtGui.QComboBox()
        self.rect_size_combo.addItems(sorted(RECT_DATA.keys()) + ["Свой размер"])
        self.rect_size_combo.currentIndexChanged.connect(self.update_rect_walls)
        rect_layout.addRow("Размер (ШxВ):", self.rect_size_combo)

        self.rect_width = QtGui.QDoubleSpinBox()
        self.rect_width.setRange(1.0, 2000.0)
        self.rect_width.setValue(last_rect_width)
        self.rect_width.setSuffix(" мм")
        rect_layout.addRow("Ширина:", self.rect_width)

        self.rect_height = QtGui.QDoubleSpinBox()
        self.rect_height.setRange(1.0, 2000.0)
        self.rect_height.setValue(last_rect_height)
        self.rect_height.setSuffix(" мм")
        rect_layout.addRow("Высота:", self.rect_height)

        self.rect_wall = QtGui.QDoubleSpinBox()
        self.rect_wall.setRange(0.1, 100.0)
        self.rect_wall.setValue(last_rect_wall)
        self.rect_wall.setSuffix(" мм")
        rect_layout.addRow("Толщина стенки:", self.rect_wall)

        layout.addWidget(self.rect_group)

        # Кнопки
        buttons = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Первое обновление
        self.on_type_changed()
        self.update_circle_walls()
        self.update_square_walls()
        self.update_rect_walls()

    def save_settings(self):
        """Сохраняет текущие настройки в параметры FreeCAD."""
        self.params.SetInt("LastProfileIndex", self.type_combo.currentIndex())
        self.params.SetString("LastDN", self.dn_combo.currentText())
        self.params.SetFloat("LastWall", self.circle_wall.value())
        self.params.SetFloat("LastSquareSize", self.square_size.value())
        self.params.SetFloat("LastSquareWall", self.square_wall.value())
        self.params.SetFloat("LastRectWidth", self.rect_width.value())
        self.params.SetFloat("LastRectHeight", self.rect_height.value())
        self.params.SetFloat("LastRectWall", self.rect_wall.value())

    def accept(self):
        """Перед закрытием — сохраняем настройки."""
        self.save_settings()
        super().accept()

    def on_type_changed(self):
        idx = self.type_combo.currentIndex()
        self.circle_group.setVisible(idx == 0)
        self.square_group.setVisible(idx == 1)
        self.rect_group.setVisible(idx == 2)
        self.adjustSize()

    def update_circle_walls(self):
        dn = self.dn_combo.currentText()
        if dn in PIPE_DATA:
            self.circle_outer.setValue(PIPE_DATA[dn]["outer"])
            if PIPE_DATA[dn]["walls"]:
                self.circle_wall.setValue(PIPE_DATA[dn]["walls"][0])

    def update_square_walls(self):
        size = self.square_size_combo.currentText()
        if size in SQUARE_DATA:
            self.square_size.setValue(float(size))
            if SQUARE_DATA[size]:
                self.square_wall.setValue(SQUARE_DATA[size][0])

    def update_rect_walls(self):
        size = self.rect_size_combo.currentText()
        if size in RECT_DATA:
            w, h = size.split("x")
            self.rect_width.setValue(float(w))
            self.rect_height.setValue(float(h))
            if RECT_DATA[size]:
                self.rect_wall.setValue(RECT_DATA[size][0])

    def get_result(self):
        idx = self.type_combo.currentIndex()
        if idx == 0:
            return ("circle", {
                "outer": self.circle_outer.value(),
                "wall": self.circle_wall.value(),
            })
        elif idx == 1:
            return ("square", {
                "size": self.square_size.value(),
                "wall": self.square_wall.value(),
            })
        else:
            return ("rect", {
                "width": self.rect_width.value(),
                "height": self.rect_height.value(),
                "wall": self.rect_wall.value(),
            })


# ============================================================
# Создание тела
# ============================================================
def create_pipe_by_trajectory():
    """Создаёт тело по траектории ParametricWire."""
    doc = App.ActiveDocument
    if not doc:
        App.Console.PrintError("Нет активного документа.\n")
        return

    # Ищем все ParametricWire
    wires = [obj for obj in doc.Objects
             if obj.TypeId == "Part::FeaturePython"
             and hasattr(obj, "Spreadsheet")]

    if not wires:
        App.Console.PrintError("В документе нет объектов ParametricWire.\n")
        return

    if len(wires) == 1:
        wire_obj = wires[0]
    else:
        labels = [f"{w.Label} ({w.Name})" for w in wires]
        selected, ok = QtGui.QInputDialog.getItem(
            None, "Выбор траектории", "Выберите ParametricWire:",
            labels, 0, False
        )
        if not ok:
            return
        wire_obj = wires[labels.index(selected)]

    dlg = PipeDialog()
    if dlg.exec_() != QtGui.QDialog.Accepted:
        return

    profile_type, params = dlg.get_result()

    if not wire_obj.Shape or not wire_obj.Shape.Edges:
        App.Console.PrintError("У ParametricWire нет геометрии.\n")
        return

    # === Имя Body ===
    if profile_type == "circle":
        body_name = f"Pipe_DN{int(params['outer'])}x{params['wall']}"
    elif profile_type == "square":
        body_name = f"Box_{int(params['size'])}x{int(params['size'])}x{params['wall']}"
    else:
        body_name = f"Rect_{int(params['width'])}x{int(params['height'])}x{params['wall']}"
    body_name = body_name.replace(".", "_")

    # === Создаём Body ===
    body = doc.addObject("PartDesign::Body", body_name)
    body.Label = body_name

    # === SubShapeBinder ===
    binder = body.newObject("PartDesign::SubShapeBinder", "Trajectory")
    binder.Label = "Trajectory"
    binder.Support = [(wire_obj, "")]
    doc.recompute()

    # === DatumPlane ===
    datum = body.newObject("PartDesign::Plane", "ProfilePlane")
    datum.Label = "Profile Plane"
    datum.MapMode = "NormalToEdge"
    datum.AttachmentSupport = [(binder, "Edge1")]
    doc.recompute()
    datum.ViewObject.Visibility = False

    # === Sketch ===
    sketch = body.newObject("Sketcher::SketchObject", "Profile")
    sketch.Label = "Profile"
    sketch.AttachmentSupport = [(datum, "")]
    sketch.MapMode = "FlatFace"
    doc.recompute()

    # === Рисуем профиль ===
    if profile_type == "circle":
        outer = params["outer"]
        wall = params["wall"]
        inner = outer - 2 * wall
        sketch.addGeometry(
            Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), outer / 2.0), False
        )
        sketch.addGeometry(
            Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), inner / 2.0), False
        )
    elif profile_type == "square":
        size = params["size"]
        wall = params["wall"]
        inner = size - 2 * wall
        _add_rect(sketch, size, size, 0, 0)
        _add_rect(sketch, inner, inner, 0, 0)
    else:
        w = params["width"]
        h = params["height"]
        wall = params["wall"]
        iw = w - 2 * wall
        ih = h - 2 * wall
        _add_rect(sketch, w, h, 0, 0)
        _add_rect(sketch, iw, ih, 0, 0)

    doc.recompute()

    # === AdditivePipe ===
    pipe = body.newObject("PartDesign::AdditivePipe", "Pipe")
    pipe.Label = "Pipe"
    pipe.Profile = sketch
    pipe.Spine = binder
    pipe.Mode = "Standard"
    pipe.Transition = 1
    doc.recompute()

    App.Console.PrintMessage(f"Создано тело: {body_name}\n")


def _add_rect(sketch, width, height, cx, cy):
    """
    Добавляет прямоугольник (или квадрат) из 4 линий
    с ограничениями совпадения концов.
    Центр — в точке (cx, cy).
    """
    hw = width / 2.0
    hh = height / 2.0

    # Четыре угла
    p1 = App.Vector(cx - hw, cy - hh, 0)
    p2 = App.Vector(cx + hw, cy - hh, 0)
    p3 = App.Vector(cx + hw, cy + hh, 0)
    p4 = App.Vector(cx - hw, cy + hh, 0)

    # Запоминаем индекс первой новой линии
    start_idx = sketch.GeometryCount

    # Добавляем 4 линии (по кругу против часовой стрелки)
    sketch.addGeometry(Part.LineSegment(p1, p2), False)  # 0: низ
    sketch.addGeometry(Part.LineSegment(p2, p3), False)  # 1: право
    sketch.addGeometry(Part.LineSegment(p3, p4), False)  # 2: верх
    sketch.addGeometry(Part.LineSegment(p4, p1), False)  # 3: лево

    # Связываем концы линий ограничениями совпадения
    sketch.addConstraint(Sketcher.Constraint('Coincident',
                                              start_idx + 0, 2,
                                              start_idx + 1, 1))
    sketch.addConstraint(Sketcher.Constraint('Coincident',
                                              start_idx + 1, 2,
                                              start_idx + 2, 1))
    sketch.addConstraint(Sketcher.Constraint('Coincident',
                                              start_idx + 2, 2,
                                              start_idx + 3, 1))
    sketch.addConstraint(Sketcher.Constraint('Coincident',
                                              start_idx + 3, 2,
                                              start_idx + 0, 1))
