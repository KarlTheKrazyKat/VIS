import sys

file = sys.argv[1]
frame = file.split('/')[-1][:-3]
file=file.replace(frame,"f_"+frame)
with open(file,"r") as f:
    text = f.read()
text = text.replace("<frame>","f_"+frame)
with open(file,"w") as f:
    f.write(text)
    print("patched\tf_"+frame+".py")