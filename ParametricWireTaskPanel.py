# FreeCAD-RouteBuilder by VibeCADer
# Copyright (C) 2026 VibeCADer
# Contact: korney92d1@yandex.ru
# SPDX-License-Identifier: LGPL-2.1-or-later

import os
import FreeCAD as App
import FreeCADGui as Gui
import Part

try:
    from PySide import QtGui, QtCore
except ImportError:
    from PySide6 import QtGui, QtCore


# ============================================================
# Диалог добавления вектора
# ============================================================
class AddVectorDialog(QtGui.QDialog):
    """Диалог добавления нового вектора с фантомом и проверкой."""

    def __init__(self, panel, parent=None):
        super().__init__(parent)
        self.panel = panel
        self.phantom = None
        self.setWindowTitle("Add Vector")
        self.setMinimumWidth(320)

        layout = QtGui.QVBoxLayout(self)

        axis_layout = QtGui.QHBoxLayout()
        axis_layout.addWidget(QtGui.QLabel("Axis:"))
        self.axis_combo = QtGui.QComboBox()
        self.axis_combo.addItems(["+X", "-X", "+Y", "-Y", "+Z", "-Z"])
        self.axis_combo.currentIndexChanged.connect(self._update_phantom)
        axis_layout.addWidget(self.axis_combo)
        layout.addLayout(axis_layout)

        length_layout = QtGui.QHBoxLayout()
        length_layout.addWidget(QtGui.QLabel("Length (mm):"))
        self.length_input = QtGui.QDoubleSpinBox()
        self.length_input.setRange(0.01, 1000000.0)
        self.length_input.setValue(1000.0)
        self.length_input.setDecimals(2)
        self.length_input.valueChanged.connect(self._update_phantom)
        length_layout.addWidget(self.length_input)
        layout.addLayout(length_layout)

        self.overlap_label = QtGui.QLabel("")
        self.overlap_label.setStyleSheet(
            "color: #c0392b; font-weight: bold; font-size: 11px;"
        )
        self.overlap_label.setWordWrap(True)
        layout.addWidget(self.overlap_label)

        buttons = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._check_overlap()

    def showEvent(self, event):
        super().showEvent(event)
        self._create_phantom()
        self._update_phantom()

    def closeEvent(self, event):
        self._remove_phantom()
        super().closeEvent(event)

    def _create_phantom(self):
        if self.phantom:
            return
        doc = App.ActiveDocument
        old = doc.getObject("_AddVectorPhantom")
        if old:
            doc.removeObject("_AddVectorPhantom")
        self.phantom = doc.addObject("Part::Feature", "_AddVectorPhantom")
        self.phantom.ViewObject.LineWidth = 3.0
        doc.recompute()

    def _update_phantom(self):
        if not self.phantom:
            return

        doc = App.ActiveDocument

        last_point = self.panel.get_last_point()
        if last_point is None:
            last_point = (0.0, 0.0, 0.0)

        axis = self.axis_combo.currentText()
        length = self.length_input.value()

        dx = dy = dz = 0.0
        if axis == "+X":
            dx = length
        elif axis == "-X":
            dx = -length
        elif axis == "+Y":
            dy = length
        elif axis == "-Y":
            dy = -length
        elif axis == "+Z":
            dz = length
        elif axis == "-Z":
            dz = -length

        start = App.Vector(*last_point)
        end = App.Vector(last_point[0] + dx, last_point[1] + dy, last_point[2] + dz)

        line = Part.makeLine(start, end)
        self.phantom.Shape = line

        overlap = self.panel._check_vector_overlap(axis, length)

        if "X" in axis:
            color = (1.0, 0.0, 0.0)
        elif "Y" in axis:
            color = (0.0, 1.0, 0.0)
        else:
            color = (0.0, 0.0, 1.0)

        if overlap:
            color = tuple(c * 0.3 for c in color)
            self.overlap_label.setText("⚠ Overlap on existing segment")
        else:
            self.overlap_label.setText("")

        self.phantom.ViewObject.LineColor = color
        doc.recompute()

    def _check_overlap(self):
        axis = self.axis_combo.currentText()
        length = self.length_input.value()

        overlap = self.panel._check_vector_overlap(axis, length)

        if overlap:
            self.overlap_label.setText("⚠ Overlap on existing segment")
        else:
            self.overlap_label.setText("")

        return overlap

    def _remove_phantom(self):
        doc = App.ActiveDocument
        old = doc.getObject("_AddVectorPhantom")
        if old:
            doc.removeObject("_AddVectorPhantom")
        self.phantom = None
        doc.recompute()

    def get_result(self):
        axis = self.axis_combo.currentText()
        length = self.length_input.value()
        return axis, length

    def accept(self):
        axis, length = self.get_result()

        if self.panel._check_vector_overlap(axis, length):
            QtGui.QMessageBox.warning(
                self,
                "Overlap",
                f"Vector {axis} {length} mm creates an overlap.\n"
                f"Change the axis or length."
            )
            return

        self._remove_phantom()
        super().accept()

    def reject(self):
        self._remove_phantom()
        super().reject()


class ParametricWireTaskPanel:
    """Панель с вкладками: Builder, Points, Vectors, Attachment."""

    def __init__(self, obj):
        self.obj = obj
        self.phantom = None
        self.shortcuts = []
        self._marker = None
        self._marker_label = None
        self._attach_marker = None
        self._new_marker = None
        self._highlight_segment = None
        self._vectors_updating = False
        self._selected_vertex_key = None
        self._overlap_cache = None
        self.form = QtGui.QWidget()
        self.form.setWindowTitle("Route Builder")
        self.layout = QtGui.QVBoxLayout(self.form)

        try:
            Gui.Selection.addSelectionGate(
                "SELECT Part::Feature SUBELEMENT Vertex "
                "SELECT Part::Feature SUBELEMENT Edge "
                "SELECT Part::Feature SUBELEMENT Face "
                "SELECT PartDesign::Body SUBELEMENT Vertex "
                "SELECT PartDesign::Body SUBELEMENT Edge "
                "SELECT PartDesign::Body SUBELEMENT Face "
                "SELECT PartDesign::Feature SUBELEMENT Vertex "
                "SELECT PartDesign::Feature SUBELEMENT Edge "
                "SELECT PartDesign::Feature SUBELEMENT Face "
                "SELECT App::Link SUBELEMENT Vertex "
                "SELECT App::Link SUBELEMENT Edge "
                "SELECT App::Link SUBELEMENT Face"
            )
            App.Console.PrintMessage("Selection filter: vertices, edges, faces.\n")
        except Exception as e:
            App.Console.PrintWarning(f"Failed to activate filter: {e}\n")

        self.tabs = QtGui.QTabWidget()
        self.layout.addWidget(self.tabs)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.builder_tab = QtGui.QWidget()
        self.builder_layout = QtGui.QVBoxLayout(self.builder_tab)
        self._build_builder_tab()
        self.tabs.addTab(self.builder_tab, "Builder")

        self.points_tab = QtGui.QWidget()
        self.points_layout = QtGui.QVBoxLayout(self.points_tab)
        self._build_points_tab()
        self.tabs.addTab(self.points_tab, "Points")

        self.vectors_tab = QtGui.QWidget()
        self.vectors_layout = QtGui.QVBoxLayout(self.vectors_tab)
        self._build_vectors_tab()
        self.tabs.addTab(self.vectors_tab, "Vectors")

        self.attach_tab = QtGui.QWidget()
        self.attach_layout = QtGui.QVBoxLayout(self.attach_tab)
        self._build_attachment_tab()
        self.tabs.addTab(self.attach_tab, "Attachment")

        sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Return"), self.form)
        sc.setContext(QtCore.Qt.ApplicationShortcut)
        sc.activated.connect(self.add_segment)
        self.shortcuts.append(sc)

        sc = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self.form)
        sc.setContext(QtCore.Qt.ApplicationShortcut)
        sc.activated.connect(self.remove_last_segment)
        self.shortcuts.append(sc)

        for keys, index in [
            ("Ctrl+1", 0), ("Ctrl+2", 1), ("Ctrl+3", 2),
            ("Ctrl+4", 3), ("Ctrl+5", 4), ("Ctrl+6", 5),
        ]:
            sc = QtGui.QShortcut(QtGui.QKeySequence(keys), self.form)
            sc.setContext(QtCore.Qt.ApplicationShortcut)
            sc.activated.connect(
                lambda idx=index: self.axis_combo.setCurrentIndex(idx)
            )
            self.shortcuts.append(sc)

        self._selection_timer = QtCore.QTimer()
        self._selection_timer.timeout.connect(self._check_selection)
        self._selection_timer.start(200)

        self._zoom_timer = QtCore.QTimer()
        self._zoom_timer.timeout.connect(self._update_marker_sizes)
        self._zoom_timer.start(100)

        self.update_info()
        self.update_phantom()
        self.refresh_points_table()
        self.refresh_attachment_info()
        self._update_toggle_button_text()
        self._update_buttons_state()

    # ============================================================
    # Переключатель точек
    # ============================================================
    def _toggle_points(self):
        if not hasattr(self.obj, "ShowPoints"):
            App.Console.PrintWarning(
                "ShowPoints property missing. Recreate the wire.\n"
            )
            return
        self.obj.ShowPoints = not self.obj.ShowPoints
        self._update_toggle_button_text()
        App.ActiveDocument.recompute()

    def _update_toggle_button_text(self):
        if not hasattr(self, "toggle_points_btn"):
            return
        if not hasattr(self.obj, "ShowPoints"):
            self.toggle_points_btn.setText("Show Points")
            return
        if self.obj.ShowPoints:
            self.toggle_points_btn.setText("Hide Points")
        else:
            self.toggle_points_btn.setText("Show Points")

    # ============================================================
    # Глобальная проверка наложения
    # ============================================================
    def _segments_overlap(self, a1, a2, b1, b2, tol=1e-6):
        da = a2 - a1
        db = b2 - b1

        if da.Length < tol or db.Length < tol:
            return False

        if (a1 - b1).Length < tol and (a2 - b2).Length < tol:
            return True
        if (a1 - b2).Length < tol and (a2 - b1).Length < tol:
            return True

        cross = da.cross(db)
        if cross.Length > tol:
            return False

        da_norm = da.normalize()

        def param_t(point, start, direction, seg_length):
            v = point - start
            return v.dot(direction) / seg_length

        t_b1 = param_t(b1, a1, da_norm, da.Length)
        t_b2 = param_t(b2, a1, da_norm, da.Length)

        t_min = min(t_b1, t_b2)
        t_max = max(t_b1, t_b2)

        if t_max < tol or t_min > 1.0 - tol:
            return False

        if tol < t_b1 < 1.0 - tol:
            return True
        if tol < t_b2 < 1.0 - tol:
            return True

        if t_min > tol and t_max < 1.0 - tol:
            return True

        return False

    def _check_vector_overlap(self, axis, length):
        doc = App.ActiveDocument
        sheet_p = self.obj.Spreadsheet
        if not sheet_p:
            return False

        points = []
        row = 1
        while True:
            try:
                x = sheet_p.get("A" + str(row))
                y = sheet_p.get("B" + str(row))
                z = sheet_p.get("C" + str(row))
            except ValueError:
                break
            if x is None or y is None or z is None:
                break
            points.append(App.Vector(x, y, z))
            row += 1

        if len(points) < 2:
            return False

        last = points[-1]

        dx = dy = dz = 0.0
        if axis == "+X":
            dx = length
        elif axis == "-X":
            dx = -length
        elif axis == "+Y":
            dy = length
        elif axis == "-Y":
            dy = -length
        elif axis == "+Z":
            dz = length
        elif axis == "-Z":
            dz = -length

        new_end = App.Vector(last.x + dx, last.y + dy, last.z + dz)

        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]

            if self._segments_overlap(last, new_end, p1, p2):
                return True

        return False

    def _check_all_overlaps(self):
        doc = App.ActiveDocument
        sheet_p = self.obj.Spreadsheet
        if not sheet_p:
            return False

        points = []
        row = 1
        while True:
            try:
                x = sheet_p.get("A" + str(row))
                y = sheet_p.get("B" + str(row))
                z = sheet_p.get("C" + str(row))
            except ValueError:
                break
            if x is None or y is None or z is None:
                break
            points.append(App.Vector(x, y, z))
            row += 1

        if len(points) < 3:
            return False

        for i in range(len(points) - 1):
            for j in range(i + 1, len(points) - 1):
                if j == i + 1:
                    continue

                a1 = points[i]
                a2 = points[i + 1]
                b1 = points[j]
                b2 = points[j + 1]

                if self._segments_overlap(a1, a2, b1, b2):
                    return True

        return False

    def _validate_no_overlap(self, action_name="action"):
        if self._check_all_overlaps():
            QtGui.QMessageBox.warning(
                None,
                "Segment overlap",
                f"Segment overlap detected.\n"
                f"{action_name} cancelled.\n\n"
                f"Check the Vectors table."
            )
            App.Console.PrintWarning(f"Overlap on action: {action_name}.\n")
            return False
        return True

    def _update_buttons_state(self):
        overlap = self._check_all_overlaps()

        if overlap:
            if hasattr(self, "add_button"):
                self.add_button.setEnabled(False)
                self.add_button.setText("Overlap - fix the route")
                self.add_button.setStyleSheet("background-color: #ffcccc;")
            if hasattr(self, "add_vector_button"):
                self.add_vector_button.setEnabled(False)
                self.add_vector_button.setStyleSheet("background-color: #ffcccc;")
        else:
            if hasattr(self, "add_button"):
                self.add_button.setEnabled(True)
                self.add_button.setText("Add Segment")
                self.add_button.setStyleSheet("")
            if hasattr(self, "add_vector_button"):
                self.add_vector_button.setEnabled(True)
                self.add_vector_button.setStyleSheet("")

    def _sub_type_label(self, sub_name):
        if not sub_name:
            return ""
        if sub_name.startswith("Vertex"):
            return "point"
        if sub_name.startswith("Edge"):
            return "edge midpoint"
        if sub_name.startswith("Face"):
            return "face center of mass"
        return ""

    def _force_recompute(self):
        doc = App.ActiveDocument
        if not doc:
            return

        try:
            self.obj.touch()
        except Exception:
            pass

        count = 0
        for o in doc.Objects:
            if o.TypeId != "PartDesign::Body":
                continue
            for child in o.Group:
                if child.TypeId != "PartDesign::SubShapeBinder":
                    continue
                if not child.Support:
                    continue
                for support_entry in child.Support:
                    if support_entry[0] == self.obj:
                        o.touch()
                        count += 1
                        break

        doc.recompute()

        self.update_info()
        self.update_phantom()
        self.refresh_points_table()
        self._refresh_vectors_table()
        self._update_toggle_button_text()
        self._update_buttons_state()
        selected = self.vectors_table.selectedItems()
        if selected:
            row = selected[0].row()
            self._highlight_segment_row(row)

        if self._check_all_overlaps():
            App.Console.PrintWarning("Segment overlap detected in route!\n")

        App.Console.PrintMessage(f"Recompute done. Bodies updated: {count}\n")

    def _on_tab_changed(self, index):
        """Скрывает фантом при уходе с Builder. Готовит Vectors и Attachment."""
        if self.phantom:
            try:
                if index == 0:
                    self.phantom.ViewObject.Visibility = True
                else:
                    self.phantom.ViewObject.Visibility = False
            except Exception:
                pass

        if index == 2:  # Vectors
            self._ensure_vectors_table()
            self._refresh_vectors_table()
            self._remove_highlight()
        elif index == 3:  # Attachment
            self._update_attach_marker()
            self._check_selection()
            # Принудительная перерисовка — маркеры появляются сразу
            try:
                Gui.SendMsgToActiveView("ViewFit")
            except Exception:
                pass
        else:
            self._remove_highlight()

    def _ensure_vectors_table(self):
        doc = App.ActiveDocument
        sheet_v = doc.getObject("Spreadsheet_Vectors")
        if sheet_v:
            return sheet_v

        sheet_v = doc.addObject("Spreadsheet::Sheet", "Spreadsheet_Vectors")
        sheet_v.Label = "Vectors"
        sheet_v.set("A1", "DIR")
        sheet_v.set("B1", "LEN")
        doc.recompute()

        self._update_vectors_from_points()
        return sheet_v

    def _refresh_vectors_table(self):
        doc = App.ActiveDocument
        sheet_v = doc.getObject("Spreadsheet_Vectors")
        if not sheet_v:
            self.vectors_table.setRowCount(0)
            return

        self._vectors_updating = True

        rows = []
        row = 2
        while True:
            try:
                dir_val = sheet_v.get("A" + str(row))
                len_val = sheet_v.get("B" + str(row))
            except ValueError:
                break
            if dir_val is None or len_val is None:
                break
            if dir_val == "" or len_val == "":
                row += 1
                continue
            rows.append((dir_val, len_val))
            row += 1

        self.vectors_table.setRowCount(len(rows))

        for i, (dir_val, len_val) in enumerate(rows):
            item_dir = QtGui.QTableWidgetItem(str(dir_val))
            item_dir.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
            item_len = QtGui.QTableWidgetItem(str(len_val))
            item_len.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable)
            self.vectors_table.setItem(i, 0, item_dir)
            self.vectors_table.setItem(i, 1, item_len)

        self.vectors_table.resizeColumnsToContents()

        self._vectors_updating = False
        self._update_buttons_state()

    def _on_vectors_cell_changed(self, row, col):
        if self._vectors_updating:
            return
        if col != 1:
            return

        doc = App.ActiveDocument
        sheet_v = doc.getObject("Spreadsheet_Vectors")
        if not sheet_v:
            return

        item = self.vectors_table.item(row, 1)
        if not item:
            return

        try:
            new_len = float(item.text())
        except ValueError:
            App.Console.PrintWarning("Invalid LEN value.\n")
            return

        dir_item = self.vectors_table.item(row, 0)
        if not dir_item:
            return
        axis = dir_item.text().strip()

        sheet_row = row + 2
        try:
            old_len = sheet_v.get("B" + str(sheet_row))
        except ValueError:
            old_len = "0"

        sheet_v.set("B" + str(sheet_row), str(new_len))
        doc.recompute()

        self._apply_vectors_to_points()

        if not self._validate_no_overlap("Change LEN"):
            sheet_v.set("B" + str(sheet_row), str(old_len))
            doc.recompute()
            self._apply_vectors_to_points()
            self._refresh_vectors_table()
            return

        App.Console.PrintMessage(f"Applied new LEN value: {new_len}\n")

    def _on_vectors_selection_changed(self):
        selected = self.vectors_table.selectedItems()
        if not selected:
            self._remove_highlight()
            return

        row = selected[0].row()
        self._highlight_segment_row(row)

    def _highlight_segment_row(self, row):
        self._remove_highlight()

        doc = App.ActiveDocument
        sheet_p = self.obj.Spreadsheet
        if not sheet_p:
            return

        p1_row = row + 1
        p2_row = row + 2

        try:
            x1 = sheet_p.get("A" + str(p1_row))
            y1 = sheet_p.get("B" + str(p1_row))
            z1 = sheet_p.get("C" + str(p1_row))
            x2 = sheet_p.get("A" + str(p2_row))
            y2 = sheet_p.get("B" + str(p2_row))
            z2 = sheet_p.get("C" + str(p2_row))
        except ValueError:
            return

        if x1 is None or y1 is None or z1 is None:
            return
        if x2 is None or y2 is None or z2 is None:
            return

        dir_item = self.vectors_table.item(row, 0)
        if not dir_item:
            return
        dir_str = dir_item.text().strip()

        if "X" in dir_str:
            color = (1.0, 0.0, 0.0)
        elif "Y" in dir_str:
            color = (0.0, 1.0, 0.0)
        elif "Z" in dir_str:
            color = (0.0, 0.0, 1.0)
        else:
            color = (1.0, 1.0, 0.0)

        p1 = App.Vector(x1, y1, z1)
        p2 = App.Vector(x2, y2, z2)
        line = Part.makeLine(p1, p2)

        marker = doc.addObject("Part::Feature", "_HighlightSegment")
        marker.Shape = line
        marker.ViewObject.LineWidth = 6.0
        marker.ViewObject.LineColor = color
        self._highlight_segment = marker
        doc.recompute()

    def _remove_highlight(self):
        doc = App.ActiveDocument
        old = doc.getObject("_HighlightSegment")
        if old:
            doc.removeObject("_HighlightSegment")
        self._highlight_segment = None
        doc.recompute()

    def _update_vectors_from_points(self):
        doc = App.ActiveDocument
        sheet_p = self.obj.Spreadsheet
        sheet_v = doc.getObject("Spreadsheet_Vectors")
        if not sheet_p or not sheet_v:
            return

        row = 2
        while True:
            try:
                v = sheet_v.get("A" + str(row))
                if v is None:
                    break
                sheet_v.clear("A" + str(row))
                sheet_v.clear("B" + str(row))
                row += 1
            except ValueError:
                break

        sheet_v.set("A1", "DIR")
        sheet_v.set("B1", "LEN")

        points = []
        row = 1
        while True:
            try:
                x = sheet_p.get("A" + str(row))
                y = sheet_p.get("B" + str(row))
                z = sheet_p.get("C" + str(row))
            except ValueError:
                break
            if x is None or y is None or z is None:
                break
            points.append(App.Vector(x, y, z))
            row += 1

        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]
            delta = p2 - p1
            length = delta.Length

            if abs(delta.x) > 1e-6 and abs(delta.y) < 1e-6 and abs(delta.z) < 1e-6:
                dir_val = "+X" if delta.x > 0 else "-X"
            elif abs(delta.y) > 1e-6 and abs(delta.x) < 1e-6 and abs(delta.z) < 1e-6:
                dir_val = "+Y" if delta.y > 0 else "-Y"
            elif abs(delta.z) > 1e-6 and abs(delta.x) < 1e-6 and abs(delta.y) < 1e-6:
                dir_val = "+Z" if delta.z > 0 else "-Z"
            else:
                dir_val = "DIAG"

            row_out = i + 2
            sheet_v.set("A" + str(row_out), dir_val)
            sheet_v.set("B" + str(row_out), str(length))

        doc.recompute()

    def _apply_vectors_to_points(self):
        doc = App.ActiveDocument
        sheet_p = self.obj.Spreadsheet
        sheet_v = doc.getObject("Spreadsheet_Vectors")
        if not sheet_p or not sheet_v:
            App.Console.PrintError("Table not found.\n")
            return

        try:
            x0 = sheet_p.get("A1")
            y0 = sheet_p.get("B1")
            z0 = sheet_p.get("C1")
        except ValueError:
            App.Console.PrintError("Failed to read first point.\n")
            return

        if x0 is None or y0 is None or z0 is None:
            return

        points = [App.Vector(x0, y0, z0)]

        row = 2
        while True:
            try:
                dir_val = sheet_v.get("A" + str(row))
                len_val = sheet_v.get("B" + str(row))
            except ValueError:
                break
            if dir_val is None or len_val is None:
                break
            if dir_val == "" or len_val == "":
                row += 1
                continue

            dir_str = str(dir_val).strip()
            try:
                length = float(len_val)
            except ValueError:
                row += 1
                continue

            last = points[-1]

            if dir_str == "+X":
                new_point = last + App.Vector(length, 0, 0)
            elif dir_str == "-X":
                new_point = last + App.Vector(-length, 0, 0)
            elif dir_str == "+Y":
                new_point = last + App.Vector(0, length, 0)
            elif dir_str == "-Y":
                new_point = last + App.Vector(0, -length, 0)
            elif dir_str == "+Z":
                new_point = last + App.Vector(0, 0, length)
            elif dir_str == "-Z":
                new_point = last + App.Vector(0, 0, -length)
            elif dir_str == "DIAG":
                # DIAG — берём координаты из существующей таблицы
                try:
                    px = sheet_p.get("A" + str(row))
                    py = sheet_p.get("B" + str(row))
                    pz = sheet_p.get("C" + str(row))
                    if px is not None and py is not None and pz is not None:
                        new_point = App.Vector(float(px), float(py), float(pz))
                    else:
                        row += 1
                        continue
                except ValueError:
                    row += 1
                    continue
            else:
                row += 1
                continue

            points.append(new_point)
            row += 1

        for i, p in enumerate(points):
            row_p = i + 1
            sheet_p.set("A" + str(row_p), str(p.x))
            sheet_p.set("B" + str(row_p), str(p.y))
            sheet_p.set("C" + str(row_p), str(p.z))

        doc.recompute()
        self.update_info()
        self.update_phantom()
        self.refresh_points_table()
        self._refresh_vectors_table()

        selected = self.vectors_table.selectedItems()
        if selected:
            row = selected[0].row()
            self._highlight_segment_row(row)

    def _on_add_vector(self):
        dlg = AddVectorDialog(self)
        if dlg.exec_() != QtGui.QDialog.Accepted:
            return

        axis, length = dlg.get_result()

        doc = App.ActiveDocument
        sheet_p = self.obj.Spreadsheet
        sheet_v = doc.getObject("Spreadsheet_Vectors")

        if not sheet_v:
            sheet_v = self._ensure_vectors_table()

        if sheet_p:
            try:
                x0 = sheet_p.get("A1")
                if x0 is None or x0 == "":
                    sheet_p.set("A1", "0")
                    sheet_p.set("B1", "0")
                    sheet_p.set("C1", "0")
                    doc.recompute()
            except ValueError:
                sheet_p.set("A1", "0")
                sheet_p.set("B1", "0")
                sheet_p.set("C1", "0")
                doc.recompute()

        last_point = self.get_last_point()
        if last_point is None:
            last_point = (0.0, 0.0, 0.0)

        dx = dy = dz = 0.0
        if axis == "+X":
            dx = length
        elif axis == "-X":
            dx = -length
        elif axis == "+Y":
            dy = length
        elif axis == "-Y":
            dy = -length
        elif axis == "+Z":
            dz = length
        elif axis == "-Z":
            dz = -length

        new_point = (last_point[0] + dx, last_point[1] + dy, last_point[2] + dz)

        row = 1
        while True:
            try:
                x = sheet_p.get("A" + str(row))
                if x is None or x == "":
                    break
                row += 1
            except ValueError:
                break

        sheet_p.set("A" + str(row), str(new_point[0]))
        sheet_p.set("B" + str(row), str(new_point[1]))
        sheet_p.set("C" + str(row), str(new_point[2]))

        row_v = row
        sheet_v.set("A" + str(row_v), axis)
        sheet_v.set("B" + str(row_v), str(length))

        doc.recompute()

        self.update_info()
        self.update_phantom()
        self.refresh_points_table()
        self._refresh_vectors_table()

        App.Console.PrintMessage(
            f"Vector added: {axis} {length} mm -> point ({new_point[0]:.2f}, {new_point[1]:.2f}, {new_point[2]:.2f})\n"
        )

    def _on_remove_last_vector(self):
        doc = App.ActiveDocument
        sheet_p = self.obj.Spreadsheet
        sheet_v = doc.getObject("Spreadsheet_Vectors")

        if not sheet_v:
            App.Console.PrintWarning("Vectors table not found.\n")
            return

        last_row_v = 1
        row = 2
        while True:
            try:
                dir_val = sheet_v.get("A" + str(row))
                if dir_val is not None and dir_val != "":
                    last_row_v = row
                    row += 1
                else:
                    break
            except ValueError:
                break

        selected = self.vectors_table.selectedItems()
        if selected:
            sel_row = selected[0].row()
            sel_sheet_row = sel_row + 2
            if sel_sheet_row != last_row_v:
                QtGui.QMessageBox.warning(
                    None,
                    "Deletion forbidden",
                    "Deletion from the middle is not supported.\n"
                    "Select the last row or clear the selection."
                )
                return

        if last_row_v <= 1:
            App.Console.PrintWarning("Nothing to delete: Vectors table is empty.\n")
            return

        sheet_v.clear("A" + str(last_row_v))
        sheet_v.clear("B" + str(last_row_v))

        if sheet_p:
            last_row_p = 1
            row = 1
            while True:
                try:
                    x = sheet_p.get("A" + str(row))
                    if x is not None and x != "":
                        last_row_p = row
                        row += 1
                    else:
                        break
                except ValueError:
                    break

            if last_row_p > 1:
                sheet_p.clear("A" + str(last_row_p))
                sheet_p.clear("B" + str(last_row_p))
                sheet_p.clear("C" + str(last_row_p))

        doc.recompute()

        self.update_info()
        self.update_phantom()
        self.refresh_points_table()
        self._refresh_vectors_table()

        App.Console.PrintMessage(f"Last vector removed (row {last_row_v}).\n")

    def _update_marker_sizes(self):
        try:
            view = Gui.ActiveDocument.ActiveView
            camera = view.getCameraNode()
            focal_distance = camera.focalDistance.getValue()
        except Exception:
            return

        base_size = focal_distance * 0.08
        base_size = max(5.0, min(base_size, 80.0))

        doc = App.ActiveDocument

        # Красный маркер привязки (текущая привязка)
        red = doc.getObject("_AttachmentMarker")
        if red:
            try:
                red.ViewObject.PointSize = base_size * 1.0
            except Exception:
                pass

        # Синий маркер (выбранная вершина/ребро/грань)
        blue = doc.getObject("_NewVertexMarker")
        if blue:
            try:
                blue.ViewObject.PointSize = base_size * 0.9
            except Exception:
                pass

        # Маркер точки из таблицы Points
        point_marker = doc.getObject("_PointMarker")
        if point_marker:
            try:
                point_marker.ViewObject.PointSize = base_size * 0.9
            except Exception:
                pass

    def _check_selection(self):
        try:
            selection = Gui.Selection.getSelectionEx()
        except Exception:
            return

        doc = App.ActiveDocument

        if not selection:
            if self._selected_vertex_key is not None:
                old = doc.getObject("_NewVertexMarker")
                if old:
                    doc.removeObject("_NewVertexMarker")
                self._new_marker = None
                self._selected_vertex_key = None
                try:
                    self.selected_vertex_label.setText("Selected: —")
                    self.selected_vertex_label.setStyleSheet(
                        "color: #2980b9; font-weight: bold; font-size: 12px;"
                    )
                except Exception:
                    pass
                doc.recompute()
            return

        sel = selection[0]
        sub_names = sel.SubElementNames
        if not sub_names:
            return

        sub_name = None
        for name in sub_names:
            if (name.startswith("Vertex") or
                name.startswith("Edge") or
                name.startswith("Face")):
                sub_name = name
                break

        if not sub_name:
            return

        key = f"{sel.Object.Name}.{sub_name}"

        if key == self._selected_vertex_key:
            return

        old = doc.getObject("_NewVertexMarker")
        if old:
            doc.removeObject("_NewVertexMarker")
        self._new_marker = None

        try:
            obj = sel.Object
            shape = obj.Shape
            pos = None

            if sub_name.startswith("Vertex"):
                idx = int(sub_name.replace("Vertex", "")) - 1
                if 0 <= idx < len(shape.Vertexes):
                    pos = shape.Vertexes[idx].Point

            elif sub_name.startswith("Edge"):
                idx = int(sub_name.replace("Edge", "")) - 1
                if 0 <= idx < len(shape.Edges):
                    edge = shape.Edges[idx]
                    param = edge.FirstParameter + (edge.LastParameter - edge.FirstParameter) / 2.0
                    pos = edge.valueAt(param)

            elif sub_name.startswith("Face"):
                idx = int(sub_name.replace("Face", "")) - 1
                if 0 <= idx < len(shape.Faces):
                    face = shape.Faces[idx]
                    pos = face.CenterOfMass

            if pos is None:
                return
        except Exception:
            return

        marker = doc.addObject("Part::Feature", "_NewVertexMarker")
        marker.Shape = Part.Vertex(pos)
        marker.ViewObject.PointSize = 80.0
        marker.ViewObject.PointColor = (0.0, 0.0, 1.0)
        self._new_marker = marker
        self._selected_vertex_key = key
        doc.recompute()

        try:
            type_label = self._sub_type_label(sub_name)
            if type_label:
                text = f"Selected: {sel.Object.Label}.{sub_name} ({type_label})"
            else:
                text = f"Selected: {sel.Object.Label}.{sub_name}"
            self.selected_vertex_label.setText(text)
            self.selected_vertex_label.setStyleSheet(
                "color: #2980b9; font-weight: bold; font-size: 12px;"
            )
        except Exception:
            pass

    def _build_builder_tab(self):
        title = QtGui.QLabel("Add orthogonal segment")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.builder_layout.addWidget(title)

        axis_layout = QtGui.QHBoxLayout()
        axis_layout.addWidget(QtGui.QLabel("Axis:"))
        self.axis_combo = QtGui.QComboBox()
        self.axis_combo.addItems(["+X", "-X", "+Y", "-Y", "+Z", "-Z"])
        axis_layout.addWidget(self.axis_combo)
        self.builder_layout.addLayout(axis_layout)

        length_layout = QtGui.QHBoxLayout()
        length_layout.addWidget(QtGui.QLabel("Length (mm):"))
        self.length_input = QtGui.QDoubleSpinBox()
        self.length_input.setRange(0.01, 1000000.0)
        self.length_input.setValue(1000.0)
        self.length_input.setDecimals(2)
        length_layout.addWidget(self.length_input)
        self.builder_layout.addLayout(length_layout)

        self.info_label = QtGui.QLabel("Last point: —")
        self.info_label.setStyleSheet("color: #555; font-style: italic;")
        self.builder_layout.addWidget(self.info_label)

        self.add_button = QtGui.QPushButton("Add Segment")
        self.add_button.clicked.connect(self.add_segment)
        self.builder_layout.addWidget(self.add_button)

        self.remove_button = QtGui.QPushButton("Remove Last Segment")
        self.remove_button.clicked.connect(self.remove_last_segment)
        self.builder_layout.addWidget(self.remove_button)

        self.recompute_button = QtGui.QPushButton("Recompute All")
        self.recompute_button.clicked.connect(self._force_recompute)
        self.builder_layout.addWidget(self.recompute_button)

        self.toggle_points_btn = QtGui.QPushButton("Hide Points")
        self.toggle_points_btn.clicked.connect(self._toggle_points)
        self.builder_layout.addWidget(self.toggle_points_btn)

        hint = QtGui.QLabel(
            "Hotkeys:\n"
            "  Ctrl+Enter - add segment\n"
            "  Ctrl+Z - remove last segment\n"
            "  Ctrl+1..6 - select axis"
        )
        hint.setStyleSheet("color: #777; font-size: 10px;")
        self.builder_layout.addWidget(hint)

        self.builder_layout.addStretch()

        self.axis_combo.currentIndexChanged.connect(self.update_phantom)
        self.length_input.valueChanged.connect(self.update_phantom)

    def _build_points_tab(self):
        title = QtGui.QLabel("Trajectory Points")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.points_layout.addWidget(title)

        self.points_table = QtGui.QTableWidget()
        self.points_table.setColumnCount(4)
        self.points_table.setHorizontalHeaderLabels(["#", "X", "Y", "Z"])
        self.points_table.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.points_table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.points_table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.points_table.horizontalHeader().setStretchLastSection(True)
        self.points_table.setMinimumHeight(250)
        self.points_table.doubleClicked.connect(self.on_point_double_click)
        self.points_layout.addWidget(self.points_table)

        btn_layout = QtGui.QHBoxLayout()

        self.refresh_button = QtGui.QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_points_table)
        btn_layout.addWidget(self.refresh_button)

        self.copy_button = QtGui.QPushButton("Copy All")
        self.copy_button.clicked.connect(self.copy_all_points)
        btn_layout.addWidget(self.copy_button)

        self.export_button = QtGui.QPushButton("Export CSV")
        self.export_button.clicked.connect(self.export_to_csv)
        btn_layout.addWidget(self.export_button)

        self.delete_button = QtGui.QPushButton("Delete Last")
        self.delete_button.clicked.connect(self.remove_last_segment)
        btn_layout.addWidget(self.delete_button)

        self.points_layout.addLayout(btn_layout)

    def refresh_points_table(self):
        sheet = self.obj.Spreadsheet
        if not sheet:
            self.points_table.setRowCount(0)
            return

        points = []
        row = 1
        while True:
            try:
                x = sheet.get("A" + str(row))
                y = sheet.get("B" + str(row))
                z = sheet.get("C" + str(row))
            except ValueError:
                break
            if x is None or y is None or z is None:
                break
            points.append((x, y, z))
            row += 1

        self.points_table.setRowCount(len(points))
        for i, (x, y, z) in enumerate(points):
            self.points_table.setItem(i, 0, QtGui.QTableWidgetItem(str(i + 1)))
            self.points_table.setItem(i, 1, QtGui.QTableWidgetItem(f"{x:.2f}"))
            self.points_table.setItem(i, 2, QtGui.QTableWidgetItem(f"{y:.2f}"))
            self.points_table.setItem(i, 3, QtGui.QTableWidgetItem(f"{z:.2f}"))

        self.points_table.resizeColumnsToContents()

    def on_point_double_click(self, index):
        row = index.row()
        item_x = self.points_table.item(row, 1)
        item_y = self.points_table.item(row, 2)
        item_z = self.points_table.item(row, 3)
        if not (item_x and item_y and item_z):
            return

        try:
            x = float(item_x.text())
            y = float(item_y.text())
            z = float(item_z.text())
        except ValueError:
            return

        self._remove_marker()

        doc = App.ActiveDocument

        marker = doc.addObject("Part::Feature", "_PointMarker")
        marker.Shape = Part.Vertex(App.Vector(x, y, z))
        marker.ViewObject.PointSize = 12.0
        marker.ViewObject.PointColor = (1.0, 0.0, 0.0)

        try:
            label = doc.addObject("App::Annotation", "_PointLabel")
            label.LabelText = [f"#{row + 1} ({x:.1f}, {y:.1f}, {z:.1f})"]
            label.Position = App.Vector(x, y, z)
            label.ViewObject.TextColor = (1.0, 0.0, 0.0)
            label.ViewObject.FontSize = 14
            self._marker_label = label
        except Exception:
            self._marker_label = None

        doc.recompute()

        try:
            Gui.SendMsgToActiveView("ViewAxonometric")
        except Exception:
            try:
                Gui.runCommand("Std_ViewIsometric", 0)
            except Exception:
                pass
        try:
            Gui.SendMsgToActiveView("ViewFit")
        except Exception:
            try:
                Gui.runCommand("Std_ViewFitAll", 0)
            except Exception:
                pass

        self._marker = marker

    def _remove_marker(self):
        doc = App.ActiveDocument
        for name in ("_PointMarker", "_PointLabel"):
            obj = doc.getObject(name)
            if obj:
                doc.removeObject(name)
        self._marker = None
        self._marker_label = None
        doc.recompute()

    def copy_all_points(self):
        sheet = self.obj.Spreadsheet
        if not sheet:
            return

        lines = ["X\tY\tZ"]
        row = 1
        while True:
            try:
                x = sheet.get("A" + str(row))
                y = sheet.get("B" + str(row))
                z = sheet.get("C" + str(row))
            except ValueError:
                break
            if x is None or y is None or z is None:
                break
            lines.append(f"{x:.4f}\t{y:.4f}\t{z:.4f}")
            row += 1

        text = "\n".join(lines)
        clipboard = QtGui.QApplication.clipboard()
        clipboard.setText(text)
        App.Console.PrintMessage(f"Copied {len(lines) - 1} points to clipboard.\n")

    def export_to_csv(self):
        sheet = self.obj.Spreadsheet
        if not sheet:
            return

        file_path, _ = QtGui.QFileDialog.getSaveFileName(
            None, "Save CSV", "", "CSV Files (*.csv);;All Files (*)"
        )
        if not file_path:
            return

        if not file_path.lower().endswith(".csv"):
            file_path += ".csv"

        try:
            with open(file_path, "w", encoding="utf-8-sig") as f:
                f.write("X;Y;Z\n")
                row = 1
                while True:
                    try:
                        x = sheet.get("A" + str(row))
                        y = sheet.get("B" + str(row))
                        z = sheet.get("C" + str(row))
                    except ValueError:
                        break
                    if x is None or y is None or z is None:
                        break
                    f.write(f"{x:.4f};{y:.4f};{z:.4f}\n")
                    row += 1
            App.Console.PrintMessage(f"Exported to: {file_path}\n")
        except Exception as e:
            App.Console.PrintError(f"Export error: {e}\n")

    def _build_vectors_tab(self):
        title = QtGui.QLabel("Trajectory Vectors")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.vectors_layout.addWidget(title)

        self.vectors_table = QtGui.QTableWidget()
        self.vectors_table.setColumnCount(2)
        self.vectors_table.setHorizontalHeaderLabels(["DIR", "LEN"])
        self.vectors_table.setEditTriggers(
            QtGui.QAbstractItemView.DoubleClicked |
            QtGui.QAbstractItemView.EditKeyPressed
        )
        self.vectors_table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.vectors_table.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.vectors_table.horizontalHeader().setStretchLastSection(True)
        self.vectors_table.setMinimumHeight(220)
        self.vectors_table.cellChanged.connect(self._on_vectors_cell_changed)
        self.vectors_table.itemSelectionChanged.connect(self._on_vectors_selection_changed)
        self.vectors_layout.addWidget(self.vectors_table)

        btn_layout1 = QtGui.QHBoxLayout()

        self.refresh_vectors_button = QtGui.QPushButton("Refresh Vectors")
        self.refresh_vectors_button.clicked.connect(self._on_refresh_vectors)
        btn_layout1.addWidget(self.refresh_vectors_button)

        self.apply_vectors_button = QtGui.QPushButton("Apply LEN")
        self.apply_vectors_button.clicked.connect(self._on_apply_vectors)
        btn_layout1.addWidget(self.apply_vectors_button)

        self.vectors_layout.addLayout(btn_layout1)

        btn_layout2 = QtGui.QHBoxLayout()

        self.add_vector_button = QtGui.QPushButton("Add Vector")
        self.add_vector_button.clicked.connect(self._on_add_vector)
        btn_layout2.addWidget(self.add_vector_button)

        self.remove_vector_button = QtGui.QPushButton("Remove Last Vector")
        self.remove_vector_button.clicked.connect(self._on_remove_last_vector)
        btn_layout2.addWidget(self.remove_vector_button)

        self.vectors_layout.addLayout(btn_layout2)

        hint = QtGui.QLabel(
            "Double-click on LEN to edit.\n"
            "DIR - read-only.\n"
            "'Add Vector' - adds to the end of the route.\n"
            "'Remove Last Vector' - only the last one.\n"
            "Segment overlap is forbidden."
        )
        hint.setStyleSheet("color: #777; font-size: 10px;")
        self.vectors_layout.addWidget(hint)

    def _on_refresh_vectors(self):
        self._update_vectors_from_points()
        self._refresh_vectors_table()
        App.Console.PrintMessage("Vectors refreshed from coordinates.\n")

    def _on_apply_vectors(self):
        self._apply_vectors_to_points()
        App.Console.PrintMessage("Coordinates recalculated from vectors.\n")

    def _build_attachment_tab(self):
        title = QtGui.QLabel("Attachment to Geometry")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.attach_layout.addWidget(title)

        self.attach_status = QtGui.QLabel("Not attached (0, 0, 0)")
        self.attach_status.setStyleSheet("color: #c0392b; font-style: italic;")
        self.attach_layout.addWidget(self.attach_status)

        self.selected_vertex_label = QtGui.QLabel("Selected: —")
        self.selected_vertex_label.setStyleSheet(
            "color: #2980b9; font-weight: bold; font-size: 12px;"
        )
        self.attach_layout.addWidget(self.selected_vertex_label)

        coord_layout = QtGui.QFormLayout()
        self.attach_x = QtGui.QLabel("0.00")
        self.attach_y = QtGui.QLabel("0.00")
        self.attach_z = QtGui.QLabel("0.00")
        coord_layout.addRow("X:", self.attach_x)
        coord_layout.addRow("Y:", self.attach_y)
        coord_layout.addRow("Z:", self.attach_z)
        self.attach_layout.addLayout(coord_layout)

        self.pick_button = QtGui.QPushButton("Change Attachment")
        self.pick_button.clicked.connect(self.pick_attachment)
        self.attach_layout.addWidget(self.pick_button)

        self.reset_attach_button = QtGui.QPushButton("Reset Attachment")
        self.reset_attach_button.clicked.connect(self.reset_attachment)
        self.attach_layout.addWidget(self.reset_attach_button)

        hint = QtGui.QLabel(
            "How to attach:\n"
            "1. Select a vertex, edge, or face in 3D.\n"
            "2. Click 'Change Attachment'.\n"
            "\n"
            "Position:\n"
            "  Vertex - point.\n"
            "  Edge - midpoint.\n"
            "  Face - center of mass.\n"
            "\n"
            "Green marker - current attachment.\n"
            "Blue marker - preliminary selection."
        )
        hint.setStyleSheet("color: #777; font-size: 10px;")
        self.attach_layout.addWidget(hint)

        self.attach_layout.addStretch()

    def _update_attach_marker(self):
        doc = App.ActiveDocument

        old = doc.getObject("_AttachmentMarker")
        if old:
            doc.removeObject("_AttachmentMarker")

        if not self.obj.AttachmentSupport:
            self._attach_marker = None
            return

        try:
            pos = self.obj.AttachmentPosition
        except Exception:
            self._attach_marker = None
            return

        marker = doc.addObject("Part::Feature", "_AttachmentMarker")
        marker.Shape = Part.Vertex(pos)
        marker.ViewObject.PointSize = 100.0
        marker.ViewObject.PointColor = (0.0, 1.0, 0.0)
        self._attach_marker = marker
        doc.recompute()

    def refresh_attachment_info(self):
        if not self.obj.AttachmentSupport:
            self.attach_status.setText("Not attached (0, 0, 0)")
            self.attach_status.setStyleSheet("color: #c0392b; font-style: italic;")
            self.selected_vertex_label.setText("Selected: —")
            self.selected_vertex_label.setStyleSheet(
                "color: #2980b9; font-weight: bold; font-size: 12px;"
            )
            self.attach_x.setText("0.00")
            self.attach_y.setText("0.00")
            self.attach_z.setText("0.00")
            self._update_attach_marker()
            return

        try:
            support_obj, sub_elements = self.obj.AttachmentSupport
            if not support_obj:
                self.attach_status.setText("Attachment lost")
                self.attach_status.setStyleSheet("color: #c0392b; font-weight: bold;")
                self.selected_vertex_label.setText("Selected: —")
                return

            sub_name = ""
            if sub_elements:
                if isinstance(sub_elements, (list, tuple)):
                    sub_name = sub_elements[0] if sub_elements else ""
                else:
                    sub_name = str(sub_elements)

            obj_label = support_obj.Label
            sub_label = sub_name

            type_label = self._sub_type_label(sub_label)
            if type_label:
                text = f"Attached to: {obj_label}.{sub_label} ({type_label})"
            else:
                text = f"Attached to: {obj_label}.{sub_label}"
            self.attach_status.setText(text)
            self.attach_status.setStyleSheet("color: #27ae60; font-weight: bold;")

            self.selected_vertex_label.setText(
                f"Selected: {obj_label}.{sub_label}"
            )
            self.selected_vertex_label.setStyleSheet(
                "color: #2980b9; font-weight: bold; font-size: 12px;"
            )

            pos = self.obj.AttachmentPosition
            self.attach_x.setText(f"{pos.x:.2f}")
            self.attach_y.setText(f"{pos.y:.2f}")
            self.attach_z.setText(f"{pos.z:.2f}")

        except Exception as e:
            self.attach_status.setText(f"Error: {e}")
            self.attach_status.setStyleSheet("color: #c0392b; font-weight: bold;")

        self._update_attach_marker()

    def pick_attachment(self):
        selection = Gui.Selection.getSelectionEx()

        if not selection:
            App.Console.PrintWarning("Nothing selected. Select in 3D.\n")
            self.attach_status.setText("Nothing selected")
            self.attach_status.setStyleSheet("color: #c0392b; font-weight: bold;")
            return

        sel = selection[0]
        sub_names = sel.SubElementNames

        if not sub_names:
            App.Console.PrintWarning("Whole object selected. Select a sub-element.\n")
            self.attach_status.setText("Select a vertex, edge, or face")
            self.attach_status.setStyleSheet("color: #c0392b; font-weight: bold;")
            return

        target_name = None
        for name in sub_names:
            if (name.startswith("Vertex") or
                name.startswith("Edge") or
                name.startswith("Face")):
                target_name = name
                break

        if not target_name:
            App.Console.PrintWarning(
                f"Selected element '{sub_names[0]}'. Select a vertex, edge, or face.\n"
            )
            self.attach_status.setText(f"Unknown type: {sub_names[0]}")
            self.attach_status.setStyleSheet("color: #c0392b; font-weight: bold;")
            return

        self.obj.AttachmentSupport = (sel.Object, target_name)
        App.ActiveDocument.recompute()

        self.refresh_attachment_info()
        App.Console.PrintMessage(f"Attached to: {sel.Object.Label}.{target_name}\n")

    def reset_attachment(self):
        self.obj.AttachmentSupport = None
        App.ActiveDocument.recompute()
        self.refresh_attachment_info()
        App.Console.PrintMessage("Attachment reset (0, 0, 0).\n")

    def create_phantom(self):
        if self.phantom:
            return
        doc = App.ActiveDocument
        self.phantom = doc.addObject("Part::Feature", "_PhantomRay")
        self.phantom.ViewObject.LineWidth = 3.0

    def update_phantom(self):
        if not self.phantom:
            self.create_phantom()

        last_point = self.get_last_point()
        if last_point is None:
            last_point = (0.0, 0.0, 0.0)

        axis = self.axis_combo.currentText()
        length = self.length_input.value()

        dx = dy = dz = 0.0
        if axis == "+X":
            dx = length
        elif axis == "-X":
            dx = -length
        elif axis == "+Y":
            dy = length
        elif axis == "-Y":
            dy = -length
        elif axis == "+Z":
            dz = length
        elif axis == "-Z":
            dz = -length

        start = App.Vector(*last_point)
        end = App.Vector(last_point[0] + dx, last_point[1] + dy, last_point[2] + dz)

        target_exists = self.point_exists((end.x, end.y, end.z))
        overlap = self._check_vector_overlap(axis, length)

        line = Part.makeLine(start, end)
        self.phantom.Shape = line

        if "X" in axis:
            color = (1.0, 0.0, 0.0)
        elif "Y" in axis:
            color = (0.0, 1.0, 0.0)
        else:
            color = (0.0, 0.0, 1.0)

        if target_exists or overlap:
            color = tuple(c * 0.3 for c in color)

        self.phantom.ViewObject.LineColor = color

        if target_exists:
            self.add_button.setEnabled(False)
            self.add_button.setText("Point already exists")
            self.add_button.setStyleSheet("background-color: #ffcccc;")
        elif overlap:
            self.add_button.setEnabled(False)
            self.add_button.setText("Overlap - fix")
            self.add_button.setStyleSheet("background-color: #ffcccc;")
        else:
            self.add_button.setEnabled(True)
            self.add_button.setText("Add Segment")
            self.add_button.setStyleSheet("")

        App.ActiveDocument.recompute()

    def remove_phantom(self):
        if self.phantom:
            doc = App.ActiveDocument
            doc.removeObject(self.phantom.Name)
            self.phantom = None
            App.ActiveDocument.recompute()

    def update_info(self):
        last_point = self.get_last_point()
        if last_point:
            self.info_label.setText(
                f"Last point: X={last_point[0]:.2f}, Y={last_point[1]:.2f}, Z={last_point[2]:.2f}"
            )
        else:
            self.info_label.setText("Last point: — (table empty)")

    def get_last_point(self):
        sheet = self.obj.Spreadsheet
        if not sheet:
            return None

        last = None
        row = 1
        while True:
            try:
                x = sheet.get("A" + str(row))
                y = sheet.get("B" + str(row))
                z = sheet.get("C" + str(row))
            except ValueError:
                break
            if x is None or y is None or z is None:
                break
            last = (x, y, z)
            row += 1
        return last

    def point_exists(self, point, tolerance=1e-6):
        sheet = self.obj.Spreadsheet
        if not sheet:
            return False

        row = 1
        while True:
            try:
                x = sheet.get("A" + str(row))
                y = sheet.get("B" + str(row))
                z = sheet.get("C" + str(row))
            except ValueError:
                break
            if x is None or y is None or z is None:
                break
            if (abs(x - point[0]) < tolerance and
                abs(y - point[1]) < tolerance and
                abs(z - point[2]) < tolerance):
                return True
            row += 1
        return False

    def add_segment(self):
        sheet = self.obj.Spreadsheet
        if not sheet:
            App.Console.PrintError("Table not linked to object.\n")
            return

        last_point = self.get_last_point()
        if last_point is None:
            last_point = (0.0, 0.0, 0.0)

        axis = self.axis_combo.currentText()
        length = self.length_input.value()

        dx = dy = dz = 0.0
        if axis == "+X":
            dx = length
        elif axis == "-X":
            dx = -length
        elif axis == "+Y":
            dy = length
        elif axis == "-Y":
            dy = -length
        elif axis == "+Z":
            dz = length
        elif axis == "-Z":
            dz = -length

        new_point = (last_point[0] + dx, last_point[1] + dy, last_point[2] + dz)

        if self.point_exists(new_point):
            App.Console.PrintWarning(
                f"Point ({new_point[0]:.2f}, {new_point[1]:.2f}, {new_point[2]:.2f}) already exists. "
                f"Segment not added.\n"
            )
            return

        if self._check_vector_overlap(axis, length):
            QtGui.QMessageBox.warning(
                None,
                "Overlap",
                f"Vector {axis} {length} mm creates an overlap.\n"
                f"Segment not added."
            )
            return

        row = 1
        while True:
            try:
                sheet.get("A" + str(row))
                row += 1
            except ValueError:
                break

        sheet.set("A" + str(row), str(new_point[0]))
        sheet.set("B" + str(row), str(new_point[1]))
        sheet.set("C" + str(row), str(new_point[2]))

        doc = App.ActiveDocument
        sheet_v = doc.getObject("Spreadsheet_Vectors")
        if sheet_v:
            row_v = row
            sheet_v.set("A" + str(row_v), axis)
            sheet_v.set("B" + str(row_v), str(length))

        doc.recompute()
        self.update_info()
        self.update_phantom()
        self.refresh_points_table()
        if sheet_v:
            self._refresh_vectors_table()

        App.Console.PrintMessage(
            f"Segment added: {axis} {length} mm -> point ({new_point[0]:.2f}, {new_point[1]:.2f}, {new_point[2]:.2f})\n"
        )

    def remove_last_segment(self):
        sheet = self.obj.Spreadsheet
        if not sheet:
            return

        last_row = 1
        row = 1
        while True:
            try:
                x = sheet.get("A" + str(row))
                if x is not None and x != "":
                    last_row = row
                    row += 1
                else:
                    break
            except ValueError:
                break

        if last_row <= 1:
            App.Console.PrintWarning("Nothing to delete: table has only the start point.\n")
            return

        sheet.clear("A" + str(last_row))
        sheet.clear("B" + str(last_row))
        sheet.clear("C" + str(last_row))

        doc = App.ActiveDocument
        sheet_v = doc.getObject("Spreadsheet_Vectors")
        if sheet_v:
            sheet_v.clear("A" + str(last_row))
            sheet_v.clear("B" + str(last_row))

        doc.recompute()
        self.update_info()
        self.update_phantom()
        self.refresh_points_table()
        if sheet_v:
            self._refresh_vectors_table()

        App.Console.PrintMessage(f"Last segment removed (row {last_row}).\n")

    def getStandardButtons(self):
        return QtGui.QDialogButtonBox.Close

    def _cleanup(self):
        self.remove_phantom()
        self._remove_marker()
        self._remove_highlight()
        try:
            self._selection_timer.stop()
        except Exception:
            pass
        try:
            self._zoom_timer.stop()
        except Exception:
            pass
        doc = App.ActiveDocument
        for name in ("_AttachmentMarker", "_NewVertexMarker"):
            old = doc.getObject(name)
            if old:
                doc.removeObject(name)
        self._attach_marker = None
        self._new_marker = None
        self._selected_vertex_key = None

        if self._check_all_overlaps():
            App.Console.PrintWarning(
                "Segment overlap detected on panel close!\n"
            )

        try:
            Gui.Selection.removeSelectionGate()
            App.Console.PrintMessage("Selection filter removed.\n")
        except Exception:
            pass
        for sc in self.shortcuts:
            sc.setEnabled(False)
            sc.deleteLater()
        self.shortcuts = []

    def reject(self):
        self._cleanup()
        Gui.Control.closeDialog()
        return True

    def accept(self):
        self._cleanup()
        Gui.Control.closeDialog()
        return True
