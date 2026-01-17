from tkinter import *
from tkinter import ttk

def size(sizeable:Tk|ttk.Frame|Toplevel,rows:int,columns:int):
    """Sets the size of the grid
    
    Args:
        rows (int): The number of rows in the layout
        columns (int): The number of columns in the layout
    """
    #Ensure Sizeable Has .rows
    try: 1+1 if sizeable.rows is None else 1+1
    except AttributeError: sizeable.rows = []

    #Ensure Sizeable Has .columns
    try: 1+1 if sizeable.columns is None else 1+1
    except AttributeError: sizeable.columns = []


    if rows < 1: rows = 1
    if columns < 1: columns = 1

    for row in range(0,rows,1):
        sizeable.rowconfigure(row)
        sizeable.rows.append({})

    for column in range(0,columns,1):
        sizeable.columnconfigure(column)
        sizeable.columns.append({})

def rowSize(sizeable:Tk|ttk.Frame|Toplevel, row:int, weight:int=0, minsize:int=0, maxsize:int=None):
    """Sets sizing options for row
    
    Args:
        row (int): The row to set the size options for
        weight (int): The weight of the row when resizing
        minsize (int): The minimum size of the row
        maxsize (int): The maximum size of the row
    """

    sizeable.rows[row-1]={
        "weight": weight,
        "minsize": minsize,
        "maxsize": maxsize
    }

def colSize(sizeable:Tk|ttk.Frame|Toplevel, column:int, weight:int=0, minsize:int=0, maxsize:int=None):
    """Sets sizing options for a column
    
    Args:
        row (int): The row to set the size options for
        weight (int): The weight of the row when resizing
        minsize (int): The minimum size of the row
        maxsize (int): The maximum size of the row
    """

    sizeable.columns[column-1]={
        "weight": weight,
        "minsize": minsize,
        "maxsize": maxsize
    }

def sizeUp(solutions:list[int], solved:list[int], match:int) -> list[int]:
    """Steps the size up toward match
    
    Args:
        solutions (list[int]): The calculated solutions
        solved (list[int]): A list of the solved (maxed) solutions
        match (int): The constraint to match

    Returns:
        solutions (list): The verified solutions
    """
    #Attempt to keep equal solutions equal
    for i in range(0,len(solutions),1):
        if i in solved:pass
        else:
            if solutions.count(solutions[i]) == 1:
                solutions[i] += 1
                return solutions
            else:pass
    
    #Break equal solutions if necessary
    for i in range(0,len(solutions),1):
        if i in solved:pass
        else:
            solutions[i] += 1
            return solutions

def sizeDn(solutions:list[int], solved:list[int], match:int) -> list[int]:
    """Steps the size down toward match
    
    Args:
        solutions (list[int]): The calculated solutions
        solved (list[int]): A list of the solved (maxed) solutions
        match (int): The constraint to match

    Returns:
        solutions (list): The verified solutions
    """
    #Attempt to keep equal solutions equal
    for i in range(0,len(solutions),1):
        if i in solved:pass
        else:
            if solutions.count(solutions[i]) == 1:
                solutions[i] -= 1
                return solutions
            else:pass
    
    #Break equal solutions if necessary
    for i in range(0,len(solutions),1):
        if i in solved:pass
        else:
            solutions[i] -= 1
            return solutions

def verifier(solutions:list[int], solved:list[int], match:int) -> list[int]:
    """Verifies that the solutions sum to the constraint
    
    Args:
        solutions (list[int]): The calculated solutions
        solved (list[int]): A list of the solved (maxed) solutions
        match (int): The constraint to match

    Returns:
        solutions (list): The verified solutions
    """
    while sum(solutions) < match:
        solutions=sizeUp(solutions,solved,match)
    while sum(solutions) > match:
        solutions=sizeDn(solutions,solved,match)

    return solutions

def autosize(sizeable:Tk|ttk.Frame|Toplevel,*nonsense):
    """Resizing the grid according to the given rules"""
    #Solve Variables
    rowperp = 0
    colperp = 0
    minr = 0
    minc = 0
    
    #Calculate Row Values
    for i in sizeable.rows:
        #Find Weight
        w = i.get("weight")
        if w is None: w = 0
        #Find Minsize
        m = i.get("minsize")
        if m is None: m = 0
        #Add to Values
        rowperp += int(w)
        minr += int(m)

    #Calculate Columns Values
    for i in sizeable.columns:
        #Find Weight
        w = i.get("weight")
        if w is None: w = 0
        #Find Minsize
        m = i.get("minsize")
        if m is None: m = 0
        #Add to Values
        colperp += int(w)
        minc += int(m)
    
    #Calculate Usable Size
    try: #Will Fail for TopLevel Widgets
        e, r, width, height = sizeable.master.bbox(sizeable.grid_info()["column"],sizeable.grid_info()["row"])

    except AttributeError:
        width = sizeable.winfo_width()
        height = sizeable.winfo_height()
    
    uswidth = width - minc
    usheight = height - minr
    
    #Solve Variables for Rows
    solvedy = []
    solutionsy = [0] * len(sizeable.rows)

    while True: #Solve Rows
        #Break if weve solved all items
        if len(solvedy) >= len(sizeable.rows): break
        #Break if we have reached the size of the layout
        if round(sum(solutionsy)) >= height: break

        #Correct rate
        ratey = usheight/rowperp

        #Attempt Solve
        for i in range(0, len(sizeable.rows),1):
            if i in solvedy:
                pass #Do not resolve items
            else:
                #Calculate newsize
                newsize = sizeable.rows[i]["minsize"]+sizeable.rows[i]["weight"]*ratey

                #Find Maxsize and Resolve
                maxsize = sizeable.rows[i].get("maxsize")
                if not maxsize is None:
                    if newsize > maxsize:
                        #Modify Usable Width & Column Pixels/Pixel
                        dif = maxsize - sizeable.rows[i]["minsize"]
                        usheight -= dif
                        rowperp -= sizeable.rows[i]["weight"]
                        
                        #Append Solution & Solved Info
                        solvedy.append(i)
                        solutionsy[i]=maxsize
                    else:
                        #Append Solution
                        solutionsy[i] = newsize
                else:
                    #Append Solution
                    solutionsy[i] = newsize
    
    #Solve Variables for Columns
    solvedx = []
    solutionsx = [0] * len(sizeable.columns)

    while True: #Solve Columns
        #Break if weve solved all items
        if len(solvedx) >= len(sizeable.columns): break
        #Break if we have reached the size of the layout
        if round(sum(solutionsx)) >= width: break

        #Correct rate
        ratex = uswidth/colperp

        #Attempt Solve
        for i in range(0, len(sizeable.columns),1):
            if i in solvedx:
                pass #Do not resolve items
            else:
                #Calculate newsize
                newsize = sizeable.columns[i]["minsize"]+sizeable.columns[i]["weight"]*ratex

                #Find Maxsize and Resolve
                maxsize = sizeable.columns[i].get("maxsize")
                if not maxsize is None:
                    if newsize > maxsize:
                        #Modify Usable Width & Column Pixels/Pixel
                        dif = maxsize - sizeable.columns[i]["minsize"]
                        uswidth -= dif
                        colperp -= sizeable.columns[i]["weight"]
                        
                        #Append Solution & Solved Info
                        solvedx.append(i)
                        solutionsx[i]=maxsize
                    else:
                        #Append Solution
                        solutionsx[i] = newsize
                else:
                    #Append Solution
                    solutionsx[i] = newsize

    #Round All Y Values
    for i in range(0,len(solutionsy),1):
        solutionsy[i] = round(solutionsy[i])

    #Round All X Values
    for i in range(0,len(solutionsx),1):
        solutionsx[i] = round(solutionsx[i])
    
    #Verify Y Values
    solutionsy = verifier(solutionsy,solvedy,height)

    #Verify X Values
    solutionsx = verifier(solutionsx,solvedx,width)
    
    #Configure All Rows
    for i in range(0,len(solutionsy),1):
        sizeable.rowconfigure(i+1,minsize=solutionsy[i])

    #Configure All Columns
    for i in range(0,len(solutionsx),1):
        sizeable.columnconfigure(i+1,minsize=solutionsx[i])

    print(width,height)