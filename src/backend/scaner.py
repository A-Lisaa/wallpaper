import imghdr
import os
import re
import shutil
import sqlite3
import statistics
import time
from collections.abc import Callable
from queue import Queue
from threading import Lock, Thread
from typing import Any, Iterable

from colormath.color_conversions import \
    convert_color as colormath_convert_color
from colormath.color_diff import (delta_e_cie1976, delta_e_cie1994,
                                  delta_e_cie2000, delta_e_cmc)
from colormath.color_objects import LabColor, sRGBColor
from PIL import Image, ImageFile, UnidentifiedImageError
# pylint: disable=no-name-in-module, attribute-defined-outside-init
from PyQt6.QtCore import QObject, pyqtSignal

from ..utils.md5 import get_file_md5

ImageFile.LOAD_TRUNCATED_IMAGES = True
lock = Lock()

class Scaner(QObject):
    initialized = pyqtSignal(int)
    message_signal = pyqtSignal(str)
    image_scanned_signal = pyqtSignal(int)

    def get_color_algorithm(self, index: int) -> Callable[[LabColor, LabColor], float]:
        algorithms = {
            0: delta_e_cie1976,
            1: delta_e_cmc,
            2: delta_e_cie1994,
            3: delta_e_cie2000
        }
        return algorithms[index]

    def get_prevailing_color(self, colors: Iterable[tuple[int, int, int]]) -> LabColor:
        modes = tuple(zip(*statistics.multimode(colors)))

        red = sum(modes[0]) // len(modes[0])
        green = sum(modes[1]) // len(modes[1])
        blue = sum(modes[2]) // len(modes[2])

        return colormath_convert_color(sRGBColor(red, green, blue, is_upscaled=True), LabColor)

    def get_vertical_line_prevailing_color(self, img: Image.Image, pixel_x_pos: int) -> LabColor:
        colors = (
            img.getpixel((pixel_x_pos, pixel_y_pos))
            for pixel_y_pos in range(0, img.height-1, self.settings["pixel_scan_frequency"])
        )

        return self.get_prevailing_color(colors)

    def get_vertical_line_deviation(self, img: Image.Image, mode_lab_color: LabColor, pixel_x_pos: int) -> float:
        deviation = 0
        for pixel_y_pos in range(0, img.height-1, self.settings["pixel_scan_frequency"]):
            red, green, blue = img.getpixel((pixel_x_pos, pixel_y_pos))[:3]
            rgb_color = sRGBColor(red, green, blue, is_upscaled=True)
            lab_pixel_color = colormath_convert_color(rgb_color, LabColor)
            deviation += self.settings["color_algorithm"](mode_lab_color, lab_pixel_color)

        return deviation/(img.height/self.settings["pixel_scan_frequency"])

    def get_edges_deviations(self, img: Image.Image) -> tuple[float, float]:
        # TODO: В случае градиентного фона распознавания не будет, вариант - отслеживание резкости изменения фона
        img = img.crop(
            (
                0,
                int(img.height*self.settings["top_crop"]),
                img.width,
                int(img.height*(1 - self.settings["bottom_crop"]))
            )
        )

        left_edge_mode_lab_color = self.get_vertical_line_prevailing_color(img, 0)
        right_edge_mode_lab_color = self.get_vertical_line_prevailing_color(img, img.width-1)
        deviation_left = self.get_vertical_line_deviation(img, left_edge_mode_lab_color, 0)
        deviation_right = self.get_vertical_line_deviation(img, right_edge_mode_lab_color, img.width-1)

        return deviation_left, deviation_right

    def run_thread(self):
        while not self.pics_queue.empty():
            filename = self.pics_queue.get()
            md5 = get_file_md5(filename)
            if md5 in self.existing_md5s:
                self.pics_queue.task_done()
                self.images_scanned += 1
                self.image_scanned_signal.emit(self.images_scanned)
                continue

            try:
                img = Image.open(filename)
            except UnidentifiedImageError:
                self.pics_queue.task_done()
                self.images_scanned += 1
                self.image_scanned_signal.emit(self.images_scanned)
                continue

            left_deviation, right_deviation = self.get_edges_deviations(img.convert("RGBA"))

            addition_date = time.strftime("%d-%m-%Y")
            addition_time = time.strftime("%H:%M:%S")

            values = (
                md5, filename,
                img.width, img.height,
                self.settings["top_crop"], self.settings["bottom_crop"],
                left_deviation, right_deviation,
                self.settings["color_algorithm"].__name__,
                self.settings["pixel_scan_frequency"],
                addition_date, addition_time
            )
            try:
                lock.acquire(True)
                self.cursor.execute("INSERT INTO pictures VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);", values)
                self.connection.commit()
            finally:
                lock.release()

            self.pics_queue.task_done()

            self.images_scanned += 1
            self.image_scanned_signal.emit(self.images_scanned)

    def __init__(self):
        super().__init__()
        self.settings: dict[str, Any] = {}

    def copy_file(self, filename: str, dest_folder: str = os.getcwd(), maximum_copies_amount: int = 3):
        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)

        existing_copies = []
        for _, _, folder_files in os.walk(dest_folder):
            for folder_file in folder_files:
                if re.match(rf"{os.path.splitext(filename)[0]}_copy\d{os.path.splitext(filename)[1]}", folder_file):
                    existing_copies.append(folder_file)
            break

        if len(existing_copies) > maximum_copies_amount:
            return 0

        copy_filename = f"{os.path.splitext(filename)[0]}_copy{len(existing_copies)-1}.{os.path.splitext(filename)[1]}"

        os.rename(filename, copy_filename)
        shutil.copy2(copy_filename, dest_folder)
        os.rename(copy_filename, filename)

    def run(self):
        self.images_scanned = 0

        self.settings["color_algorithm"] = self.get_color_algorithm(self.settings["color_algorithm"])
        self.connection = sqlite3.connect(f"./{self.settings['db_name']}.db", check_same_thread=False)
        self.cursor = self.connection.cursor()
        self.pics_queue: Queue[str] = Queue()

        self.cursor.execute(
            """
                CREATE TABLE IF NOT EXISTS pictures(
                    md5 TEXT PRIMARY KEY,
                    path TEXT,

                    width INT,
                    height INT,

                    top_crop REAL,
                    bottom_crop REAL,

                    left_deviation REAL,
                    right_deviation REAL,

                    comparison_function TEXT,

                    pixel_scan_frequency INT,

                    addition_date TEXT,
                    addition_time TEXT
                );
            """
        )
        self.connection.commit()

        self.cursor.execute("SELECT md5 FROM pictures;")
        self.existing_md5s = tuple(file[0] for file in self.cursor.fetchall())

        for path, _, files in os.walk(self.settings["scan_folder"]):
            for name in files:
                fpath = os.path.join(path, name)
                self.pics_queue.put(fpath)

        self.initialized.emit(self.pics_queue.qsize())

        threads_amount = min(self.settings["threads_amount"], self.pics_queue.qsize())

        for _ in range(threads_amount):
            thread = Thread(target=self.run_thread)
            thread.start()
