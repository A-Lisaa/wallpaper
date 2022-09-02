import os
import sys

# pylint: disable=no-name-in-module
from PyQt6.QtCore import QThread, pyqtSlot
from PyQt6.QtWidgets import QApplication, QMainWindow

from ..backend.scaner import Scaner
from ..utils.files_IO import read_json_file, write_json_file
from ..utils.logger import get_logger
from .main_window import Ui_MainWindow

_logger = get_logger(__file__)


class MainWindow(Ui_MainWindow, QMainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)

        self.scanStartButton.pressed.connect(self.run)

        self.settings = {}
        self.settings_path = "./settings.json"

        self.scanFolderLineEdit.textChanged.connect(self.update_settings)
        self.scanFolderSubfoldersCheckBox.stateChanged.connect(self.update_settings)
        self.colorAlgorithmComboBox.currentIndexChanged.connect(self.update_settings)
        self.dbNameLineEdit.textChanged.connect(self.update_settings)
        self.topCropLineEdit.textChanged.connect(self.update_settings)
        self.bottomCropLineEdit.textChanged.connect(self.update_settings)
        self.pixelScanFrequencyLineEdit.textChanged.connect(self.update_settings)
        self.threadsAmountLineEdit.textChanged.connect(self.update_settings)

        self.scaner = Scaner()
        self.scaner_thread = QThread()
        self.scaner.moveToThread(self.scaner_thread)
        self.scaner_thread.started.connect(self.scaner.run)

        @pyqtSlot(int)
        def update_scaner_progress(value):
            self.scanProgressBar.setValue(value)
        self.scaner.image_scanned_signal.connect(update_scaner_progress)

        @pyqtSlot(int)
        def update_scaner_progress_maximum(value):
            self.scanProgressBar.setMaximum(value)
        self.scaner.initialized.connect(update_scaner_progress_maximum)

        @pyqtSlot(str)
        def show_scaner_message(message):
            self.scanerOutputField.insertPlainText(message)
        self.scaner.message_signal.connect(show_scaner_message)

    def update_settings(self):
        self.settings["scan_folder"] = self.scanFolderLineEdit.text()
        self.settings["scan_folder_subfolders"] = self.scanFolderSubfoldersCheckBox.isChecked()
        self.settings["color_algorithm"] = self.colorAlgorithmComboBox.currentIndex()
        self.settings["db_name"] = self.dbNameLineEdit.text()
        self.settings["top_crop"] = float(self.topCropLineEdit.text())
        self.settings["bottom_crop"] = float(self.bottomCropLineEdit.text())
        self.settings["pixel_scan_frequency"] = int(self.pixelScanFrequencyLineEdit.text())
        self.settings["threads_amount"] = int(self.threadsAmountLineEdit.text())

        write_json_file(self.settings, self.settings_path)

    def retrieve_settings(self):
        if not os.path.exists(self.settings_path):
            return

        self.settings = read_json_file(self.settings_path)

        self.scanFolderLineEdit.setText(self.settings["scan_folder"])
        self.scanFolderSubfoldersCheckBox.setChecked(self.settings["scan_folder_subfolders"])
        self.colorAlgorithmComboBox.setCurrentIndex(self.settings["color_algorithm"])
        self.dbNameLineEdit.setText(self.settings["db_name"])
        self.topCropLineEdit.setText(str(self.settings["top_crop"]))
        self.bottomCropLineEdit.setText(str(self.settings["bottom_crop"]))
        self.pixelScanFrequencyLineEdit.setText(str(self.settings["pixel_scan_frequency"]))
        self.threadsAmountLineEdit.setText(str(self.settings["threads_amount"]))

    def show(self):
        self.retrieve_settings()
        super().show()

    def run(self):
        self.update_settings()
        self.scaner.settings = self.settings
        self.scanStartButton.setEnabled(False)
        self.scaner_thread.start()


def start_ui():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
