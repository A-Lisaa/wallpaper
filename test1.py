from PIL import Image

im = Image.open("./tests/images/test_image_monochrome.jpg")

print(im.getpixel((0, 0)))
