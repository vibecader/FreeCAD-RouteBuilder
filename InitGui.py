# Parametric Wire Workbench by KorneyCAD
# Copyright (C) 2026 KorneyCAD
# Contact: korney92d1@yandex.ru
# SPDX-License-Identifier: LGPL-2.1-or-later

import os
import FreeCAD as App
import FreeCADGui as Gui
from FreeCADGui import Workbench


class ParametricWireWorkbench(Workbench):
    MenuText = "Parametric Wire"
    ToolTip = "Параметрические полилинии, тела и экспорт"
    Icon = "/home/andrei/.local/share/FreeCAD/v26-3/Mod/ParametricWireWB/Icons/WorkbenchIcon.svg"

    def Initialize(self):
        self.list = [
            "CreateParametricWire",
            "EditParametricWire",
            "CreatePipeByTrajectory",
            "ExportToStep"
        ]
        self.appendToolbar("Parametric Wire", self.list)
        self.appendMenu("Parametric Wire", self.list)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


class CreateParametricWireCommand:
    def GetResources(self):
        icon = os.path.join(
            App.getUserAppDataDir(), "Mod", "ParametricWireWB", "Icons", "CreateWire.svg"
        )
        return {
            "Pixmap": icon,
            "MenuText": "Создать Parametric Wire",
            "ToolTip": "Создать полилинию из таблицы Spreadsheet"
        }

    def Activated(self):
        try:
            from PySide import QtGui
        except ImportError:
            from PySide6 import QtGui

        import ParametricWire_core as PW
        import ParametricWireTaskPanel as Panel

        doc = App.ActiveDocument
        if not doc:
            App.Console.PrintError("Нет активного документа.\n")
            return

        sheets = [obj for obj in doc.Objects if obj.TypeId == "Spreadsheet::Sheet"]
        selected_sheet_name = None

        if not sheets:
            new_sheet = doc.addObject("Spreadsheet::Sheet", "Spreadsheet")
            new_sheet.set("A1", "0")
            new_sheet.set("B1", "0")
            new_sheet.set("C1", "0")
            doc.recompute()
            selected_sheet_name = new_sheet.Name
        elif len(sheets) == 1:
            selected_sheet_name = sheets[0].Name
        else:
            sheet_names = [sheet.Name for sheet in sheets]
            sheet_labels = [f"{sheet.Label} ({sheet.Name})" for sheet in sheets]
            selected_label, ok = QtGui.QInputDialog.getItem(
                None, "Выбор таблицы", "Выберите таблицу с координатами:",
                sheet_labels, 0, False
            )
            if not ok:
                return
            index = sheet_labels.index(selected_label)
            selected_sheet_name = sheet_names[index]

        obj = PW.create_parametric_wire(selected_sheet_name, 1)
        if obj:
            panel = Panel.ParametricWireTaskPanel(obj)
            Gui.Control.showDialog(panel)

    def IsActive(self):
        return App.ActiveDocument is not None


class EditParametricWireCommand:
    def GetResources(self):
        icon = os.path.join(
            App.getUserAppDataDir(), "Mod", "ParametricWireWB", "Icons", "EditWire.svg"
        )
        return {
            "Pixmap": icon,
            "MenuText": "Редактировать Parametric Wire",
            "ToolTip": "Открыть панель-компас для существующей линии"
        }

    def Activated(self):
        try:
            from PySide import QtGui
        except ImportError:
            from PySide6 import QtGui

        import ParametricWireTaskPanel as Panel

        doc = App.ActiveDocument
        if not doc:
            return

        wires = [obj for obj in doc.Objects if obj.TypeId == "Part::FeaturePython"
                 and hasattr(obj, "Spreadsheet")]

        if not wires:
            App.Console.PrintError("В документе нет объектов ParametricWire.\n")
            return

        if len(wires) == 1:
            obj = wires[0]
        else:
            wire_labels = [f"{w.Label} ({w.Name})" for w in wires]
            selected, ok = QtGui.QInputDialog.getItem(
                None, "Выбор линии", "Выберите Parametric Wire для редактирования:",
                wire_labels, 0, False
            )
            if not ok:
                return
            index = wire_labels.index(selected)
            obj = wires[index]

        panel = Panel.ParametricWireTaskPanel(obj)
        Gui.Control.showDialog(panel)

    def IsActive(self):
        doc = App.ActiveDocument
        if not doc:
            return False
        wires = [obj for obj in doc.Objects if obj.TypeId == "Part::FeaturePython"
                 and hasattr(obj, "Spreadsheet")]
        return len(wires) > 0


class CreatePipeByTrajectoryCommand:
    def GetResources(self):
        icon = os.path.join(
            App.getUserAppDataDir(), "Mod", "ParametricWireWB", "Icons", "CreatePipe.svg"
        )
        return {
            "Pixmap": icon,
            "MenuText": "Создать тело по траектории",
            "ToolTip": "Создать тело, протянув профиль по Parametric Wire"
        }

    def Activated(self):
        import PipeCreator as PC
        PC.create_pipe_by_trajectory()

    def IsActive(self):
        doc = App.ActiveDocument
        if not doc:
            return False
        wires = [obj for obj in doc.Objects if obj.TypeId == "Part::FeaturePython"
                 and hasattr(obj, "Spreadsheet")]
        return len(wires) > 0


class ExportToStepCommand:
    def GetResources(self):
        icon = os.path.join(
            App.getUserAppDataDir(), "Mod", "ParametricWireWB", "Icons", "ExportStep.svg"
        )
        return {
            "Pixmap": icon,
            "MenuText": "Экспорт в STEP",
            "ToolTip": "Экспортировать тела в формат STEP"
        }

    def Activated(self):
        import StepExporter as SE
        SE.export_to_step()

    def IsActive(self):
        doc = App.ActiveDocument
        if not doc:
            return False
        bodies = [obj for obj in doc.Objects
                  if obj.TypeId in ("PartDesign::Body", "Part::Feature")
                  and obj.Shape and not obj.Shape.isNull()]
        return len(bodies) > 0


Gui.addCommand("CreateParametricWire", CreateParametricWireCommand())
Gui.addCommand("EditParametricWire", EditParametricWireCommand())
Gui.addCommand("CreatePipeByTrajectory", CreatePipeByTrajectoryCommand())
Gui.addCommand("ExportToStep", ExportToStepCommand())
Gui.addWorkbench(ParametricWireWorkbench())
