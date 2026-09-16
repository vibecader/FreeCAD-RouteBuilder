# FreeCAD-RouteBuilder by VibeCADer
# Copyright (C) 2026 VibeCADer
# Contact: korney92d1@yandex.ru
# SPDX-License-Identifier: LGPL-2.1-or-later

import FreeCAD as App
import Part
import Draft


class ParametricWire:
    def __init__(self, obj, spreadsheet, start_row=1):
        obj.Proxy = self
        self.Type = "ParametricWire"

        if not hasattr(obj, "Spreadsheet"):
            obj.addProperty("App::PropertyLink", "Spreadsheet", "Base", "Ссылка на таблицу")
        obj.Spreadsheet = spreadsheet

        if not hasattr(obj, "StartRow"):
            obj.addProperty("App::PropertyInteger", "StartRow", "Base", "Номер первой строки")
        obj.StartRow = start_row

        if not hasattr(obj, "FilletRadius"):
            obj.addProperty("App::PropertyLength", "FilletRadius", "Base", "Радиус скругления")
        obj.FilletRadius = 0.0

        if not hasattr(obj, "Shape"):
            obj.addProperty("Part::PropertyPartShape", "Shape", "Base", "Форма полилинии")
            obj.setEditorMode("Shape", 2)

        if not hasattr(obj, "InternalWire"):
            obj.addProperty("App::PropertyLink", "InternalWire", "Base", "Внутренняя ломаная")
            obj.setEditorMode("InternalWire", 2)

        # === Отображение ===
        if not hasattr(obj, "ShowPoints"):
            obj.addProperty("App::PropertyBool", "ShowPoints", "Display", "Показывать точки")
            obj.ShowPoints = True

        # === Привязка к геометрии ===
        if not hasattr(obj, "AttachmentSupport"):
            obj.addProperty("App::PropertyLinkSub", "AttachmentSupport", "Attachment",
                            "Ссылка на объект привязки (вершина, ребро, грань)")
            obj.setEditorMode("AttachmentSupport", 2)

        if not hasattr(obj, "AttachmentPosition"):
            obj.addProperty("App::PropertyVector", "AttachmentPosition", "Attachment",
                            "Вычисленная позиция привязки")
            obj.setEditorMode("AttachmentPosition", 2)

    def onChanged(self, obj, prop):
        if prop == "ShowPoints":
            try:
                self.execute(obj)
            except Exception:
                pass

    def get_attachment_position(self, obj):
        if not obj.AttachmentSupport:
            return None

        try:
            support_obj, sub_elements = obj.AttachmentSupport
            if not support_obj:
                return None

            if hasattr(support_obj, "Placement") and not sub_elements:
                return support_obj.Placement.Base

            if not sub_elements:
                return None

            sub_element = sub_elements[0] if isinstance(sub_elements, (list, tuple)) else sub_elements
            if not sub_element:
                return None

            if not hasattr(support_obj, "Shape"):
                return None

            shape = support_obj.Shape

            if sub_element.startswith("Vertex"):
                idx = int(sub_element.replace("Vertex", "")) - 1
                if 0 <= idx < len(shape.Vertexes):
                    return shape.Vertexes[idx].Point

            elif sub_element.startswith("Edge"):
                idx = int(sub_element.replace("Edge", "")) - 1
                if 0 <= idx < len(shape.Edges):
                    edge = shape.Edges[idx]
                    param = edge.FirstParameter + (edge.LastParameter - edge.FirstParameter) / 2.0
                    return edge.valueAt(param)

            elif sub_element.startswith("Face"):
                idx = int(sub_element.replace("Face", "")) - 1
                if 0 <= idx < len(shape.Faces):
                    face = shape.Faces[idx]
                    return face.CenterOfMass

            return None
        except Exception as e:
            App.Console.PrintWarning(f"Ошибка чтения привязки: {e}\n")
            return None

    def _update_points_markers(self, obj, points):
        """Создаёт/обновляет маркеры точек."""
        doc = obj.Document

        if not hasattr(obj, "ShowPoints"):
            return

        if not obj.ShowPoints:
            old = doc.getObject("_PointsMarkers")
            if old:
                try:
                    old.ViewObject.Visibility = False
                except Exception:
                    pass
            return

        if not points:
            return

        try:
            marker = doc.getObject("_PointsMarkers")
            if marker is None:
                marker = doc.addObject("Part::Feature", "_PointsMarkers")
                marker.ViewObject.PointSize = 8.0
                marker.ViewObject.PointColor = (0.0, 0.0, 1.0)

            vertices = [Part.Vertex(p) for p in points]
            marker.Shape = Part.makeCompound(vertices)
            marker.ViewObject.Visibility = True
        except Exception as e:
            App.Console.PrintWarning(f"Не удалось создать маркеры точек: {e}\n")

    def _update_points_labels(self, obj, points):
        """Создаёт/обновляет метки с номерами и координатами."""
        doc = obj.Document

        if not hasattr(obj, "ShowPoints"):
            return

        if not obj.ShowPoints:
            for o in list(doc.Objects):
                if o.Name.startswith("_PointLabel_"):
                    try:
                        o.ViewObject.Visibility = False
                    except Exception:
                        pass
            return

        if not points:
            return

        try:
            for o in list(doc.Objects):
                if o.Name.startswith("_PointLabel_"):
                    doc.removeObject(o.Name)

            for i, p in enumerate(points):
                label = doc.addObject("App::Annotation", f"_PointLabel_{i}")
                label.LabelText = [f"#{i+1} ({p.x:.1f}, {p.y:.1f}, {p.z:.1f})"]
                label.Position = p
                label.ViewObject.TextColor = (0.0, 0.0, 1.0)
                label.ViewObject.FontSize = 24
                label.ViewObject.Visibility = True
        except Exception as e:
            App.Console.PrintWarning(f"Не удалось создать метки точек: {e}\n")

    def _update_points_group(self, obj):
        """Создаёт/обновляет группу для точек и меток."""
        doc = obj.Document

        group = doc.getObject("_PointsGroup")
        if group is None:
            group = doc.addObject("App::DocumentObjectGroup", "_PointsGroup")
            group.Label = "Points"

        for child in list(group.Group):
            group.removeObject(child)

        marker = doc.getObject("_PointsMarkers")
        if marker:
            group.addObject(marker)

        for o in doc.Objects:
            if o.Name.startswith("_PointLabel_"):
                group.addObject(o)

    def execute(self, obj):
        points = []
        row = obj.StartRow
        if not obj.Spreadsheet:
            return
        while True:
            try:
                x = obj.Spreadsheet.get("A" + str(row))
                y = obj.Spreadsheet.get("B" + str(row))
                z = obj.Spreadsheet.get("C" + str(row))
            except ValueError:
                break
            if x is None or y is None or z is None:
                break
            points.append(App.Vector(x, y, z))
            row += 1

        if len(points) < 2:
            obj.Shape = Part.Shape()
            if App.GuiUp:
                old = obj.Document.getObject("_PointsMarkers")
                if old:
                    obj.Document.removeObject("_PointsMarkers")
                for o in list(obj.Document.Objects):
                    if o.Name.startswith("_PointLabel_"):
                        obj.Document.removeObject(o.Name)
            obj.purgeTouched()
            return

        attachment_pos = self.get_attachment_position(obj)

        if attachment_pos is None:
            if obj.AttachmentSupport:
                App.Console.PrintWarning(
                    "Привязка потеряна. Линия остаётся на последней позиции.\n"
                )
                attachment_pos = obj.AttachmentPosition
            else:
                attachment_pos = App.Vector(0, 0, 0)
        else:
            obj.AttachmentPosition = attachment_pos

        shifted_points = [p + attachment_pos for p in points]

        doc = obj.Document
        if obj.InternalWire is None:
            wire = Draft.make_wire(shifted_points, closed=False)
            wire.Label = "_InternalWire"
            obj.InternalWire = wire
        else:
            wire = obj.InternalWire
            wire.Points = shifted_points

        wire.FilletRadius = obj.FilletRadius
        wire.recompute()
        wire.purgeTouched()
        obj.Shape = wire.Shape

        if App.GuiUp:
            wire.ViewObject.Visibility = False
            if hasattr(obj, "ShowPoints"):
                self._update_points_markers(obj, shifted_points)
                self._update_points_labels(obj, shifted_points)
                self._update_points_group(obj)

        for o in doc.Objects:
            if o.TypeId != "PartDesign::Body":
                continue
            for child in o.Group:
                if child.TypeId != "PartDesign::SubShapeBinder":
                    continue
                if not child.Support:
                    continue
                for support_entry in child.Support:
                    if support_entry[0] == obj:
                        o.touch()
                        break

        obj.purgeTouched()

    def dumps(self):
        return None

    def loads(self, state):
        pass


def create_parametric_wire(spreadsheet_name="Spreadsheet", start_row=1):
    doc = App.ActiveDocument
    sheet = doc.getObject(spreadsheet_name)
    if not sheet:
        App.Console.PrintError(f"Таблица '{spreadsheet_name}' не найдена!\n")
        return None

    obj = doc.addObject("Part::FeaturePython", "ParametricWire")
    ParametricWire(obj, sheet, start_row)
    if App.GuiUp:
        obj.ViewObject.Proxy = 0
    doc.recompute()
    return obj
