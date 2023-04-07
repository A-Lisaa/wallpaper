import os
import sys

# pylint: disable=no-name-in-module
from PyQt6.QtCore import QThread, pyqtSlot
from PyQt6.QtGui import QDoubleValidator, QIntValidator
from PyQt6.QtWidgets import QApplication, QFileDialog, QMainWindow

from ..backend.copier import Copier
from ..backend.scaner import Scaner
from ..utils.files_IO import read_json_file, write_json_file
from ..utils.logger import get_logger
from .ui_main_window import Ui_MainWindow

_logger = get_logger(__file__)


class MainWindow(Ui_MainWindow, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.settings = {}
        self.settings_path = "./settings.json"

        self.folder_dialog = QFileDialog(caption="Выберите папку", directory="/")
        self.folder_dialog.setFileMode(QFileDialog.FileMode.Directory)
        self.folder_dialog.setOption(QFileDialog.Option.ShowDirsOnly)


        ##############################################################################
        # Scaner setup
        ##############################################################################

        self.scanStartButton.pressed.connect(self.run_scaner)

        self.topCropLineEdit.setValidator(QDoubleValidator())
        self.bottomCropLineEdit.setValidator(QDoubleValidator())
        self.threadsAmountLineEdit.setValidator(QIntValidator())
        self.pixelScanFrequencyLineEdit.setValidator(QIntValidator())

        self.scaner = Scaner()
        self.scaner_thread = QThread()
        self.scaner.moveToThread(self.scaner_thread)
        self.scaner_thread.started.connect(self.scaner.run)

        @pyqtSlot()
        def scan_folder_button():
            directory = self.folder_dialog.getExistingDirectory()
            if directory != "":
                self.scanFolderLineEdit.setText(directory)
        self.scanFolderButton.pressed.connect(scan_folder_button)

        @pyqtSlot(int)
        def update_scaner_progress(value):
            self.scanProgressBar.setValue(value)
        self.scaner.image_scanned_signal.connect(update_scaner_progress)

        @pyqtSlot(int)
        def update_scaner_progress_maximum(value):
            self.scanProgressBar.setMaximum(value)
        self.scaner.initialized_signal.connect(update_scaner_progress_maximum)

        @pyqtSlot(str)
        def show_scaner_message(message):
            self.scanerOutputField.insertPlainText(message)
        self.scaner.message_signal.connect(show_scaner_message)


        ##############################################################################
        # Copier setup
        ##############################################################################

        self.copyStartButton.pressed.connect(self.run_copier)

        self.maximumDeviationLineEdit.setValidator(QIntValidator())
        self.minimumWidthLineEdit.setValidator(QIntValidator())
        self.minimumHeightLineEdit.setValidator(QIntValidator())

        self.copier = Copier()
        self.copier_thread = QThread()
        self.copier.moveToThread(self.copier_thread)
        self.copier_thread.started.connect(self.copier.run)

        @pyqtSlot()
        def copy_folder_button():
            directory = self.folder_dialog.getExistingDirectory()
            if directory != "":
                self.resultCopyFolderLineEdit.setText(directory)
        self.resultCopyFolderButton.pressed.connect(copy_folder_button)

        @pyqtSlot(int)
        def update_copy_progress(value):
            self.copyProgressBar.setValue(value)
        self.copier.image_checked_signal.connect(update_copy_progress)

        @pyqtSlot(int)
        def update_copy_progress_maximum(value):
            self.copyProgressBar.setMaximum(value)
        self.copier.initialized_signal.connect(update_copy_progress_maximum)

        @pyqtSlot(str)
        def show_copier_message(message):
            self.copyOutputField.insertPlainText(message)
        self.copier.message_signal.connect(show_copier_message)

    def update_settings(self):
        self.settings["scan_folder"] = self.scanFolderLineEdit.text()
        self.settings["scan_folder_subfolders"] = self.scanFolderSubfoldersCheckBox.isChecked()
        self.settings["color_algorithm"] = self.colorAlgorithmComboBox.currentIndex()
        self.settings["db_name"] = self.dbNameLineEdit.text()
        self.settings["top_crop"] = float(self.topCropLineEdit.text())
        self.settings["bottom_crop"] = float(self.bottomCropLineEdit.text())
        self.settings["pixel_scan_frequency"] = int(self.pixelScanFrequencyLineEdit.text())
        self.settings["threads_amount"] = int(self.threadsAmountLineEdit.text())

        self.settings["result_copy_folder"] = self.resultCopyFolderLineEdit.text()
        self.settings["copier_db_name"] = self.dbNameCopierLineEdit.text()
        self.settings["sides_ratio"] = self.sidesRelationLineEdit.text()
        self.settings["whratio_deviation"] = self.sidesRelationDeviationLineEdit.text()
        self.settings["minimum_width"] = int(self.minimumWidthLineEdit.text())
        self.settings["minimum_height"] = int(self.minimumHeightLineEdit.text())
        self.settings["maximum_deviation"] = int(self.maximumDeviationLineEdit.text())

        write_json_file(self.settings, self.settings_path)

    def retrieve_settings(self):
        if not os.path.exists(self.settings_path):
            return

        self.settings: dict = read_json_file(self.settings_path)

        self.scanFolderLineEdit.setText(self.settings.get("scan_folder", ""))
        self.scanFolderSubfoldersCheckBox.setChecked(self.settings.get("scan_folder_subfolders", False))
        self.colorAlgorithmComboBox.setCurrentIndex(self.settings.get("color_algorithm", 3))
        self.dbNameLineEdit.setText(self.settings.get("db_name", "wallpaper"))
        self.topCropLineEdit.setText(str(self.settings.get("top_crop", 0.1)))
        self.bottomCropLineEdit.setText(str(self.settings.get("bottom_crop", 0.1)))
        self.pixelScanFrequencyLineEdit.setText(str(self.settings.get("pixel_scan_frequency", 2)))
        self.threadsAmountLineEdit.setText(str(self.settings.get("threads_amount", 12)))

        self.resultCopyFolderLineEdit.setText(self.settings.get("result_copy_folder", ""))
        self.dbNameCopierLineEdit.setText(self.settings.get("copier_db_name", "wallpaper"))
        self.sidesRelationLineEdit.setText(self.settings.get("sides_ratio", "16x9"))
        self.sidesRelationDeviationLineEdit.setText(self.settings.get("whratio_deviation", "10%"))
        self.minimumWidthLineEdit.setText(str(self.settings.get("minimum_width", 0)))
        self.minimumHeightLineEdit.setText(str(self.settings.get("minimum_height", 0)))
        self.maximumDeviationLineEdit.setText(str(self.settings.get("maximum_deviation", 5)))

    def show(self):
        self.retrieve_settings()
        super().show()

    def run_scaner(self):
        self.scanStartButton.setEnabled(False)
        self.update_settings()
        self.scaner.settings = self.settings
        self.scaner_thread.start()

    def run_copier(self):
        self.scanStartButton.setEnabled(False)
        self.update_settings()
        self.copier.settings = self.settings
        self.copier_thread.start()

def start_ui():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
