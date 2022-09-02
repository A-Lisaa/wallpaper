
import imghdr
import os
import queue
import sqlite3
from threading import Thread

from PIL import Image
from src.backend.scaner import ScanImages


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


if __name__ == "__main__":
    scaner = ScanImages("wallpaper.db")
    #scaner.run("E:\\Эротические фотокарточки\\Хентай (полноразмерный)")
    scaner.run(".\\")
