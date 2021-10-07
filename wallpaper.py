# -*- coding: utf-8 -*-
import os
import hashlib
import shutil
import statistics
import time
import sqlite3
import queue
import imghdr
from PIL import Image, UnidentifiedImageError
from threading import Thread
from colormath.color_objects import sRGBColor, LabColor
from colormath.color_conversions import convert_color
from colormath.color_diff import delta_e_cie2000
# TODO: Tests for each method


class MakeDB:
    class StartThread(Thread):
        def __init__(
                    self, name: str, db_name: str, q: queue.Queue, queue_start_size: int,
                    top_crop: float = 0.1, bottom_crop: float = 0.1,
                    pixel_group: int = 1, check_value: int = 25
                    ):
            print(f"{name} has been launched\n", end="")
            super().__init__()

            # Mandatory args
            self.name = name
            self.conn = sqlite3.connect(db_name, check_same_thread=False)
            self.cur = self.conn.cursor()
            self.q = q
            self.queue_start_size = queue_start_size

            # Optional args
            self.top_crop = top_crop
            self.bottom_crop = bottom_crop
            self.pixel_group = pixel_group
            self.check_value = check_value

        def get_file_md5(self, fname: str) -> str:
            hash_md5 = hashlib.md5()
            with open(fname, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()

        def comparison(self, img: Image, mode_lab_color: LabColor, pixel_width: int) -> int:
            compared_pixels = 0
            for pixel_height in range(0, img.height-1, self.pixel_group):
                r, g, b, _ = img.getpixel((pixel_width, pixel_height))
                lab_pixel_color = convert_color(sRGBColor(r, g, b), LabColor)
                if delta_e_cie2000(lab_pixel_color, mode_lab_color) <= self.check_value:
                    compared_pixels += 1

            return compared_pixels

        def edges_mono_check(self, img: Image) -> float:
            colors = []
            img = img.crop((0, img.height*self.top_crop, img.width, img.height*(1-self.bottom_crop)))

            # ! gif colors and modes do not work correctly
            for pixel_height in range(0, img.height-1, self.pixel_group):
                colors.append(img.getpixel((0, pixel_height)))
                colors.append(img.getpixel((img.width-1, pixel_height)))

            modes = statistics.multimode(colors)
            modes_length = len(modes)
            modes = tuple(zip(*modes))
            red = sum(modes[0]) / modes_length
            green = sum(modes[1]) / modes_length
            blue = sum(modes[2]) / modes_length
            mode_lab_color = convert_color(sRGBColor(red, green, blue), LabColor)

            compared_pixels = self.comparison(img, mode_lab_color, 0)
            compared_pixels += self.comparison(img, mode_lab_color, img.width-1)
            percentage = compared_pixels/(img.height*2/self.pixel_group)

            return percentage

        # TODO: Отлов исключений и ведение лога и/или вывод на экран
        # TODO: GUI (PyQt6)
        def run(self):
            while not self.q.empty():
                file = self.q.get()

                try:
                    img = Image.open(file)
                except UnidentifiedImageError:
                    continue

                md5 = self.get_file_md5(file)
                monochrome = self.edges_mono_check(img.convert("RGBA"))
                resolution = img.width/img.height
                current_time = time.localtime()
                addition_date = time.strftime("%d.%m.%Y", current_time)
                addition_time = time.strftime("%H:%M:%S", current_time)

                values = (md5, file, img.width, img.height, resolution,
                        monochrome, self.check_value, addition_date, addition_time)
                self.cur.execute("INSERT INTO files VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?);", values)
                self.conn.commit()
                print(f"{self.name} CHECKED {file} ({self.queue_start_size-self.q.qsize()}/{self.queue_start_size})\n", end="")

                self.q.task_done()


    def __init__(self, db_name: str = "wallpaper.db", db_path: str = os.getcwd()):
        self.db_name = db_name
        self.db_path = db_path

        if not os.path.exists(self.db_path):
            os.makedirs(self.db_path)
        if not os.path.exists(self.db_name):
            with open(self.db_name, "w"):
                pass

    def copy_db(self):
        appdata = os.getenv("appdata")
        copy_db_name = f"{self.db_name}.copy"

        shutil.copy2(self.db_name, appdata)
        try:
            os.rename(f"{appdata}\\{self.db_name}", f"{appdata}\\{copy_db_name}")
        except FileExistsError:
            os.remove(f"{appdata}\\{copy_db_name}")
            os.rename(f"{appdata}\\{self.db_name}", f"{appdata}\\{copy_db_name}")
        shutil.copy2(f"{appdata}\\{copy_db_name}", os.getcwd())
        os.remove(f"{appdata}\\{copy_db_name}")

    def run(self, start_folder: str, threads_amount: int = 24):
        conn = sqlite3.connect(self.db_name, check_same_thread=False)
        cur = conn.cursor()

        # TODO: md5 instead of path as key, path is needed but not as key
        cur.execute("""CREATE TABLE IF NOT EXISTS files(
            md5 TEXT PRIMARY KEY,
            path TEXT,
            width INT,
            height INT,
            resolution INT,
            monochrome INT,
            max_deviation INT,
            addition_date TEXT,
            addition_time TEXT
            );
        """)
        conn.commit()

        cur.execute("SELECT path FROM files;")
        db_files = tuple(file[0] for file in cur.fetchall())
        conn.close()
        q = queue.Queue()

        for path, _, files in os.walk(start_folder):
            for name in files:
                fpath = os.path.join(path, name)
                if fpath not in db_files:
                    q.put(fpath)

        start_queue_size = q.qsize()
        if start_queue_size < threads_amount:
            threads_amount = start_queue_size

        for i in range(threads_amount):
            thread = self.StartThread(f"Thread {i}", self.db_name, q, start_queue_size)
            thread.start()


class CopyImages:
    class StartThread(Thread):
        def __init__(self):
            super().__init__()

        def run(self):
            pass

    def __init__(self):
        pass

    def run(self, condition: str, end_folder: str):
        if not os.path.exists(end_folder):
            os.makedirs(end_folder)
        conn = sqlite3.connect(self.db_name, check_same_thread=False)
        cur = conn.cursor()

        cur.execute("PRAGMA table_info(files);")
        columns_data = cur.fetchall()
        columns_names = [item[1] for item in columns_data]
        columns_types = []
        for item in columns_data:
            convert_types_dict = {"TEXT":"str", "NUMERIC":"int", "INTEGER":"int", "INT":"int", "REAL":"float"}
            columns_types.append(convert_types_dict[item[2].upper()])

        cur.execute("SELECT * FROM files ORDER BY path ASC;")
        for file in cur.fetchall(): # TODO: md5 implementation
            file = list(file)
            file[0] = file[0].replace("\\", "/")
            for i, cell in enumerate(file):
                exec(f"{columns_names[i]} = {columns_types[i]}(\"{cell}\")")
            if eval(condition):
                eval("shutil.copy2(path, end_folder)")


class EnlargeImages:
    class StartThread(Thread):
        def __init__(self, name: str, q: queue.Queue, queue_start_size: int):
            Thread.__init__(self)
            self.name = name
            self.q = q
            self.queue_start_size = queue_start_size
            self.end_folder = "E:\Эротические фотокарточки\На обои (по цветам краев)\Увеличенные"
            self.height_folder = "E:\Эротические фотокарточки\На обои (по цветам краев)\Малый размер"

        def run(self):
            for file in self.q:
                if imghdr.what(f"E:\Эротические фотокарточки\На обои (по цветам краев)\{file}") in ("png", "jpeg", "bmp"):
                    im = Image.open(f"E:\Эротические фотокарточки\На обои (по цветам краев)\{file}")
                    with open("enlargement_existing_files.txt", "a", encoding = "utf-8") as f:
                        f.write(file)
                        f.write("\n")
                    if im.height < 1000:
                        im.save("{}\\{}".format(self.height_folder, file))
                        continue
                    left_strip = im.crop((0, 0, 1, im.height))
                    right_strip = im.crop((im.width-1, 0, im.width, im.height))

                    enl_im = Image.new(im.mode, (int(im.height*1.77), im.height))
                    enl_im.paste(im, (int(enl_im.width/2-im.width/2), 0))
                    for width in range(int(enl_im.width/2-im.width/2)+3):
                        enl_im.paste(left_strip, (width, 0))
                        enl_im.paste(right_strip, (enl_im.width-width, 0))
                    enl_im.save("{}\\{}".format(self.end_folder, file))

                    print(f"{self.name} ENLARGED {file}")

    def __init__(self):
        pass

    def run(self, start_folder: str, threads_amount: int = 24, copy_existing_files: bool = False):
        q = queue.Queue()

        for path, _, files in os.walk(start_folder):
            for name in files:
                fpath = os.path.join(path, name)
                q.put(fpath)

        start_queue_size = q.qsize()
        if start_queue_size < threads_amount:
            threads_amount = start_queue_size

        for i in range(threads_amount):
            thread = self.StartThread(f"Thread {i}", q, start_queue_size)
            thread.start()


if __name__ == "__main__":
    mkdb = MakeDB()
    mkdb.run("E:\\Эротические фотокарточки\\Хентай (полноразмерный)")