from VIStk.Structures._Project import *
from VIStk.Structures._VINFO import *
from VIStk.Structures._Screen import *
import subprocess
import shutil
from os.path import exists
from zipfile import *
import datetime
import hashlib
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
                meta = meta.replace("$M$",str(i.Version._major))
                meta = meta.replace("$m$",str(i.Version._minor))
                meta = meta.replace("$p$",str(i.Version._patch))

                #Update Screen Version
                meta = meta.replace("$sM$",str(i.s_version._major))
                meta = meta.replace("$sm$",str(i.s_version._minor))
                meta = meta.replace("$sp$",str(i.s_version._patch))

                #Update Company Info
                if self.company != None:
                    meta = meta.replace("$company$",self.company)
                    meta = meta.replace("$year$",str(datetime.datetime.now().year))
                else:
                    meta = meta.replace("            VALUE \"CompanyName\",      VER_COMPANYNAME_STR\n","")
                    meta = meta.replace("            VALUE \"LegalCopyright\",   VER_LEGALCOPYRIGHT_STR\n","")
                    meta = meta.replace("#define VER_LEGAL_COPYRIGHT_STR     \"Copyright \u00a9 $year$ $company$\\0\"\n\n","")

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
        pendix = self.title if self.flag == "" else f"{self.title}-{self.flag}"
        out_dir = f"{self.location}{pendix}"

        #Remove Pre-existing Folders for Icons, Images, & .VIS
        for folder in ("Icons", "Images", ".VIS"):
            target = f"{out_dir}/{folder}/"
            if exists(target):
                shutil.rmtree(target)

        #Copy Project Folder for Icons, Images, & .VIS
        for folder in ("Icons", "Images", ".VIS"):
            shutil.copytree(f"{self.p_project}/{folder}/", f"{out_dir}/{folder}/", dirs_exist_ok=True)

        #Announce Completion
        print(f"\n\nReleased a new{' '+self.flag+' ' if not self.flag is None else ''}build of {self.title}!")

    def newVersion(self):
        """Updates the project version, PERMANENT, cannot be undone"""
        old = str(self.Version)

        if self.type == "Major":
            self.Version.major()
        elif self.type == "Minor":
            self.Version.minor()
        elif self.type == "Patch":
            self.Version.patch()
        else:
            print(f"Unknown version type '{self.type}'. Use Major, Minor, or Patch.")
            return False

        confirm = input(f"Version will change from {old} to {self.Version}. Proceed? (y/n): ")
        if confirm.lower() not in ("y", "yes"):
            # Revert to old version
            self.Version = Version(old)
            print("Version change cancelled.")
            return False

        print(f"Updated Version {old} => {self.Version}")
        return True

    def release(self):
        """Releases a version of your project"""
        #Check Version
        if self.type != "":
            if not self.newVersion():
                return

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
        pendix = self.title if self.flag == "" else f"{self.title}-{self.flag}"
        final = f"{self.location}{pendix}"
        binaries_zip = f"{self.location}binaries.zip"

        #Create binaries.zip from built output
        print(f"Creating binaries.zip from {final} for installer")
        shutil.make_archive(base_name=f"{self.location}binaries", format="zip", root_dir=final)

        #Resolve installer icon
        icon_file = self.d_icon
        if sys.platform == "win32":
            icon_file = self.p_project + "/Icons/" + icon_file + ".ico"
        else:
            icon_file = self.p_project + "/Icons/" + icon_file + ".xbm"

        #Installer cache — skip PyInstaller if Installer.py and icon are unchanged
        installer_src = VISROOT.replace("\\","/")+"Structures/Installer.py"
        cache_dir = self.p_vinfo + "/cache"
        os.makedirs(cache_dir, exist_ok=True)

        cache_base = cache_dir + "/installer_base"
        if sys.platform == "win32":
            cache_base += ".exe"
        cache_hash_file = cache_dir + "/installer.hash"

        #Hash installer source + icon to detect changes
        hasher = hashlib.sha256()
        for path in (installer_src, icon_file):
            with open(path, "rb") as f:
                hasher.update(f.read())
        current_hash = hasher.hexdigest()

        #Check if cached base installer is still valid
        cached_hash = ""
        if os.path.exists(cache_hash_file) and os.path.exists(cache_base):
            with open(cache_hash_file, "r") as f:
                cached_hash = f.read().strip()

        if cached_hash == current_hash:
            print("Installer source unchanged — using cached base installer")
        else:
            print(f"Compiling base installer for {pendix}")
            subprocess.call(
                f"pyinstaller --noconfirm --onefile "
                f"{'--uac-admin ' if sys.platform == 'win32' else ''}"
                f"--windowed --name installer_base --log-level FATAL "
                f"--icon {icon_file} --hidden-import PIL._tkinter_finder "
                f"{installer_src}",
                shell=True, cwd=self.location
            )

            #Cache the compiled base installer
            built_base = glob.glob("installer_base*", root_dir=self.location+"dist/")[0]
            shutil.copy2(self.location+f"dist/{built_base}", cache_base)

            #Save hash for future comparisons
            with open(cache_hash_file, "w") as f:
                f.write(current_hash)

            #Clean PyInstaller build artifacts
            shutil.rmtree(self.location+"dist/")
            shutil.rmtree(self.location+"build/")
            if os.path.exists(self.location+"installer_base.spec"):
                os.remove(self.location+"installer_base.spec")

            print("Base installer cached for future releases")

        #Concatenate: cached base exe + binaries.zip = final installer
        installer_name = f"{pendix}_Installer"
        if sys.platform == "win32":
            installer_name += ".exe"
        final_installer = f"{self.p_project}/{installer_name}"

        print(f"Assembling {installer_name} (base + binaries.zip)")
        if os.path.exists(final_installer):
            os.remove(final_installer)
        with open(final_installer, "wb") as out:
            with open(cache_base, "rb") as base:
                out.write(base.read())
            with open(binaries_zip, "rb") as data:
                out.write(data.read())

        #Clean up temporary binaries.zip
        os.remove(binaries_zip)
        print(f"Installer ready: {final_installer}")
