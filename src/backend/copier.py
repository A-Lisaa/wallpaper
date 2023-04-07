import os
import shutil
import sqlite3
from typing import Any

# pylint: disable=no-name-in-module, attribute-defined-outside-init
from PyQt6.QtCore import QObject, pyqtSignal


class Copier(QObject):
    initialized_signal = pyqtSignal(int)
    message_signal = pyqtSignal(str)
    image_checked_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.settings: dict[str, Any] = {}

    def run(self):
        self.images_checked = 0
        w = int(self.settings["sides_ratio"].split("x")[0].strip())
        h = int(self.settings["sides_ratio"].split("x")[1].strip())
        whratio = w / h
        whratio_deviation = int(self.settings["whratio_deviation"].split("%")[0])/100
        minimum_ratio = whratio*(1 - (whratio_deviation))
        maximum_ratio = whratio*(whratio_deviation)

        self.connection = sqlite3.connect(f"./{self.settings['copier_db_name']}.db", check_same_thread=False)
        self.cursor = self.connection.cursor()

        self.cursor.execute("SELECT COUNT(md5) FROM pictures;")
        self.initialized_signal.emit(self.cursor.fetchone()[0])

        self.cursor.execute("SELECT path, width, height, left_deviation, right_deviation FROM pictures;")
        for path, width, height, left_deviation, right_deviation in self.cursor.fetchall():
            image_whratio = width / height
            if (
                width > self.settings["minimum_width"] and
                height > self.settings["minimum_height"] and
                (
                    (
                        left_deviation < self.settings["maximum_deviation"] and
                        right_deviation < self.settings["maximum_deviation"]
                    ) or
                    minimum_ratio < image_whratio < maximum_ratio
                )
            ):
                if not os.path.exists(path):
                    self.message_signal.emit(f"Could not find file {path}\n")
                    continue
                shutil.copy(path, f"{self.settings['result_copy_folder']}/{os.path.split(path)[1]}")
            self.images_checked += 1
            self.image_checked_signal.emit(self.images_checked)
