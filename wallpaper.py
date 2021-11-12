# -*- coding: utf-8 -*-
# pylint: disable = fixme, line-too-long, too-many-arguments, too-few-public-methods
import hashlib
import imghdr
import os
import queue
import re
import shutil
import sqlite3
import statistics
import time
from configparser import ConfigParser
from threading import Thread, active_count

from colormath.color_conversions import convert_color
from colormath.color_diff import delta_e_cie1976, delta_e_cie1994, delta_e_cie2000, delta_e_cmc
from colormath.color_objects import LabColor, sRGBColor
from PIL import Image

SETTINGS_PATH = "wallpaper.ini"


class Settings:
    @staticmethod
    def get_config_location(settings_path: str = SETTINGS_PATH) -> str:
        if not os.path.exists(settings_path):
            with open(settings_path, "w", encoding="utf-8"):
                pass

        return settings_path

    @staticmethod
    def get_config() -> ConfigParser:
        config = ConfigParser()
        config.read(Settings.get_config_location())

        return config

    @staticmethod
    def get_setting(section: str, setting: str):
        config = Settings.get_config()

        value = config.get(section, setting)

        return value

    @staticmethod
    def update_setting(section: str, setting: str, value: str | int | float | bool):
        config = Settings.get_config()

        if not config.has_section(section):
            config.add_section(section)
        config.set(section, setting, str(value))

        with open(Settings.get_config_location(), "w", encoding="utf-8") as config_file:
            config.write(config_file)


class MakeDB:
    class StartThread(Thread):
        def __init__(self,
                     thread_name: str, db_name: str, pics_queue: queue.Queue, pics_queue_start_size: int,
                     top_crop: float = 0.1, bottom_crop: float = 0.1,
                     pixel_group: int = 1, max_deviation: int = 5, chosen_algorithm: int = 0,
                     date_format: str = "%d.%m.%Y", time_format: str = "%H:%M:%S"
                     ):
            super().__init__()
            print(f"{thread_name} has been launched\n", end="")
            comparison_algorithms = (delta_e_cie1976,
                                     delta_e_cmc,
                                     delta_e_cie1994,
                                     delta_e_cie2000
                                     )

            # Mandatory args
            self.thread_name = thread_name
            self.conn = sqlite3.connect(db_name, check_same_thread=False)
            self.cur = self.conn.cursor()
            self.pics_queue = pics_queue
            self.pics_queue_start_size = pics_queue_start_size # if there are different sizes of queue for different threads, change it to a parameter

            # Optional args
            self.top_crop = top_crop
            self.bottom_crop = bottom_crop
            self.pixel_group = pixel_group
            self.max_deviation = max_deviation
            self.comparison_function = comparison_algorithms[chosen_algorithm]
            self.date_format = date_format
            self.time_format = time_format

        def get_file_md5(self, name: str) -> str:
            """
            Gets md5 of a file

            Args:
                name (str): path and name to the file

            Returns:
                str: md5 string of a file
            """
            hash_md5 = hashlib.md5()
            with open(name, "rb") as file:
                for chunk in iter(lambda: file.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()

        def calculate_frequent_color(self, colors: list[list | tuple] | tuple[list | tuple]) -> LabColor:
            modes = tuple(zip(*statistics.multimode(colors)))

            red = sum(modes[0]) / len(modes[0])
            green = sum(modes[1]) / len(modes[1])
            blue = sum(modes[2]) / len(modes[2])

            return convert_color(sRGBColor(red, green, blue), LabColor)

        def calculate_edges_frequent_colors(self, img: Image) -> tuple[LabColor, LabColor]:
            # ! gif colors and modes may not work correctly, but do we really need gifs?
            left_colors = []
            right_colors = []
            for pixel_height in range(0, img.height-1, self.pixel_group):
                left_colors.append(img.getpixel((0, pixel_height)))
                right_colors.append(img.getpixel((img.width-1, pixel_height)))

            return (self.calculate_frequent_color(left_colors),
                    self.calculate_frequent_color(right_colors))

        def comparison(self, img: Image, mode_lab_color: LabColor, pixel_x_pos: int) -> int:
            compared_pixels = 0
            for pixel_height in range(0, img.height-1, self.pixel_group):
                red, green, blue = img.getpixel((pixel_x_pos, pixel_height))[:3]
                lab_pixel_color = convert_color(sRGBColor(red, green, blue), LabColor)
                if self.comparison_function(lab_pixel_color, mode_lab_color) <= self.max_deviation:
                    compared_pixels += 1

            return compared_pixels

        def edges_mono_check(self, img: Image) -> float:
            # TODO: В случае градиентного фона распознавания не будет, вариант - отслеживание резкости изменения фона
            img = img.crop((0, img.height*self.top_crop, img.width, img.height*(1-self.bottom_crop)))

            mode_lab_color = self.calculate_edges_frequent_colors(img)
            coincident_left_pixels = self.comparison(img, mode_lab_color[0], 0)
            coincident_right_pixels = self.comparison(img, mode_lab_color[1], img.width-1)

            return (coincident_left_pixels+coincident_right_pixels)/(img.height*2/self.pixel_group)

        def run(self):
            while not self.pics_queue.empty():
                file = self.pics_queue.get()

                if imghdr.what(file):
                    img = Image.open(file)
                else:
                    continue

                md5 = self.get_file_md5(file)
                resolution = img.width/img.height

                monochrome = self.edges_mono_check(img.convert("RGBA"))

                addition_date = time.strftime(self.date_format)
                addition_time = time.strftime(self.time_format)

                values = (md5, file,
                          img.width, img.height, resolution,
                          self.top_crop, self.bottom_crop,
                          monochrome, self.comparison_function.__name__,
                          self.max_deviation, self.pixel_group,
                          addition_date, addition_time)
                self.cur.execute("INSERT INTO files VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);", values)
                self.conn.commit()
                print(f"{self.thread_name} CHECKED {file} ({self.pics_queue_start_size-self.pics_queue.unfinished_tasks+1}/{self.pics_queue_start_size} ({'%.2f' % (100-(self.pics_queue.unfinished_tasks-1)/self.pics_queue_start_size*100)}%))\n", end="")

                self.pics_queue.task_done()

    def __init__(self, db_name: str, db_path: str = os.getcwd()):
        self.db_name = db_name
        self.db_path = db_path

        if not os.path.exists(self.db_path):
            os.makedirs(self.db_path)
        if not os.path.exists(self.db_name):
            with open(self.db_name, "w", encoding="utf-8"):
                pass

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

    def run(self, start_folder: str, threads_amount: int = 24):
        conn = sqlite3.connect(self.db_name, check_same_thread=False)
        cur = conn.cursor()
        pics_queue = queue.Queue()

        cur.execute("""CREATE TABLE IF NOT EXISTS files(
            md5 TEXT PRIMARY KEY,
            path TEXT,

            width INT,
            height INT,
            resolution INT,

            top_crop REAL,
            bottom_crop REAL,

            monochrome REAL,
            comparison_function TEXT,

            max_deviation REAL,
            pixel_group INT,

            addition_date TEXT,
            addition_time TEXT
            );
        """)
        conn.commit()

        cur.execute("SELECT path FROM files;")
        db_files = tuple(file[0] for file in cur.fetchall())
        conn.close()

        for path, _, files in os.walk(start_folder):
            for name in files:
                fpath = os.path.join(path, name)
                if fpath not in db_files:
                    pics_queue.put(fpath)

        pics_queue_size = pics_queue.qsize()
        if pics_queue_size < threads_amount:
            threads_amount = pics_queue_size

        for i in range(threads_amount):
            thread = self.StartThread(f"Thread {i}", self.db_name, pics_queue, pics_queue_size)
            thread.start()


class CopyImages:
    # ! The fuck it does?
    class StartThread(Thread):
        def __init__(self):
            super().__init__()

        def run(self):
            pass

    def __init__(self, db_name):
        self.db_name = db_name

    def run(self, condition: str, end_folder: str):
        # if not os.path.exists(end_folder):
        #     os.makedirs(end_folder)
        conn = sqlite3.connect(self.db_name, check_same_thread=False)
        cur = conn.cursor()

        cur.execute("PRAGMA table_info(files);")
        columns_data = cur.fetchall()
        columns_names = [item[1] for item in columns_data]
        columns_types = []
        for item in columns_data:
            convert_types_dict = {"TEXT": "str", "NUMERIC": "int",
                                  "INTEGER": "int", "INT": "int", "REAL": "float"}
            columns_types.append(convert_types_dict[item[2].upper()])

        cur.execute("SELECT * FROM files ORDER BY path ASC;")
        for file in cur.fetchall():
            for i, cell in enumerate(file):
                print(f"{columns_names[i]} = {columns_types[i]}('{cell}')")
            # file = list(file)
            # file[0] = file[0].replace("\\", "/")
            # for i, cell in enumerate(file):
            #     exec(f"{columns_names[i]} = {columns_types[i]}(\"{cell}\")")
            # if eval(condition):
            #     eval("shutil.copy2(path, end_folder)")


class EnlargeImages:
    # TODO: Изменение расширения с копирования 1 и n-1 строчек на цвет этих строчек, чтобы избежать полос + отдельно для градиента
    # TODO: В случае наклона градиента - попытка продолжения наклона
    class StartThread(Thread):
        def __init__(self, name: str, q: queue.Queue, queue_start_size: int, min_height: int = 1000):
            super().__init__()
            self.thread_name = name
            self.pics_queue = q
            self.pics_queueueue_start_size = queue_start_size
            self.min_height = min_height
            self.end_folder = r"E:\Эротические фотокарточки\На обои (по цветам краев)\Увеличенные"
            self.height_folder = r"E:\Эротические фотокарточки\На обои (по цветам краев)\Малый размер"

        def run(self):
            for file in self.pics_queue:
                if imghdr.what(rf"E:\Эротические фотокарточки\На обои (по цветам краев)\{file}") in ("png", "jpeg", "bmp"):
                    img = Image.open(f"E:\\Эротические фотокарточки\\На обои (по цветам краев)\\{file}")
                    if img.height < self.min_height:
                        img.save(f"{self.height_folder}\\{file}")
                        continue
                    left_strip = img.crop((0, 0, 1, img.height))
                    right_strip = img.crop((img.width-1, 0, img.width, img.height))

                    enl_im = Image.new(img.mode, (int(img.height*1.77), img.height))
                    enl_im.paste(img, (int(enl_im.width/2-img.width/2), 0))
                    for width in range(int(enl_im.width/2 - img.width/2) + 3):
                        enl_im.paste(left_strip, (width, 0))
                        enl_im.paste(right_strip, (enl_im.width-width, 0))
                    enl_im.save("{self.end_folder}\\{file}")

                    print(f"{self.thread_name} ENLARGED {file}")

    def __init__(self):
        pass

    def run(self, start_folder: str, threads_amount: int = 24, copy_existing_files: bool = False):
        pics_queue = queue.Queue()

        for path, _, files in os.walk(start_folder):
            for name in files:
                fpath = os.path.join(path, name)
                pics_queue.put(fpath)

        start_queue_size = pics_queue.qsize()
        if start_queue_size < threads_amount:
            threads_amount = start_queue_size

        for i in range(threads_amount):
            thread = self.StartThread(
                f"Thread {i}", pics_queue, start_queue_size)
            thread.start()


if __name__ == "__main__":
    mkdb = MakeDB("wallpaper.db")
    mkdb.run("E:\\Эротические фотокарточки\\Хентай (полноразмерный)")
