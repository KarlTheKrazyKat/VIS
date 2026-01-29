from VIStk.Structures._Project import *
from VIStk.Structures._VINFO import *
from VIStk.Structures._Screen import *
import subprocess
import shutil
from os.path import exists
from zipfile import *
import datetime
from VIStk.Structures._Version import Version

class Release(Project):
    """A VIS Release object"""
    def __init__(self, flag:str="",type:str="",note:str=""):
        """Creates a Release object to release or examine a releaes of a project"""
        super().__init__()
        self.type = type
        self.flag = flag
        self.note = note

        self.location = self.dist_location.replace(".",self.p_project)
        self._internal = f"{self.location}{self.title}-{self.flag}/_internal/"

    def build(self):
        """Build project spec file for release
        """
        
        #Announce Spec Creation
        print(f"Creating project.spec for {self.title}")
        
        #Ensure spec template has hidden imports
        with open(self.p_vinfo+"/Templates/spec.txt","r+") as f:
            oldspec = f.readlines()
            newspec=""
            for line in oldspec:
                if "hiddenimports" in line:
                    line = "\thiddenimports=" + str(self.hidden_imports) + ",\n"
                newspec = newspec + line
            f.seek(0)
            f.write(newspec)
            f.truncate()

        #Load Spec & Collect
        with open(self.p_vinfo+"/Templates/spec.txt","r") as f:
            spec = f.read()
        with open(self.p_vinfo+"/Templates/collect.txt","r") as f:
            collect = f.read()
        
        #Initialize locations for builds
        spec_list = []
        name_list = []
        if os.path.exists(self.p_vinfo+"/Build"):
            shutil.rmtree(self.p_vinfo+"/Build")
        os.mkdir(self.p_vinfo+"/Build")

        #Loop and Build Screens as .txt
        for i in self.screenlist:
            if i.release:
                name_list.append(i.name)
                if not i.icon == None:
                    icon = i.icon
                else:
                    icon = self.d_icon
                if str.upper(sys.platform)=="WIN32":
                    ixt = ".ico"
                else:
                    ixt = ".xbm"
                icon = icon + ixt
                spec_list.append(spec.replace("$name$",i.name))
                spec_list[-1] = spec_list[-1].replace("$icon$",icon)
                spec_list[-1] = spec_list[-1].replace("$file$",i.script)

                #Load metadata template
                with open(self.p_templates+"/version.txt","r") as f:
                    meta = f.read()

                #Update Overall Project Version
                meta = meta.replace("$M$",i.Version._major)
                meta = meta.replace("$m$",i.Version._minor)
                meta = meta.replace("$p$",i.Version._patch)

                #Update Screen Version
                meta = meta.replace("$sM$",i.s_version._major)
                meta = meta.replace("$sm$",i.s_version._minor)
                meta = meta.replace("$sp$",i.s_version._patch)

                #Update Company Info
                if self.company != None:
                    meta = meta.replace("$company$",self.company)
                    meta = meta.replace("$year$",str(datetime.datetime.now().year))
                else:
                    meta = meta.replace("            VALUE \"CompanyName\",      VER_COMPANYNAME_STR\n","")
                    meta = meta.replace("            VALUE \"LegalCopyright\",   VER_LEGALCOPYRIGHT_STR\n","")
                    meta = meta.replace("#define VER_LEGAL_COPYRIGHT_STR     \"Copyright © $year$ $company$\\0\"\n\n","")
                
                #Update Name & Description
                meta = meta.replace("$name$",i.name)
                meta = meta.replace("$desc$",i.desc)
                
                #Write Screen Version Metadata to .txt
                with open(self.p_vinfo+f"/Build/{i.name}.txt","w") as f:
                    f.write(meta)

                #Speclist point to correct path
                spec_list[-1] = spec_list[-1].replace("$meta$",f"./Build/{i.name}.txt")
                spec_list.append("\n\n")

        #Create _a, _pyz, _exe and insert into Collect
        if sys.platform == "linux": #No Collects on Linux
            collect = ""
            for i in range(0,len(spec_list),1):
                spec_list[i] = spec_list[i].replace("exclude_binaries=True","exclude_binaries=False")
        else:
            insert = ""
            for i in name_list:
                insert=insert+"\n\t"+i+"_exe,\n\t"+i+"_a.binaries,\n\t"+i+"_a.zipfiles,\n\t"+i+"_a.datas,"
            collect = collect.replace("$insert$",insert)
            collect = collect.replace("$version$",self.title+"-"+self.flag) if not self.flag == "" else collect.replace("$version$",self.title)
            
        #Header for specfile
        header = "# -*- mode: python ; coding: utf-8 -*-\n\n\n"

        #Write Spec
        with open(self.p_vinfo+"/project.spec","w") as f:
            f.write(header)
            f.writelines(spec_list)
            f.write(collect)

        #Announce Completion
        print(f"Finished creating project.spec for {self.title} {self.flag if not self.flag =='' else 'current'}")#advanced version will improve this

    def clean(self):
        """Cleans up build environment to save space and appends to _internal"""
        #Announce Removal
        print("Cleaning up build environment")

        #Remove Build Folder
        if exists(self.p_vinfo+"/Build"):
            shutil.rmtree(self.p_vinfo+"/Build")

        #Announce Appending Screen Data
        print("Appending Screen Data To Environment")

        #Append Screen Data
        if self.flag == "":
            #Remove Pre-existing Folders for Icons, Images, & .VIS
            if exists(f"{self.location}{self.title}/Icons/"): shutil.rmtree(f"{self.location}{self.title}/Icons/")
            if exists(f"{self.location}{self.title}/Images/"): shutil.rmtree(f"{self.location}{self.title}/Images/")
            if exists(f"{self.location}{self.title}/.VIS/"): shutil.rmtree(f"{self.location}{self.title}/.VIS/")

            #Copy Project Folder for Icons, Images, & .VIS
            shutil.copytree(self.p_project+"/Icons/",f"{self.location}{self.title}/Icons/",dirs_exist_ok=True)
            shutil.copytree(self.p_project+"/Images/",f"{self.location}{self.title}/Images/",dirs_exist_ok=True)
            shutil.copytree(self.p_project+"/.VIS/",f"{self.location}{self.title}/.VIS/",dirs_exist_ok=True)
        
        else:
            #Remove Pre-existing Folders for Icons, Images, & .VIS
            if exists(f"{self.location}{self.title}-{self.flag}/Icons/"): shutil.rmtree(f"{self.location}{self.title}-{self.flag}/Icons/")
            if exists(f"{self.location}{self.title}-{self.flag}/Images/"): shutil.rmtree(f"{self.location}{self.title}-{self.flag}/Images/")
            if exists(f"{self.location}{self.title}-{self.flag}/.VIS/"): shutil.rmtree(f"{self.location}{self.title}-{self.flag}/.VIS/")

            #Copy Project Folder for Icons, Images, & .VIS
            shutil.copytree(self.p_project+"/Icons/",f"{self.location}{self.title}-{self.flag}/Icons/",dirs_exist_ok=True)
            shutil.copytree(self.p_project+"/Images/",f"{self.location}{self.title}-{self.flag}/Images/",dirs_exist_ok=True)
            shutil.copytree(self.p_project+"/.VIS/",f"{self.location}{self.title}-{self.flag}/.VIS/",dirs_exist_ok=True)

        #Announce Completion
        print(f"\n\nReleased a new{' '+self.flag+' ' if not self.flag is None else ''}build of {self.title}!")

    def newVersion(self):
        """Updates the project version, PERMANENT, cannot be undone"""
        #Split Version for Addition
        old = str(self.Version)

        #THIS DOES NOT WORK YET
        #Interate Version Number
        if self.Version == "Major":
            self.Version.major()
        if self.Version == "Minor":
            self.Version.minor()
        if self.Version == "Patch":
            self.Version.patch()

        #Announce Completation
        print(f"Updated Version {old}=>{self.Version}")

    def release(self):
        """Releases a version of your project"""
        #Check Version
        if self.type == "":
            pass #self.newVersion()

        #Build
        self.build()

        #Announce and Update Required Tools
        print("Updating pip...")
        subprocess.call(f"python -m pip install --upgrade pip --quiet",shell=True)

        print("Updating setuptools...")
        subprocess.call(f"python -m pip install --upgrade setuptools --quiet",shell=True)

        print("Updating pyinstaller...")
        subprocess.call(f"python -m pip install --upgrade pyinstaller --quiet",shell=True)

        #Determine Binary Destination
        if sys.platform == "linux":
            destination = self.location+self.title
            if not self.flag == "": destination = destination + "-" + self.flag
        else:
            destination = self.location

        #Announce and Run PyInstaller
        print(f"Running PyInstaller for {self.title}{' ' + self.flag if not self.flag =='' else ''}")
        subprocess.call(f"pyinstaller {self.p_vinfo}/project.spec --noconfirm --distpath {destination} --log-level FATAL",shell=True,cwd=self.p_vinfo)
        
        #Clean Environment
        self.clean()

        #%Installer Generation
        #Move to Installer Build Location
        returndir = os.getcwd()
        if not returndir == self.location:
            os.chdir(self.location)
        
        print(f"We are in {os.getcwd()}")

        #Create Installer
        final = "/".join(destination.split("/")[:-1])+"/"
        pendix = self.title
        if not self.flag == "": pendix = pendix + "-" + self.flag
        final = final + pendix

        #Announce and binaries.zip
        print(f"Creating binaries.zip from {final} for installer")
        shutil.make_archive(base_name="binaries",format="zip",root_dir=final)

        #Load info from binaries.zip
        archive = ZipFile('./binaries.zip','r')
        pfile = archive.open(".VIS/project.json")
        info = json.load(pfile)
        pfile.close()
        archive.close()
        title = list(info.keys())[0]

        #Get Installer Icon
        icon_file = info[title]["defaults"]["icon"]
        if sys.platform == "win32":
            icon_file = self.p_project + "/Icons/" + icon_file + ".ico"
        else:
            icon_file = self.p_project + "/Icons/" + icon_file + ".xbm"

        #Name & Compile Installer
        installer = VISROOT.replace("\\","/")+"Structures/Installer.py"
        print(f"Compiling Installer for {pendix}")
        subprocess.call(f"pyinstaller --noconfirm --onefile --add-data binaries.zip:. {'--uac-admin ' if sys.platform == 'win32' else ''}--windowed --name {pendix}_Installer --log-level FATAL --icon {icon_file} --hidden-import PIL._tkinter_finder {installer}", shell=True)

        #Move Installer to Project Root
        print("Installer completed. Moving to project root...")
        binstaller = glob.glob(f"{pendix}_Installer*",root_dir=self.location+"dist/")[0]
        if os.path.exists(self.p_project+"/"+binstaller):
            os.remove(self.p_project+"/"+binstaller)

        shutil.move(self.location+f"dist/{binstaller}",self.p_project)

        #Clean Installer Build Environment
        print("Cleaning up installer build environment...")
        shutil.rmtree(self.location+"dist/")
        shutil.rmtree(self.location+"build/")
        #os.remove(self.location+"binaries.zip")
        os.remove(self.location+f"{pendix}_installer.spec")

        os.chdir(returndir)