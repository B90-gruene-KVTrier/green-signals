#! /bin/python3

import os
import subprocess
import sys
import tkinter as tk

# imporrt the standard to read and write config files
import configparser

#the main window
master=tk.Tk()

#list of required modules
modules=list()
try:
    import vlc
except:
    modules.append("python-vlc")

try:
    import crontab
except:
    modules.append("python-crontab")

#init variables used in config file and some other places
doAutostart=tk.IntVar()
bild_dauer=tk.IntVar()
DEBUG_PREVIEW=tk.IntVar()
localPath=tk.StringVar()
remoteURL=tk.StringVar()

#set "dirty" flag to False
#any change should set it to True, so we can ask on quit to save data
isDirty=False

def createAutostart():
    '''
    create the auto start file gruene_signale.desktop in $HOME/.config/autostart/
    also create intermediate paths if the do not exist
    when the file already exists, nothing is done
    '''
    autostartfile = os.path.expanduser("~/.config/autostart/gruene_signale.desktop")
    whereami = os.path.dirname(os.path.realpath(__file__))
    contents = """[Desktop Entry]
Type=Application
Name=Green Signals Autostart
Comment=Starten der Slideshow von Grüne Signale
NoDisplay=false
Exec=sh -c 'cd %(path)s && /bin/python3 gruene_signale.py'
"""
    if os.path.isfile(autostartfile) == False:
        if os.path.exists(os.path.dirname(autostartfile)) == False:
            os.makedirs(os.path.dirname(autostartfile))
        file=open(autostartfile,"w")
        file.write(contents%{'path':whereami})
        file.close()

def removeAutostart():
    '''
    check if the auto start file exists, and if it does, remove it
    '''
    autostartfile = os.path.expanduser("~/.config/autostart/gruene_signale.desktop")
    if os.path.isfile(autostartfile) == True:
        os.remove(autostartfile)

def checkAutostartfile():
    '''
    check if the auto start file gruene_signale.desktop already exists
    returns True, if it does, False if not
    '''
    autostartfile = os.path.expanduser("~/.config/autostart/gruene_signale.desktop")
    return int(os.path.isfile(autostartfile))

def installModules():
    global modules
    failed=list()
    for module in modules:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", module])
        except:
            print("install module %s failed" % module)
            failed.append(module)
    modules=failed

def setDirty():
    global isDirty
    isDirty = True

def readConfig(configFile=None):
    global bild_dauer, DEBUG_PREVIEW, localPath, remoteURL, isDirty
    if configFile == None:
        configFile = os.path.dirname(os.path.realpath(__file__)) + os.sep + "gruene_signale.conf"
    config = configparser.ConfigParser()
    config.read(configFile)
    try:
        bild_dauer.set(int(config.get('bilder', 'dauer')))
    except:
        bild_dauer.set(10)
        isDirty = True

    try:
        val = config.get('debug', 'preview')
    except:
        val = "0"
    if val == "1":
        DEBUG_PREVIEW.set(1)

    try:
        val = os.path.realpath(config.get('pfad', 'lokal'))
    except:
        val = os.path.dirname(os.path.realpath(__file__)) + os.sep + "slideshow"
    localPath.set(val)

    #try to read the remote URL, if not given, work offline
    try:
        val = config.get('pfad', 'remote')
        remoteURL.set(val)
    except:
        val = None
        remoteURL.set("")

def writeConfig(configFile=None):
    if configFile == None:
        configFile = os.path.dirname(os.path.realpath(__file__)) + os.sep + "gruene_signale.conf"
    config = configparser.ConfigParser()
    config.read(configFile)

    config.set('bilder','dauer',"%d" % bild_dauer.get())
    config.set('debug', 'preview',"%d" % DEBUG_PREVIEW.get())
    config.set('pfad', 'lokal',localPath.get().strip())
    config.set('pfad', 'remote',remoteURL.get().strip())

    with open(configFile, 'w') as file:
        config.write(file)


def save():
    global isDirty
    if isDirty == False:
        return;
    writeConfig()
    if checkAutostartfile() == 1 and doAutostart.get() == 0:
        removeAutostart()
    if checkAutostartfile() == 0 and doAutostart.get() == 1:
        createAutostart()
    isDirty=False

def quit():
    master.destroy()
    exit(0)


readConfig()

master.minsize(600,300)
master.geometry("800x450+560+300")
master.title("Einstellungen für Grüne Signale")

#add button or notification if Python modules (see above) needs to be installed
row=tk.Frame(master,bd=1,relief=tk.SUNKEN)
lab=tk.Label(row,text="Python Module",width=30,anchor='w')
if len(modules) == 0:
    obj=tk.Label(row,text="installiert",fg="green")
else:
    obj=tk.Button(row,text="Installieren",command=installModules,fg="red")
row.pack(side=tk.TOP,padx=10,pady=10,expand=tk.YES,fill=tk.X)
lab.pack(side=tk.LEFT,pady=10)
obj.pack(side=tk.RIGHT,expand=tk.YES,fill=tk.X,padx=10)

if checkAutostartfile():
    doAutostart.set(1)

#add autostart checkbox
row=tk.Frame(master,bd=1,relief=tk.SUNKEN)
lab=tk.Label(row,text="Grüne Signale automatisch starten",width=30,anchor='w')
obj=tk.Checkbutton(row,text="aktiv",variable=doAutostart,command=setDirty)
row.pack(side=tk.TOP,padx=10,pady=10,expand=tk.YES,fill=tk.X)
lab.pack(side=tk.LEFT,pady=10)
obj.pack(side=tk.RIGHT,expand=tk.YES,fill=tk.X,padx=10)

#add entry field for local path
row=tk.Frame(master,bd=1,relief=tk.SUNKEN)
lab=tk.Label(row,text="lokaler Pfad",width=30,anchor='w')
obj=tk.Entry(row)
obj.insert(10,localPath.get())
row.pack(side=tk.TOP,padx=10,pady=10,expand=tk.YES,fill=tk.X)
lab.pack(side=tk.LEFT,pady=10)
obj.pack(side=tk.RIGHT,expand=tk.YES,fill=tk.X,padx=10)

#add entry field for remoteURL
row=tk.Frame(master,bd=1,relief=tk.SUNKEN)
lab=tk.Label(row,text="Remote-URL (leer für Offline-Modus)",width=30,anchor='w')
obj=tk.Entry(row)
obj.insert(10,remoteURL.get())
row.pack(side=tk.TOP,padx=10,pady=10,expand=tk.YES,fill=tk.X)
lab.pack(side=tk.LEFT,pady=10)
obj.pack(side=tk.RIGHT,expand=tk.YES,fill=tk.X,padx=10)

#add checkbox for Debug Preview Mode
row=tk.Frame(master,bd=1,relief=tk.SUNKEN)
lab=tk.Label(row,text="Debug Preview Modus",width=30,anchor='w')
obj=tk.Checkbutton(row,text="aktiv",variable=DEBUG_PREVIEW,command=setDirty)
row.pack(side=tk.TOP,padx=10,pady=10,expand=tk.YES,fill=tk.X)
lab.pack(side=tk.LEFT,pady=10)
obj.pack(side=tk.RIGHT,expand=tk.YES,fill=tk.X,padx=10)

#add buttons
row=tk.Frame(master)
saveButton=tk.Button(row,text="Übernehmen",command=save,pady=4,padx=10)
saveButton.pack(side=tk.LEFT,pady=10,padx=10)
quitButton=tk.Button(row,text="Beenden",command=quit,pady=4,padx=10)
quitButton.pack(side=tk.RIGHT,pady=10,padx=10)
row.pack(side=tk.BOTTOM)

master.mainloop()