from VIStk.Objects._ArgHandler import ArgHandler
import sys

test = ArgHandler()

def printer(l:list):
    print(" ".join(l))

def lister(l:list):
    print(l)

test.newFlag("print",printer)
test.newFlag("list",lister)

test.handle(sys.argv)