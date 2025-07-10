from VIS.project import *
import subprocess
import shutil
from os.path import exists
import time
import datetime

info = {}
project = Project()


def build(version:str=""):
    """Build project spec file with specific version
    """
    
    print(f"Creating project.spec for {project.name}")

    with open(project.p_vinfo+"/Templates/spec.txt","r") as f:
        spec = f.read()
    with open(project.p_vinfo+"/Templates/collect.txt","r") as f:
        collect = f.read()
    
    spec_list = []
    name_list = []
    os.mkdir(project.p_vinfo+"/Build")
    for i in project.screenlist:
        if i.release:
            name_list.append(i.name)
            if not i.icon == None:
                icon = i.icon
            else:
                icon = project.d_icon
            spec_list.append(spec.replace("$name$",i.name))
            spec_list[len(spec_list)-1] = spec_list[len(spec_list)-1].replace("$icon$",icon)
            spec_list[len(spec_list)-1] = spec_list[len(spec_list)-1].replace("$file$",i.script)

            #build metadata
            with open(project.p_templates+"/version.txt","r") as f:
                meta = f.read()

            #Update Overall Project Version
            vers = project.version.split(".")
            major = vers[0]
            minor = vers[1]
            patch = vers[2]
            meta = meta.replace("$M$",major)
            meta = meta.replace("$m$",minor)
            meta = meta.replace("$p$",patch)

            #Update Screen Version
            vers = i.s_version.split(".")
            major = vers[0]
            minor = vers[1]
            patch = vers[2]
            meta = meta.replace("$sM$",major)
            meta = meta.replace("$sm$",minor)
            meta = meta.replace("$sp$",patch)

            if project.company != None:
                meta = meta.replace("$company$",project.company)
                meta = meta.replace("$year$",str(datetime.datetime.now().year))
            else:
                meta = meta.replace("            VALUE \"CompanyName\",      VER_COMPANYNAME_STR\n","")
                meta = meta.replace("            VALUE \"LegalCopyright\",   VER_LEGALCOPYRIGHT_STR\n","")
                meta = meta.replace("#define VER_LEGAL_COPYRIGHT_STR     \"Copyright © $year$ $company$\\0\"\n\n","")
            meta = meta.replace("$name$",i.name)
            meta = meta.replace("$desc$",i.desc)
            
            with open(project.p_vinfo+f"/Build/{i.name}.txt","w") as f:
                f.write(meta)
            spec_list[len(spec_list)-1] = spec_list[len(spec_list)-1].replace("$meta$",project.p_vinfo+f"/Build/{i.name}.txt")
            spec_list.append("\n\n")

    insert = ""
    for i in name_list:
        insert=insert+"\n\t"+i+"_exe,\n\t"+i+"_a.binaries,\n\t"+i+"_a.zipfiles,\n\t"+i+"_a.datas,"
    collect = collect.replace("$insert$",insert)
    collect = collect.replace("$version$",project.name+"-"+version) if not version == "" else collect.replace("$version$",project.name)
    
    header = "# -*- mode: python ; coding: utf-8 -*-\n\n\n"

    with open(project.p_vinfo+"/project.spec","w") as f:
        f.write(header)
    with open(project.p_vinfo+"/project.spec","a") as f:
        f.writelines(spec_list)
        f.write(collect)

    print(f"Finished creating project.spec for {project.title} {version if not version =="" else "current"}")#advanced version will improve this

def clean(version:str=" "):
    """Cleans up build environment to save space
    """
    print("Cleaning up build environment")
    project=Project()
    shutil.rmtree(project.p_vinfo+"/Build")
    print("Appending Screen Data To Environment")
    if version == " ":
        if exists(f"{project.p_project}/dist/{project.title}/Icons/"): shutil.rmtree(f"{project.p_project}/dist/{project.title}/Icons/")
        if exists(f"{project.p_project}/dist/{project.title}/Images/"): shutil.rmtree(f"{project.p_project}/dist/{project.title}/Images/")
        shutil.copytree(project.p_project+"/Icons/",f"{project.p_project}/dist/{project.title}/Icons/",dirs_exist_ok=True)
        shutil.copytree(project.p_project+"/Images/",f"{project.p_project}/dist/{project.title}/Images/",dirs_exist_ok=True)
    else:
        if exists(f"{project.p_project}/dist/{project.title}/Icons/"): shutil.rmtree(f"{project.p_project}/dist/{project.name}/Icons/")
        if exists(f"{project.p_project}/dist/{project.title}/Images/"): shutil.rmtree(f"{project.p_project}/dist/{project.name}/Images/")
        shutil.copytree(project.p_project+"/Icons/",f"{project.p_project}/dist/{project.title}-{version.strip(" ")}/Icons/",dirs_exist_ok=True)
        shutil.copytree(project.p_project+"/Images/",f"{project.p_project}/dist/{project.title}-{version.strip(" ")}/Images/",dirs_exist_ok=True)
    print(f"\n\nReleased new{version}build of {project.title}!")

def newVersion(version:str):
    """Updates the project version, permanent, cannot be undone
    """
    project = VINFO()
    old = str(project.version)
    vers = project.version.split(".")
    if version == "Major":
        vers[0] = str(int(vers[0])+1)
        vers[1] = str(0)
        vers[2] = str(0)
    if version == "Minor":
        vers[1] = str(int(vers[1])+1)
        vers[2] = str(0)
    if version == "Patch":
        vers[2] = str(int(vers[2])+1)

    project.setVersion(f"{vers[0]}.{vers[1]}.{vers[2]}")
    project = VINFO()
    print(f"Updated Version {old}=>{project.version}")

def newRelease(version,type:str="Patch"):
    """Releases a version of your project
    """
    match version:
        case "a":
            build("alpha")
            subprocess.call(f"pyinstaller {project.p_vinfo}/project.spec --noconfirm --distpath {project.p_project}/dist/ --log-level FATAL")
            clean(" alpha ")
        case "b":
            build("beta")
            subprocess.call(f"pyinstaller {project.p_vinfo}/project.spec --noconfirm --distpath {project.p_project}/dist/ --log-level FATAL")
            clean(" beta ")
        case "c":
            newVersion(type)
            build()
            subprocess.call(f"pyinstaller {project.p_vinfo}/project.spec --noconfirm --distpath {project.p_project}/dist/ --log-level FATAL")
            clean()
        case "sync":
            build("alpha")
            subprocess.call(f"pyinstaller {project.p_vinfo}/project.spec --noconfirm --distpath {project.p_project}/dist/ --log-level FATAL")
            clean(" alpha ")
            build("beta")
            subprocess.call(f"pyinstaller {project.p_vinfo}/project.spec --noconfirm --distpath {project.p_project}/dist/ --log-level FATAL")
            clean(" beta ")
            build()
            subprocess.call(f"pyinstaller {project.p_vinfo}/project.spec --noconfirm --distpath {project.p_project}/dist/ --log-level FATAL")
            clean()
            print("\t- alpha\n\t- beta\n\t- current")
        case _:
            print(f"Could not release Project Version {version}")