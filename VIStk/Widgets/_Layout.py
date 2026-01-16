from tkinter import ttk

class Layout(ttk.Frame):
    """A VIS Layout Frame"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args,**kwargs)
        self.master.bind("<Configure>", self.autosize)
        self.master.bind("<<Modified>>", self.autosize)
        self.rows = []
        self.columns = []
        
    def size(self,rows:int,columns:int):
        """Sets the size of the grid
        
        Args:
            rows (int): The number of rows in the layout
            columns (int): The number of columns in the layout
        """
        if rows < 1: rows = 1
        if columns < 1: columns = 1

        for row in range(0,rows,1):
            self.rowconfigure(row)
            self.rows.append({})

        for column in range(0,columns,1):
            self.columnconfigure(column)
            self.columns.append({})

    def rowSize(self, row:int, weight:int=0, minsize:int=0, maxsize:int=None):
        """Sets sizing options for row
        
        Args:
            row (int): The row to set the size options for
            weight (int): The weight of the row when resizing
            minsize (int): The minimum size of the row
            maxsize (int): The maximum size of the row
        """

        self.rows[row-1]={
            "weight": weight,
            "minsize": minsize,
            "maxsize": maxsize
        }

    def colSize(self, column:int, weight:int=0, minsize:int=0, maxsize:int=None):
        """Sets sizing options for a column
        
        Args:
            row (int): The row to set the size options for
            weight (int): The weight of the row when resizing
            minsize (int): The minimum size of the row
            maxsize (int): The maximum size of the row
        """

        self.columns[column-1]={
            "weight": weight,
            "minsize": minsize,
            "maxsize": maxsize
        }

    def autosize(self,*nonsense):
        """Resizing the layout according to the given rules"""
        #Solve Variables
        rowperp = 0
        colperp = 0
        minr = 0
        minc = 0
        
        #Calculate Row Values
        for i in self.rows:
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
        for i in self.columns:
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
        width = self.winfo_width()
        height = self.winfo_height()
        uswidth = width - minc
        usheight = height - minr
        
        #Solve Variables for Rows
        solvedy = []
        solutionsy = [0] * len(self.rows)

        while True: #Solve Rows
            #Break if weve solved all items
            if len(solvedy) >= len(self.rows): break
            #Break if we have reached the size of the layout
            if round(sum(solutionsy)) >= height: break

            #Correct rate
            ratey = usheight/rowperp

            #Attempt Solve
            for i in range(0, len(self.rows),1):
                if i in solvedy:
                    pass #Do not resolve items
                else:
                    #Calculate newsize
                    newsize = self.rows[i]["minsize"]+self.rows[i]["weight"]*ratey

                    #Find Maxsize and Resolve
                    maxsize = self.rows[i].get("maxsize")
                    if not maxsize is None:
                        if newsize > maxsize:
                            #Modify Usable Width & Column Pixels/Pixel
                            dif = maxsize - self.rows[i]["minsize"]
                            usheight -= dif
                            rowperp -= self.rows[i]["weight"]
                            
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
        solutionsx = [0] * len(self.columns)

        while True: #Solve Columns
            #Break if weve solved all items
            if len(solvedx) >= len(self.columns): break
            #Break if we have reached the size of the layout
            if round(sum(solutionsx)) >= width: break

            #Correct rate
            ratex = uswidth/colperp

            #Attempt Solve
            for i in range(0, len(self.columns),1):
                if i in solvedx:
                    pass #Do not resolve items
                else:
                    #Calculate newsize
                    newsize = self.columns[i]["minsize"]+self.columns[i]["weight"]*ratex

                    #Find Maxsize and Resolve
                    maxsize = self.columns[i].get("maxsize")
                    if not maxsize is None:
                        if newsize > maxsize:
                            #Modify Usable Width & Column Pixels/Pixel
                            dif = maxsize - self.columns[i]["minsize"]
                            uswidth -= dif
                            colperp -= self.columns[i]["weight"]
                            
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

        #Ensure Y Values Sum to Height
        if not sum(solutionsy) == height:
            for i in range(0,len(solutionsy),1):
                if i in solvedx:pass
                else: #Try To Avoid Changing the Width of Equal Items
                    if solutionsy.count(solutionsy[i]) == 1:solutionsy[i] += 1
                    else:pass

            if not sum(solutionsy) == height:
                for i in range(0,len(solutionsy),1):
                    if i in solvedy:pass
                    else:solutionsy[i] += 1
        #Round All X Values
        for i in range(0,len(solutionsx),1):
            solutionsx[i] = round(solutionsx[i])
        
        #Ensure X Values Sum to Width
        if not sum(solutionsx) == width:
            for i in range(0,len(solutionsx),1):
                if i in solvedx:pass
                else: #Try To Avoid Changing the Width of Equal Items
                    if solutionsx.count(solutionsx[i]) == 1:solutionsx[i] += 1
                    else:pass

            if not sum(solutionsx) == width:
                for i in range(0,len(solutionsx),1):
                    if i in solvedx:pass
                    else:solutionsx[i] += 1

        #Configure All Rows
        for i in range(0,len(solutionsy),1):
            self.rowconfigure(i+1,minsize=solutionsy[i])

        #Configure All Columns
        for i in range(0,len(solutionsx),1):
            self.columnconfigure(i+1,minsize=solutionsx[i])

