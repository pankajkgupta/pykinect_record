################################################################################
# Python script to record KinectV2 depth sensors.
# The code sends specific triggers on the parallel port to signal the recording status
# Reads config.ini for parameters for recording
# Author(s)	: Pankaj Kumar Gupta
# email		: pankajkmrgupta@gmail.com
################################################################################

import ctypes
import _ctypes
import pygame
import sys
import numpy as np

from pykinect2 import PyKinectV2
from pykinect2.PyKinectV2 import *
from pykinect2 import PyKinectRuntime

from psychopy import parallel
from ConfigParser import SafeConfigParser

if sys.hexversion >= 0x03000000:
    import _thread as thread
else:
    import thread

from datetime import datetime
import os

configSec = 'DEFAULT'
config = SafeConfigParser()
config.read('config.ini')
EPOCH_LEN = int(config.get(configSec, 'EPOCH_LEN'))

trigWidth = int(config.get(configSec, 'trigWidth'))
T_SESSION_START = int(config.get(configSec, 'T_SESSION_START'))
T_START = int(config.get(configSec, 'T_START'))
T_SESSION_END = int(config.get(configSec, 'T_SESSION_END'))
T_INTERVAL = int(config.get(configSec, 'T_INTERVAL'))
T_BG = int(config.get(configSec, 'T_BG'))
n_epoch = int(config.get(configSec, 'N_EPOCH'))
pin_order = map(int, (config.get(configSec, 'PIN')).split(','))

# colors for drawing different bodies 
SKELETON_COLORS = [pygame.color.THECOLORS["red"],
                    pygame.color.THECOLORS["blue"], 
                    pygame.color.THECOLORS["green"],
                    pygame.color.THECOLORS["orange"], 
                    pygame.color.THECOLORS["purple"], 
                    pygame.color.THECOLORS["yellow"], 
                    pygame.color.THECOLORS["violet"]]


class InfraRedRuntime(object):
    def __init__(self):
        pygame.init()

        # Used to manage how fast the screen updates
        self._clock = pygame.time.Clock()

        # Loop until the user clicks the close button.
        self._done = False

        # Used to manage how fast the screen updates
        self._clock = pygame.time.Clock()

        # Kinect runtime object, we want only color and body frames 
        self._kinect = PyKinectRuntime.PyKinectRuntime(PyKinectV2.FrameSourceTypes_Depth)

        # back buffer surface for getting Kinect infrared frames, 8bit grey, width and height equal to the Kinect color frame size
        self._frame_surface = pygame.Surface((self._kinect.depth_frame_desc.Width, self._kinect.depth_frame_desc.Height), 0, 24)
        # here we will store skeleton data 
        self._bodies = None
        
        # Set the width and height of the screen [width, height]
        self._infoObject = pygame.display.Info()
        self._screen = pygame.display.set_mode((self._kinect.depth_frame_desc.Width, self._kinect.depth_frame_desc.Height),
                                                pygame.HWSURFACE|pygame.DOUBLEBUF|pygame.RESIZABLE, 32)

        self.pport = parallel.ParallelPort(address="0xCFF8")

        pygame.display.set_caption("Kinect for Windows v2 Depth")

    def send_trigger(self, code):
        global trigWidth
        re_ordered = ""
        bnry = "{0:08b}".format(code)[::-1]
        for pin in pin_order: re_ordered += bnry[pin]
        ordered_code = int(re_ordered[::-1], 2)
        for tl in range(trigWidth):
            self.pport.setData(ordered_code)


    def draw_depth_frame(self, frame, target_surface):
        if frame is None:  # some usb hub do not provide the infrared image. it works with Kinect studio though
            return
        target_surface.lock()
        f8=np.uint8(frame.clip(1,4000)/16.)
        frame8bit=np.dstack((f8,f8,f8))
        address = self._kinect.surface_as_array(target_surface.get_buffer())
        ctypes.memmove(address, frame8bit.ctypes.data, frame8bit.size)
        del address
        target_surface.unlock()

    def run(self):

        dataPath = config.get(configSec, 'dataPath')
        t = datetime.now()
        dataPath = dataPath + str(t.year) + format(t.month, '02d') + format(t.day, '02d') + \
                   format(t.hour, '02d') + format(t.minute, '02d') + format(t.second, '02d')
        if not os.path.exists(dataPath):
            print "Creating data directory: %s" % dataPath
            os.makedirs(dataPath)

        # save the configuration used
        with open(dataPath + '/config.ini', 'w') as f:
            config.write(f)

        iDepthFrame = 0
        tr_epoch = 1
        t_start = datetime.now()
        # Start of the session
        self.send_trigger(T_SESSION_START)
        # -------- Main Program Loop -----------
        logFileName = dataPath + os.sep + "depth_times.txt"
        with open(logFileName, 'w') as logFile:
            while not self._done:
                # --- Main event loop
                for event in pygame.event.get(): # User did something
                    if event.type == pygame.QUIT: # If user clicked close
                        self.send_trigger(T_SESSION_END)
                        self._done = True # Flag that we are done so we exit this loop

                    elif event.type == pygame.VIDEORESIZE: # window resized
                        self._screen = pygame.display.set_mode(event.dict['size'], 
                                                    pygame.HWSURFACE|pygame.DOUBLEBUF|pygame.RESIZABLE, 32)


                # --- Getting frames and drawing  
                if self._kinect.has_new_depth_frame():
                    sttime = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
                    iDepthFrame += 1

                    if tr_epoch == n_epoch:
                        tr_epoch = 1
                    if iDepthFrame % T_INTERVAL == 0:
                        print "Send frame: " + str(iDepthFrame)
                        self.send_trigger(tr_epoch)
                        tr_epoch += 1
                    else:
                        self.send_trigger(T_BG)

                    frame = self._kinect.get_last_depth_frame()
                    self.draw_depth_frame(frame, self._frame_surface)
                    fName = dataPath + os.sep + "depth_{:10}.png".format(iDepthFrame)
                    pygame.image.save(self._frame_surface, fName)
                    logFile.write(str(iDepthFrame) + '\t' + sttime + "\n")
                    frame = None
                    print "Frame : {}	Time : {} ...".format(iDepthFrame, datetime.now() - t_start)

                self._screen.blit(self._frame_surface, (0,0))
                pygame.display.update()

                # --- Go ahead and update the screen with what we've drawn.
                pygame.display.flip()

                # --- Limit to 60 frames per second
                self._clock.tick(60)

        # Close our Kinect sensor, close the window and quit.
        self._kinect.close()
        pygame.quit()


__main__ = "Kinect v2 InfraRed"
game =InfraRedRuntime();
game.run();

