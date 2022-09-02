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
