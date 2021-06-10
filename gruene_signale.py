#! /bin/python3

# import VLC module used for playback of files
import vlc
# TKinter is used to preapre the GUI window
import tkinter as tk

# import sys, shutil and osutil for file system access
import sys
import shutil
import os
import time
# imporrt the standard to read and write config files
import configparser
# threading is used during playback
from threading import Thread, Event
# operator is used to sort the files
import operator
# when we download new media from "remote" it will be a zip file
import zipfile
# used for downloading the fles from remote
import requests
# used to call to shutdown or vcgencmd
import subprocess

# below lines for develepment only
# When DEBUG_PREVIEW is set to True, then te dislay will only cover
# the lower right quarter of the screen
DEBUG_PREVIEW = False

# below variabels are fr configuration purposes
# they are usually overwritten from the config file
bild_dauer = 10
localPath = "./slideshow"
remoteURL = None
#below URL downloads the Intro as zip - just for reference
introURL="https://wolke.netzbegruenung.de/s/2TPGWN5FtWYy2d8/download"

localPathExists = False

# below file extensions are accepted for images
image_extensions = ['png', 'jpg', 'jpeg']
#below file extensions are accepted for videos
movie_extensions = ['mov', 'mp4', 'm4v']


#start update with 2nd media - but only once
update=0

#some variables related to system clock and energy savings and timed events
clockInSync=False
clockTimer=None
energySavingMode = 0
energySavingStart = time.gmtime(0)
energySavingEnd = time.gmtime(0)
energySavingDuration = 0

def readConfig(configFile=None):
    global bild_dauer, DEBUG_PREVIEW, localPath, remoteURL, localPathExists
    global energySavingMode, energySavingStart, energySavingEnd, energySavingDuration
    needsWrite = False
    pathToMe = os.path.realpath(sys.argv[0])
    if configFile == None:
        configFile = pathToMe.replace(".py", ".conf")
    config = configparser.ConfigParser()
    config.read(configFile)
    try:
        bild_dauer = int(config.get('bilder', 'dauer'))
    except:
        config.set('bilder', 'dauer', "10")
        needsWrite = True

    try:
        val = config.get('debug', 'preview')
    except:
        val = "0"
    if val == "1":
        DEBUG_PREVIEW = True

    try:
        localPath = os.path.realpath(config.get('pfad', 'lokal'))
    except:
        localPath = os.path.realpath(os.path.dirname(pathToMe) + os.sep + "slideshow")
        config.set('pfad', 'lokal', localPath)
        needsWrite = True
    localPathExists = os.path.exists(localPath)

    #try to read the remote URL, if not given, work offline
    try:
        remoteURL = config.get('pfad', 'remote').strip()
        if len(remoteURL) == 0:
            remoteURL = None
    except:
        remoteURL = None
        
    #try to read energySaving Info
    try:
        val = int(config.get('energy','mode'))
    except:
        val = 0
        config.set('energy','mode',0)
        config.set('energy','start',"0:00")
        config.set('energy','stop',"0:00")
        needsWrite=True
    energySavingMode = val
    
    if enenergySavingMode > 0:
        #when energy saving is disabled we do not need this stuff
        h = 0
        m = 0
        try:
            val = config.get('energy','start')
            if val.startswith("-"):
                #this is not a time but a duration, which is number of hours
                energySavingsDuration = -int(val)
            else:
                h=int(val.split(":")[0])
                m=int(val.split(":")[1])
                energySavingStart.tm_hour = h
                energySavingStart.tm_minute = m
        except:
            energySavingMode = 0
            config.set('energy','mode',0)
            config.set('energy','start',"0:00")
            config.set('energy','stop',"0:00")
            needsWrite=True
        
    if energySavingMode == 2:
        # we only needs this for wakeup blanked screen
        try:
            val = config.get('energy','stop')
                h=int(val.split(":")[0])
                m=int(val.split(":")[1])
                energySavingStop.tm_hour = h
                energySavingStop.tm_minute = m
        except:
            energySavingMode = 0
            config.set('energy','mode',0)
            config.set('energy','start',"0:00")
            config.set('energy','stop',"0:00")
            needsWrite=True    

    if needsWrite == True:
        with open(configFile, 'w') as file:
            config.write(file)

class RemoteData:
    def __init__(self):
        self.remoteURL = remoteURL
        if remoteURL == None:
            self.offline = True
        else:
            self.offline = False
        self.localZIP = "./download.zip"
        self.localUnZIP = "./temp"
        self.failed = False

    def downloadRemote(self,ui):
        #stream the remote path into download.zip
        if self.offline == True:
            return True
        r = requests.get(self.remoteURL, stream = True)
        if r.status_code != 200:
            ui.showInfo("Die URL '%(url)s' kann nicht geladen werden. Status Code = %(status)d" % {'url':self.remoteURL, 'status':r.status_code},True)
            time.sleep(5)
            self.failed = True
        else:
            #print(r.headers)
            length = 0
            ui.showInfo("Die Daten werden geladen:",True)
            #print("download to %s" % self.localZIP)
            with open(self.localZIP, "wb") as zipped:
                for chunk in r.iter_content(chunk_size = 4096):
                    if chunk:
                        zipped.write(chunk)
                        length += len(chunk)
                        ui.showInfo("Daten werden geladen: %d kB" % (length/1024))
                        #print("%d kB" % (length/1024), end="\r")
            ui.showInfo("Daten wurden erfolgreich geladen: %d kB" % (length/1024))
            time.sleep(1)
            result = self.updateLocalData()
            if result == True:
                os.remove(self.localZIP)
            self.failed = result
        return self.failed

    def updateLocalData(self):
        '''
        Update the local data withh the contents of the ZIP recently downloaded
        Ths function usually is called from downloadRemote above
        '''
        global localPathExists
        #unzip the downloaded file
        try:
            with zipfile.ZipFile(self.localZIP, 'r') as zipRef:
                zipRef.extractall(self.localUnZIP)
        except:
            print("Error while unzipping the downloaded data.")
            return False
        
        if localPathExists:
            #move orignal localPath away
            shutil.move(localPath, localPath+".old")
        #rename unzipped new data
        shutil.move(self.localUnZIP, localPath)
        if localPathExists:
            #remove old data
            shutil.rmtree(localPath+".old", True, None)
        localPathExists = True
        return True

# this class creates an invisible window to catch keboard events
class HiddenRoot(tk.Tk):
    def __init__(self):
        global bild_dauer
        tk.Tk.__init__(self)
        #hackish way, essentially makes root window
        #as small as possible but still "focused"
        #enabling us to use the binding on <esc>
        self.wm_geometry("0x0+0+0")

        self.window = MySlideShow(self)
        self.window.startSlideShow()
        
    def nextMedia(self):
        self.window.nextMedia()
        
    def previousMedia(self):
        self.window.pixNum = self.window.pixNum -2
        if self.window.pixNum < 0:
            self.window.pixNum = self.window.pixNum + len(self.window.mediaList)
        self.window.nextMedia()
        
    def shutdown(self):
        subprocess.check_call(["shutdown","--no-wall","+1"])
        self.destroy()

    def destroy(self):
        self.window.player.stop()
        self.window.destroy()
        exit(0)


# this class contains some info about media files
# it includes some media meta data especially duration of video clips
class Mediafile:
    def __init__(self,filename,caller):
        self.filename = filename
        self.type = "unknown"
        self.duration = 0
        self.valid = False
        extension = os.path.basename(filename).split(".")[-1]
        if extension in image_extensions:
            print("image file:        "+os.path.basename(filename))
            self.valid = True
        elif extension in movie_extensions:
            media = caller.instance.media_new(filename)
            media.parse()
            self.duration = media.get_duration()
            self.valid = True
            print("movie file:        "+os.path.basename(filename)+ " (%d Sekunden)"%(self.duration/1000))
        else:
            print("unknwon file type: "+os.path.basename(filename))


class MySlideShow(tk.Toplevel):
    def __init__(self, *args, **kwargs):
        tk.Toplevel.__init__(self, *args, **kwargs)
        #remove window decorations 
        self.overrideredirect(True)
        self.info = None
        self.infoText = tk.StringVar()
        #by default info widget is hidden
        self.infoHidden = True
        self.bg = (0,0,0)

        #intialize the timer for the slideshow
        self.paused = False
        self.timer = None

        #set the geometry of the playback window
        self.scr_w, self.scr_h = self.winfo_screenwidth(), self.winfo_screenheight()
        if DEBUG_PREVIEW == None or DEBUG_PREVIEW == True:
            self.scr_w = int(self.scr_w / 4)
            self.scr_h = int(self.scr_h / 4)
            self.scr_t = self.scr_h*3 - 10
            self.scr_l = self.scr_w*3 - 10
            self.font = "Courier 8"
        else:
            self.scr_t = 0
            self.scr_l = 0
            self.font = "Courier 12"
            # hide the mouse cursor if not in debug mode
            self.config(cursor="none")

        #This creates the widget where files are played back
        self.player = None
        self.videopanel = tk.Frame(self, bg="black")
        self.videopanel.pack(side="top",fill=tk.BOTH,expand=1)

        #VLC player init
        self.instance = vlc.Instance("--no-xlib --quiet --fullscreen --")
        self.player = self.instance.media_player_new()
        self.player.video_set_scale(0)
        self.player.video_set_aspect_ratio('16:9')
        self.player.video_set_deinterlace('auto')
        self.player.video_set_mouse_input(False)
        self.player.video_set_key_input(False)

        #setup the window
        self.wm_geometry("{}x{}+{}+{}".format(self.scr_w, self.scr_h,self.scr_l,self.scr_t))
        self.player.set_xwindow(self.GetHandle()) # this line messes up windows
        
        #some brief internal initializers
        self.mediaList = list()
        self.pixNum = 0

    def startup(self):
        if os.path.exists(localPath) == False:
            self.showInfo("Der Pfad '%s' wurde nicht gefunden" % localPath, True)
            time.sleep(1)
            if remoteURL == None:
                tk.messagebox.showerror("Keine Medien gefunden", "Das Verzeichnis\n'"+localPath+"'\nwurde nicht gefunden.")
                exit(0)
        #get Media Files
        self.showInfo("Gruene Signale wird gestartet", True)
        time.sleep(1)
        self.updateMedia()

    def toggleInfo(self):
        # This creates an info widget
        if self.infoHidden == True or self.info == None:
            self.infoHidden = False
            self.info = tk.Label(self, bg="#00FF44", font=self.font, height=-1, width=-1, textvariable=self.infoText, wraplength=self.scr_w-16)
            self.info.place(x=8,y=6)
        else:
            self.infoHidden = True
            self.info.destroy()
            self.info = None
             
         
    def showInfo(self,_text,_force=False):
        if self.infoHidden == True and _force == True:
            self.toggleInfo()
        self.infoText.set(_text)
        self.update()
            
    def hideInfo(self):
        if self.infoHidden == False:
            self.toggleInfo()

    def getMedia(self):
        '''
        Get image directory from command line or use current directory
        '''
        curr_dir = localPath
        self.pixNum = 0
        self.mediaList=list()

        for root, dirs, files in os.walk(curr_dir):
            for f in files:
                if f.startswith("._"):
                    continue
                item = Mediafile(os.path.join(root, f),self)
                if item.valid == True:
                    self.mediaList.append(item)
        self.mediaList.sort(key=operator.attrgetter('filename'))
        if len(self.mediaList) == 0:
            tk.messagebox.showerror("Keine Medien gefunden", "Im Pfad/n'"+localpath+"'/nwurden keine Mediendateien gefunden")
            self.destroy()
            exit(1)
        else:
            self.showInfo("%d Medien gefunden" % len(self.mediaList))
            time.sleep(2)
        self.hideInfo()

    def startSlideShow(self):
        self.after(500,self.startup)

    def nextMedia(self):
        global bild_dauer, update
        if self.paused == True:
            if self.timer != None:
                self.after_cancel(self.timer)
                self.timer=None
            return
        #print(self.pixNum)
        media = self.mediaList[self.pixNum]
        self.pixNum = (self.pixNum + 1) % len(self.mediaList)
        self.showMedia(media)
        #its like a callback function after n seconds (cycle through pics)
        #movie should be played up to the end
        #images shall be shown as given in delays
        duration = media.duration
        if duration <= 0:
            duration = bild_dauer * 1000
        self.showInfo(os.path.basename(media.filename) + " (%d Sekunden)"%(duration/1000))
        self.timer = self.after(duration, self.nextMedia)

    def showMedia(self, media):
        _media = self.instance.media_new(media.filename)
        _media.parse()
        self.player.set_media(_media)
        self.player.audio_set_mute(True)
        self.player.play()


    def pausePlayback(self):
        self.paused = True
        if self.timer != None:
            self.after_cancel(self.timer)
        self.timer = None
        self.player.stop()

    def resumePlayback(self):
        if self.paused == True:
            self.paused = False
            if self.timer != None:
                self.after_cancel(self.timer)
            self.timer = None
    
    def togglePlayback(self):
        if self.paused == True:
            self.resumePlayback()
            self.nextMedia()
        else:
            self.pausePlayback()

    def updateMedia(self):
        global update
        self.pausePlayback()
        if remoteURL != None:
            self.showInfo("Neue Medien werden geladen", True)
            time.sleep(2)
            update = RemoteData()
            result = update.downloadRemote(self)
        else:
            self.showInfo("Es ist keine Remote-URL konfiguriert.",True)
            time.sleep(2)
        update = 0
        self.getMedia()
        self.hideInfo()
        self.resumePlayback()
        self.nextMedia()
        
    def blankScreenOn(self):
        #energy savings - start blank screen
        self.pausePlayback()
        subprocess.check_call(["vcgencmd","display_power","0"])
        time.sleep(10)
        self.blankScreenOff()
        
    def blankScreenOff(self):
        #energy savings - end blank screen
        self.updateMedia()
        subprocess.check_call(["vcgencmd","display_power","1"])

    def checkNTPClock(self):
        global clockInSync
        # timedatectl show tells me, if the clock is synchronized via NTP
        for line in subprocess.check_output(["timedatectl","show"]).split():
            if line.decode().split("=")[0] == "NTPSynchronized" and line.decode().split("=")[1] == "yes":
                clockInSync=True
        #if clockInSync == False:
        #    clockTimer=self.after(60*1000,self.checkNTPClock)
        
    def GetHandle(self):
        return self.videopanel.winfo_id()

## ENTRY POINT ##
readConfig()

slideShow = HiddenRoot()

slideShow.bind("<Escape>", lambda e: slideShow.destroy())  # exit on esc
slideShow.bind("<Right>", lambda e: slideShow.nextMedia()) # right-arrow key for next image
slideShow.bind("<Left>", lambda e: slideShow.previousMedia()) # left-arrow key for previous image
slideShow.bind("U", lambda e: slideShow.window.updateMedia()) # start download of new media
slideShow.bind("P", lambda e: slideShow.window.togglePlayback()) # toggle playback
slideShow.bind("i", lambda e: slideShow.window.toggleInfo()) # toggle display of info widget

if DEBUG_PREVIEW == 1:
    #some featurres are only availade whith DEBUG Preview enabled
    slideShow.bind("B", lambda e: slideShow.window.blankScreenOn()) # briefly test blank screen feature
    slideShow.bind("S", lambda e: slideShow.shutdown()) # schedule shutdown and exit the slideshow
slideShow.mainloop()
