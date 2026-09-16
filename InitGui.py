# FreeCAD-RouteBuilder by VibeCADer
# Copyright (C) 2026 VibeCADer
# Contact: korney92d1@yandex.ru
# SPDX-License-Identifier: LGPL-2.1-or-later

import os
import FreeCAD as App
import FreeCADGui as Gui
from FreeCADGui import Workbench


class ParametricWireWorkbench(Workbench):
    MenuText = "Route Builder"
    ToolTip = "Parametric route builder, bodies and export"
    Icon = "/home/andrei/.local/share/FreeCAD/v26-3/Mod/ParametricWireWB/Icons/WorkbenchIcon.svg"

    def Initialize(self):
        self.list = [
            "CreateParametricWire",
            "EditParametricWire",
            "CreatePipeByTrajectory",
            "ExportToStep"
        ]
        self.appendToolbar("Route Builder", self.list)
        self.appendMenu("Route Builder", self.list)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


class CreateParametricWireCommand:
    def GetResources(self):
        icon = os.path.join(
            App.getUserAppDataDir(), "Mod", "ParametricWireWB", "Icons", "CreateWire.svg"
        )
        return {
            "Pixmap": icon,
            "MenuText": "Create Route",
            "ToolTip": "Create parametric route from Spreadsheet"
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
            App.Console.PrintError("No active document.\n")
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
                None, "Select table", "Select the table with coordinates:",
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
            "MenuText": "Edit Route",
            "ToolTip": "Open Builder panel for existing route"
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
            App.Console.PrintError("No ParametricWire objects in document.\n")
            return

        if len(wires) == 1:
            obj = wires[0]
        else:
            wire_labels = [f"{w.Label} ({w.Name})" for w in wires]
            selected, ok = QtGui.QInputDialog.getItem(
                None, "Select route", "Select Route Builder object to edit:",
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
            "MenuText": "Create Body by Trajectory",
            "ToolTip": "Create body by sweeping profile along the route"
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
            "MenuText": "Export to STEP",
            "ToolTip": "Export bodies to STEP format"
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
