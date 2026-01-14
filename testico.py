from PIL import Image, ImageOps

img = Image.open("cat.jpeg")
img = ImageOps.exif_transpose(img)
x, y = img.size
size = max(x, y)
_img = Image.new('RGBA', (size, size), (0,0,0,0))
_img.paste(img, (int((size-x)/2), int((size-y)/2)))
_img.save("cat.png")

#This code is for automatically creating icons