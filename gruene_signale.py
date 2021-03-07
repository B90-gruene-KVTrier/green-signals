#! /bin/python3

# import VLC module used for playback of files
import vlc
# TKinter is used to preapre the GUI window
import tkinter as tk

# import sys, shutil and osutil for file system access
import sys
import shutil
import os
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

# below lines for develepment only
# When DEBUG_PREVIEW is set to True, then te dislay will only cover
# the lower right quarter of the screen
DEBUG_PREVIEW = False

# below variabels are fr configuration purposes
# they are usually overwritten from the config file
bild_dauer = 10
localPath = "./slideshow"
remoteURL = None
localPathExists = False

# below file extensions are accepted for images
image_extensions = ['png', 'jpg']
#below file extensions are accepted for videos
movie_extensions = ['mov', 'mp4', 'm4v']

#start update with 2nd media - but only once
update=2

def readConfig(configFile=None):
    global bild_dauer, DEBUG_PREVIEW, localPath, remoteURL, localPathExists
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
        remoteURL = config.get('pfad', 'remote')
    except:
        remoteURL = None

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

    def downloadRemote(self):
        if self.offline == True:
            print("Configured for offline mode, add a 'path:remote' entry into the config file")
            return True
        #stream the remote path into download.zip
        r = requests.get(self.remoteURL, stream = True)
        if r.status_code != 200:
            print("URL %(url)s can't be loaded. Status Code = %(status)d" % {'url':self.remoteURL, 'status':r.status_code})
            self.failed = True
        else:
            #print(r.headers)
            length = 0
            print("download to %s" % self.localZIP)
            with open(self.localZIP, "wb") as zipped:
                for chunk in r.iter_content(chunk_size = 4096):
                    if chunk:
                        zipped.write(chunk)
                        length += len(chunk)
                        print("%d kB" % (length/1024), end="\r")
            print("successful download of %d kB of data" % (length/1024))
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
        
# this class simply cares about the fullscreen backdrop and starts playback
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
        
    def destroy(self):
        self.window.player.stop()
        self.window.destroy()
        exit(0)

    def updateMedia(self):
        self.window.updateMedia()

# this class contains some info about media files
# it includes some media meta data especially duration of video clips
class Mediafile:
    def __init__(self,filename,vlcinstance):
        self.filename = filename
        self.type = "unknown"
        self.duration = 0
        self.valid = False
        extension = os.path.basename(filename).split(".")[-1]
        if extension in image_extensions:
            print("image file:        "+filename)
            self.valid = True
        elif extension in movie_extensions:
            media = vlcinstance.media_new(filename)
            media.parse()
            self.duration = media.get_duration()
            self.valid = True
            print("movie file:        "+filename+ " (%d Sekunden)"%(self.duration/1000))
        else:
            print("unknwon file type: "+filename)

class ttkTimer(Thread):
    """a class serving same function as wxTimer... but there may be better ways to do this
    """
    def __init__(self, callback, tick):
        Thread.__init__(self)
        self.callback = callback
        self.stopFlag = Event()
        self.tick = tick
        self.iters = 0

    def run(self):
        while not self.stopFlag.wait(self.tick):
            self.iters += 1
            self.callback()

    def stop(self):
        self.stopFlag.set()

    def get(self):
        return self.iters

class MySlideShow(tk.Toplevel):
    def __init__(self, *args, **kwargs):
        tk.Toplevel.__init__(self, *args, **kwargs)
        #remove window decorations 
        self.overrideredirect(True)
        self.paused = False
        self.info = None

        self.scr_w, self.scr_h = self.winfo_screenwidth(), self.winfo_screenheight()
        if DEBUG_PREVIEW == None or DEBUG_PREVIEW == True:
            self.scr_w = int(self.scr_w / 4)
            self.scr_h = int(self.scr_h / 4)
            self.scr_t = self.scr_h*3 - 10
            self.scr_l = self.scr_w*3 - 10
        else:
            self.scr_t = 0
            self.scr_l = 0
        print(self.scr_w,self.scr_h)

        #save reference to photo so that garbage collection
        #does not clear image variable in show_image()
        self.persistent_image = None
        self.mediaList = list()
        self.bgcolor = (0,0,0)

        # This creates the widget where files are played back
        self.player = None
        self.videopanel = tk.Frame(self, bg="black")
        self.videopanel.pack(side="top",fill=tk.BOTH,expand=1)

        # VLC player init
        self.instance = vlc.Instance("--no-xlib --quiet --fullscreen --")
        self.player = self.instance.media_player_new()
        self.player.video_set_scale(0)
        self.player.video_set_aspect_ratio('16:9')
        self.player.video_set_deinterlace('auto')
        self.player.video_set_mouse_input(False)
        self.player.video_set_key_input(False)

        # get Media Files
        self.getMedia()
        #self.updateMedia()

    def showInfo(self,_text):
        # This creates an info widget
        if self.info == None:
            print("ShowInfo: "+_text)
            self.info = tk.Label(self, bg="#00FF44", height=1, width=int(self.scr_w/9), text=_text)
            self.info.place(x=0,y=0)
        else:
            self.info.configure(text=_text)

    def hideInfo(self):
        if self.info != None:
            print("Hide info")
            self.info.destroy()
            self.info = None

    def getMedia(self):
        '''
        Get image directory from command line or use current directory
        '''
        curr_dir = localPath
        self.pixNum = 0

        for root, dirs, files in os.walk(curr_dir):
            for f in files:
                if f.startswith("._"):
                    continue
                item = Mediafile(os.path.join(root, f),self.instance)
                if item.valid == True:
                    self.mediaList.append(item)
        self.mediaList.sort(key=operator.attrgetter('filename'))

    def startSlideShow(self):
        self.paused = False
        if len(self.mediaList) < 1:
            # nothing to show, so abort
            print("no media files found")
            exit(1)

        self.wm_geometry("{}x{}+{}+{}".format(self.scr_w, self.scr_h,self.scr_l,self.scr_t))
        self.player.set_xwindow(self.GetHandle()) # this line messes up windows
        self.nextMedia()

    def nextMedia(self):
        global bild_dauer, update
        if self.paused == True:
            return
        media = self.mediaList[self.pixNum]
        self.pixNum = (self.pixNum + 1) % len(self.mediaList)
        self.showMedia(media)
        if update > 0:
            if update==1:
                self.updateMedia()
            update -= 1
        #its like a callback function after n seconds (cycle through pics)
        # movie should be played up to the end
        # images shall be shown as given in delays
        timer = media.duration
        if timer <= 0:
            timer = bild_dauer * 1000
        # print(media.filename, timer/1000)
        self.after(timer, self.nextMedia)

    def showMedia(self, media):
        _media = self.instance.media_new(media.filename)
        _media.parse()
        self.player.set_media(_media)
        self.player.audio_set_mute(True)
        self.player.play()

    def pausePlayback(self):
        self.paused = True
        
    def updateMedia(self):
        global update
        if remoteURL != None:
            self.showInfo("Update Media Files")
            self.pausePlayback()
            update = RemoteData()
            result = update.downloadRemote()
            self.hideInfo()
        update = 0
        self.getMedia()
        self.startSlideShow()
        
    def GetHandle(self):
        return self.videopanel.winfo_id()

## ENTRY POINT ##
readConfig()
#autoUpdate = RemoteData()
#result = autoUpdate.downloadRemote()
#if result == False:
#    print("updating the media data failed")

if os.path.exists(localPath) == False:
    print("local path containing media files not found")
    if remoteURL != None:
        print("startng initial media download")
        autoUpdate = RemoteData()
        result = autoUpdate.downloadRemote()
        if result == False:
            print("updating the media data failed")
    else:
        print("add Mediafiles to "+localPath+" or configure Remote URL")
        exit(0)

slideShow = HiddenRoot()
slideShow.bind("<Escape>", lambda e: slideShow.destroy())  # exit on esc
slideShow.bind("<Right>", lambda e: slideShow.nextMedia()) # right-arrow key for next image
slideShow.bind("<Left>", lambda e: slideShow.previousMedia()) # left-arrow key for previous image
slideShow.bind("U", lambda e: slideShow.updateMedia()) # start dwnload of new media
slideShow.mainloop()
