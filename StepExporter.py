# FreeCAD-RouteBuilder by VibeCADer
# Copyright (C) 2026 VibeCADer
# Contact: korney92d1@yandex.ru
# SPDX-License-Identifier: LGPL-2.1-or-later

import FreeCAD as App
import FreeCADGui as Gui
import Part
import Import

try:
    from PySide import QtGui, QtCore
except ImportError:
    from PySide6 import QtGui, QtCore


def export_to_step():
    """Экспортирует выбранные тела в STEP-файл."""
    doc = App.ActiveDocument
    if not doc:
        App.Console.PrintError("Нет активного документа.\n")
        return

    # Ищем все Body и Part::Feature в документе
    bodies = [obj for obj in doc.Objects
              if obj.TypeId in ("PartDesign::Body", "Part::Feature")
              and obj.Shape
              and not obj.Shape.isNull()]

    if not bodies:
        App.Console.PrintError("В документе нет тел для экспорта.\n")
        return

    # Если тел несколько — показываем диалог выбора
    if len(bodies) == 1:
        selected_bodies = bodies
    else:
        labels = [f"{b.Label} ({b.Name})" for b in bodies]

        # Диалог с множественным выбором
        dlg = QtGui.QDialog()
        dlg.setWindowTitle("Экспорт в STEP")
        dlg.setMinimumWidth(400)

        layout = QtGui.QVBoxLayout(dlg)
        layout.addWidget(QtGui.QLabel("Выберите тела для экспорта:"))

        list_widget = QtGui.QListWidget()
        list_widget.setSelectionMode(QtGui.QAbstractItemView.MultiSelection)
        for label in labels:
            item = QtGui.QListWidgetItem(label)
            item.setSelected(True)  # По умолчанию — все выбраны
            list_widget.addItem(item)
        layout.addWidget(list_widget)

        buttons = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec_() != QtGui.QDialog.Accepted:
            return

        # Собираем выбранные тела
        selected_bodies = []
        for i, item in enumerate(list_widget.selectedItems()):
            index = list_widget.row(item)
            selected_bodies.append(bodies[index])

        if not selected_bodies:
            App.Console.PrintWarning("Ничего не выбрано.\n")
            return

    # Диалог сохранения файла
    file_path, _ = QtGui.QFileDialog.getSaveFileName(
        None,
        "Сохранить STEP-файл",
        "",
        "STEP Files (*.step *.stp);;All Files (*)"
    )

    if not file_path:
        return  # Пользователь отменил

    # Добавляем расширение, если не указано
    if not (file_path.lower().endswith(".step") or file_path.lower().endswith(".stp")):
        file_path += ".step"

    # Экспорт
    try:
        Import.export(selected_bodies, file_path)
        App.Console.PrintMessage(
            f"Экспортировано {len(selected_bodies)} тел(о) в: {file_path}\n"
        )
    except Exception as e:
        App.Console.PrintError(f"Ошибка экспорта: {e}\n")
