import os,sys,time,traceback
from math import hypot

import numpy as np
import cv2

import frame_capture
import frame_draw

#-------------------------------
# default settings
#-------------------------------

# camera values
camera_id = 0
camera_width = 1920
camera_height = 1080
camera_frame_rate = 30
#camera_fourcc = cv2.VideoWriter_fourcc(*"YUYV")
camera_fourcc = cv2.VideoWriter_fourcc(*"MJPG")

# auto measure mouse events
auto_percent = 0.2 
auto_threshold = 127
auto_blur = 5

# normalization mouse events
norm_alpha = 0
norm_beta = 255

configfile = 'ldr_config.csv'
if os.path.isfile(configfile):
    with open(configfile) as f:
        for line in f:
            line = line.strip()
            if line and line[0] != '#' and (',' in line or '=' in line):
                if ',' in line:
                    item,value = [x.strip() for x in line.split(',',1)]
                elif '=' in line:
                    item,value = [x.strip() for x in line.split('=',1)]
                else:
                    continue                        
                if item in 'camera_id camera_width camera_height camera_frame_rate camera_fourcc auto_percent auto_threshold auto_blur norm_alpha norm_beta'.split():
                    try:
                        exec(f'{item}={value}')
                        print('CONFIG:',(item,value))
                    except:
                        print('CONFIG ERROR:',(item,value))

# camera setup

# get camera id from argv[1]
# example "python3 ldr.py 2"
if len(sys.argv) > 1:
    camera_id = sys.argv[1]
    if camera_id.isdigit():
        camera_id = int(camera_id)

# camera thread setup
camera = frame_capture.Camera_Thread()
camera.camera_source = camera_id # SET THE CORRECT CAMERA NUMBER
camera.camera_width  = camera_width
camera.camera_height = camera_height
camera.camera_frame_rate = camera_frame_rate
camera.camera_fourcc = camera_fourcc

#1 start camera thread
camera.start()

# initial camera values (shortcuts for below)
width  = camera.camera_width
height = camera.camera_height
area = width*height
cx = int(width/2)
cy = int(height/2)
dm = hypot(cx,cy) # max pixel distance
frate  = camera.camera_frame_rate
print('CAMERA:',[camera.camera_source,width,height,area,frate])

#-------------------------------
# frame drawing/text module 
#-------------------------------

draw = frame_draw.DRAW()
draw.width = width
draw.height = height

#-------------------------------
# define frames
#-------------------------------

# define display frame
framename = "LDR Object Measurement"
cv2.namedWindow(framename,flags=cv2.WINDOW_NORMAL|cv2.WINDOW_GUI_NORMAL)

#-------------------------------
# key events
#-------------------------------

key_last = 0
key_flags = {
             'auto':False,   # a key
             'rotate':False, # r key
             'lock':False,   # 
             }

def key_flags_clear():

    global key_flags

    for key in list(key_flags.keys()):
        if key not in ('rotate',):
            key_flags[key] = False

def key_event(key):

    global key_last
    global key_flags
    global mouse_mark
    global cal_last

    # rotate
    if key == 114:
        if key_flags['rotate']:
            key_flags['rotate'] = False
        else:
            key_flags['rotate'] = True

    # auto mode
    elif key == 97:
        if key_flags['auto']:
            key_flags['auto'] = False
        else:
            key_flags_clear()
            key_flags['auto'] = True
            mouse_mark = None

    # auto percent
    elif key == 112 and key_flags['auto']:
        key_flags['percent'] = not key_flags['percent']
        key_flags['thresh'] = False
        key_flags['lock'] = False

    # auto threshold
    elif key == 116 and key_flags['auto']:
        key_flags['thresh'] = not key_flags['thresh']
        key_flags['percent'] = False
        key_flags['lock'] = False

    # log
    print('key:',[key,chr(key)])
    key_last = key
    
#-------------------------------
# mouse events
#-------------------------------

# mouse events
mouse_raw  = (0,0) # pixels from top left
mouse_now  = (0,0) # pixels from center
mouse_mark = None  # last click (from center)

# mouse callback
def mouse_event(event,x,y,flags,parameters):

    # globals
    global mouse_raw
    global mouse_now
    global mouse_mark
    global key_last
    global auto_percent
    global auto_threshold
    global auto_blur
    global norm_alpha
    global norm_beta

    # update threshold
    if key_flags['thresh']:
        auto_threshold = int(255*x/width)
        auto_blur = int(20*y/height) | 1 # insure it is odd and at least 1


    # update mouse location
    mouse_raw = (x,y)

    # offset from center
    # invert y to standard quadrants
    ox = x - cx
    oy = (y-cy)*-1

    # update mouse location
    mouse_raw = (x,y)
    if not key_flags['lock']:
        mouse_now = (ox,oy)

    # left click event
    if event == 1:

        if key_flags['config']:
            key_flags['lock'] = False
            mouse_mark = (ox,oy)

        elif key_flags['auto']:
            key_flags['lock'] = False
            mouse_mark = (ox,oy)

        if key_flags['percent']:
            key_flags['percent'] = False
            mouse_mark = (ox,oy)
            
        elif key_flags['thresh']:
            key_flags['thresh'] = False
            mouse_mark = (ox,oy)

        elif not key_flags['lock']:
            if mouse_mark:
                key_flags['lock'] = True
            else:
                mouse_mark = (ox,oy)
        else:
            key_flags['lock'] = False
            mouse_now = (ox,oy)
            mouse_mark = (ox,oy)

        key_last = 0

    # right click event
    elif event == 2:
        key_flags_clear()
        mouse_mark = None
        key_last = 0

# register mouse callback
cv2.setMouseCallback(framename,mouse_event)

#-------------------------------
# main loop
#-------------------------------

# loop
while 1:

    # get frame
    frame0 = camera.next(wait=1)
    if frame0 is None:
        time.sleep(0.1)
        continue

    # normalize
    cv2.normalize(frame0,frame0,norm_alpha,norm_beta,cv2.NORM_MINMAX)

    # rotate 180
    if key_flags['rotate']:
        frame0 = cv2.rotate(frame0,cv2.ROTATE_180)

    # start top-left text block
    text = []

    # camera text
    fps = camera.current_frame_rate
    text.append(f'CAMERA: {camera_id} {width}x{height} {fps}FPS')

    # mouse text
    text.append('')
    if not mouse_mark:
        text.append(f'LAST CLICK: NONE')
    else:
        text.append(f'LAST CLICK: {mouse_mark} PIXELS')
    text.append(f'CURRENT XY: {mouse_now} PIXELS')

    #-------------------------------
    # auto mode
    #-------------------------------
    if key_flags['auto']:
        
        mouse_mark = None

        # auto text data
        text.append('')
        text.append(f'AUTO MODE')
        text.append(f'UNITS: {unit_suffix}')
        text.append(f'MIN PERCENT: {auto_percent:.2f}')
        text.append(f'THRESHOLD: {auto_threshold}')
        text.append(f'GAUSS BLUR: {auto_blur}')
        
        # gray frame
        frame1 = cv2.cvtColor(frame0,cv2.COLOR_BGR2GRAY)

        # blur frame
        frame1 = cv2.GaussianBlur(frame1,(auto_blur,auto_blur),0)

        # threshold frame n out of 255 (85 = 33%)
        frame1 = cv2.threshold(frame1,auto_threshold,255,cv2.THRESH_BINARY)[1]

        # invert
        frame1 = ~frame1

        # find contours on thresholded image
        contours,nada = cv2.findContours(frame1,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        
        # small crosshairs (after getting frame1)
        draw.crosshairs(frame0,5,weight=2,color='green')    
    
        # loop over the contours
        for c in contours:

            # contour data (from top left)
            x1,y1,w,h = cv2.boundingRect(c)
            x2,y2 = x1+w,y1+h
            x3,y3 = x1+(w/2),y1+(h/2)

            # percent area
            percent = 100*w*h/area
            
            # if the contour is too small, ignore it
            if percent < auto_percent:
                    continue

            # if the contour is too large, ignore it
            elif percent > 60:
                    continue

            # convert to center, then distance
            x1c,y1c = conv(x1-(cx),y1-(cy))
            x2c,y2c = conv(x2-(cx),y2-(cy))
            xlen = abs(x1c-x2c)
            ylen = abs(y1c-y2c)
            alen = 0
            if max(xlen,ylen) > 0 and min(xlen,ylen)/max(xlen,ylen) >= 0.95:
                alen = (xlen+ylen)/2              
            carea = xlen*ylen

            # plot
            draw.rect(frame0,x1,y1,x2,y2,weight=2,color='red')

            # add dimensions
            draw.add_text(frame0,f'{xlen:.2f}',x1-((x1-x2)/2),min(y1,y2)-8,center=True,color='red')
            draw.add_text(frame0,f'Area: {carea:.2f}',x3,y2+8,center=True,top=True,color='red')
            if alen:
                draw.add_text(frame0,f'Avg: {alen:.2f}',x3,y2+34,center=True,top=True,color='green')
            if x1 < width-x2:
                draw.add_text(frame0,f'{ylen:.2f}',x2+4,(y1+y2)/2,middle=True,color='red')
            else:
                draw.add_text(frame0,f'{ylen:.2f}',x1-4,(y1+y2)/2,middle=True,right=True,color='red')

    #-------------------------------
    # dimension mode
    #-------------------------------
    else:

        # small crosshairs
        draw.crosshairs(frame0,5,weight=2,color='green')    

        # mouse cursor lines
        draw.vline(frame0,mouse_raw[0],weight=1,color='green')
        draw.hline(frame0,mouse_raw[1],weight=1,color='green')
       
        # draw
        if mouse_mark:

            # locations
            x1,y1 = mouse_mark
            x2,y2 = mouse_now

            # convert to distance
            x1c,y1c = conv(x1,y1)
            x2c,y2c = conv(x2,y2)
            xlen = abs(x1c-x2c)
            ylen = abs(y1c-y2c)
            llen = hypot(xlen,ylen)
            alen = 0
            if max(xlen,ylen) > 0 and min(xlen,ylen)/max(xlen,ylen) >= 0.95:
                alen = (xlen+ylen)/2              
            carea = xlen*ylen

            # print distances
            text.append('')
            text.append(f'X LEN: {xlen:.2f}{unit_suffix}')
            text.append(f'Y LEN: {ylen:.2f}{unit_suffix}')
            text.append(f'L LEN: {llen:.2f}{unit_suffix}')

            # convert to plot locations
            x1 += cx
            x2 += cx
            y1 *= -1
            y2 *= -1
            y1 += cy
            y2 += cy
            x3 = x1+((x2-x1)/2)
            y3 = max(y1,y2)

            # line weight
            weight = 1
            if key_flags['lock']:
                weight = 2

            # plot
            draw.rect(frame0,x1,y1,x2,y2,weight=weight,color='red')
            draw.line(frame0,x1,y1,x2,y2,weight=weight,color='green')

            # add dimensions
            draw.add_text(frame0,f'{xlen:.2f}',x1-((x1-x2)/2),min(y1,y2)-8,center=True,color='red')
            draw.add_text(frame0,f'Area: {carea:.2f}',x3,y3+8,center=True,top=True,color='red')
            if alen:
                draw.add_text(frame0,f'Avg: {alen:.2f}',x3,y3+34,center=True,top=True,color='green')           
            if x2 <= x1:
                draw.add_text(frame0,f'{ylen:.2f}',x1+4,(y1+y2)/2,middle=True,color='red')
                draw.add_text(frame0,f'{llen:.2f}',x2-4,y2-4,right=True,color='green')
            else:
                draw.add_text(frame0,f'{ylen:.2f}',x1-4,(y1+y2)/2,middle=True,right=True,color='red')
                draw.add_text(frame0,f'{llen:.2f}',x2+8,y2-4,color='green')

    # add usage key
    text.append('')
    text.append(f'Q = QUIT')
    text.append(f'R = ROTATE')
    text.append(f'A = AUTO-MODE')

    # draw top-left text block
    draw.add_text_top_left(frame0,text)

    # display
    cv2.imshow(framename,frame0)

    # key delay and action
    key = cv2.waitKey(1) & 0xFF

    # esc ==  27 == quit
    # q   == 113 == quit
    if key in (27,113):
        break

    # key data
    #elif key != 255:
    elif key not in (-1,255):
        key_event(key)

#-------------------------------
# kill sequence
#-------------------------------

# close camera thread
camera.stop()

# close all windows
cv2.destroyAllWindows()

exit()

#-------------------------------
# end
#-------------------------------
