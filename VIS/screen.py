import sys
file = sys.argv[1]
frame = file.split('\\')[-1][:-3]
dump_screens = False
dump_modules = False
with open(file,"r") as f:
    text= f.readlines()
    for line in text:
        if "screen elements" in line.lower():
            dump_screens=True
        elif "screen elements" in line.lower():
            dump_modules=True

with open(file,"w") as f:
    f.write(text)
