WIFI = True
WINDOWS = False
GAMEPAD = False

if WIFI:
    import socket
else:
    import simplepyble
import time
import struct
import wiiuse # https://github.com/arpruss/pywiiuse
from threading import Thread,Event
import os
if GAMEPAD:
    import vgamepad as vg
from pynput.keyboard import Key, Controller

HOST = "192.168.1.246"
PORT = 8765



def uuid16(n):
    return "0000%04x-0000-1000-8000-00805f9b34fb" % n

CADENCE_SERVICE = uuid16(0x1816)
CSC_MEASUREMENT = uuid16(0x2A5B)

DOWN = 1
UP = 0
WAIT = 2

bleBike = None
prevCrankRev = None
buffer = []
haveOutput = Event()
haveOutput.clear()
if GAMEPAD:
    gamepad = vg.VX360Gamepad()
    xAxis = 0
    yAxis = 0
    print("Gamepad mode")
else:
    keyboard = Controller()
    
wiimotePressed = set()
buttonMap = { wiiuse.button['-']:Key.esc, wiiuse.button['Left']:'4', wiiuse.button['Right']:'6', wiiuse.button['B']:'8', wiiuse.button['+']:'5' }

def emitter():
    global xAxis,yAxis
    while True:
        haveOutput.wait()
        haveOutput.clear()
        oldBuffer = buffer[:]
        buffer.clear()
        if GAMEPAD:
            for state,key in oldBuffer:
                if state == DOWN:
                    if key == Key.esc:
                        gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
                    elif key == '4':
                        xAxis = -1.
                        gamepad.left_joystick_float(x_value_float=xAxis,y_value_float=yAxis)
                    elif key == '6':
                        yAxis = 1.
                        gamepad.left_joystick_float(x_value_float=xAxis,y_value_float=yAxis)
                    elif key == '8':
                        xAxis = -1.
                        yAxis = 1.
                        gamepad.left_joystick_float(x_value_float=xAxis,y_value_float=yAxis)
                    elif key == '5':
                        gamepad.press_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
                    gamepad.update()
                elif state == UP:
                    if key == Key.esc:
                        gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
                    elif key == '4':
                        xAxis = 0.
                        gamepad.left_joystick_float(x_value_float=xAxis,y_value_float=yAxis)
                    elif key == '6':
                        yAxis = 0.
                        gamepad.left_joystick_float(x_value_float=xAxis,y_value_float=yAxis)
                    elif key == '8':
                        xAxis = 0.
                        yAxis = 0.
                        gamepad.left_joystick_float(x_value_float=xAxis,y_value_float=yAxis)
                    elif key == '5':
                        gamepad.release_button(button=vg.XUSB_BUTTON.XUSB_GAMEPAD_A)
                    gamepad.update()
                elif state == WAIT:
                    time.sleep(key)
                gamepad.update()                    
        else:
            for state,key in oldBuffer:
                if state == DOWN:
                    keyboard.press(key)
                elif state == UP:
                    keyboard.release(key)
                elif state == WAIT:
                    time.sleep(key)
            
def wiimoteEvent(w):
    for b in buttonMap:
        if b in wiimotePressed:
            if not wiiuse.is_pressed(w, b):
                wiimotePressed.remove(b)
                buffer.append((UP, buttonMap[b]))
                haveOutput.set()
        else:
            if wiiuse.is_pressed(w, b):
                wiimotePressed.add(b)
                buffer.append((DOWN, buttonMap[b]))
                haveOutput.set()

def processCrankRev(crankRev):                
    global prevCrankRev
    if prevCrankRev is not None:
        count = (crankRev - prevCrankRev) & 0xFFFF
        try:
            for i in range(count):
                if i:
                    buffer.append((WAIT,0.1))
                buffer.append((DOWN,'5'))
                buffer.append((WAIT,0.1))
                buffer.append((UP,'5'))
                haveOutput.set()
        except Exception as e:
            print(e)
    prevCrankRev = crankRev                

def measurement(data):
    flags = data[0]
    if flags & 1:
        # skip wheel rev
        data = data[7:] 
    else:
        data = data[1:]
    if flags & 2:
        crankRev,crankTime = struct.unpack('HH', data)
        processCrankRev(crankRev)

def found(p):
    global bleBike
    print("Found",p.identifier(),p.address())
    try:
        for s in p.services():
            if s.uuid() == CADENCE_SERVICE:
                print("Has cadence service!")
                bleBike = p
                return
    except:
        print("Error scanning services")
        

            
def connectBLE():
    global bleBike
    
    adapter = simplepyble.Adapter.get_adapters()[0]
    print("Selected adapter:", adapter.identifier(), adapter.address())

    adapter.set_callback_on_scan_found(found)
    adapter.scan_start()

    while not bleBike:
        time.sleep(0.2)
        
    adapter.scan_stop()

    if bleBike is None:
        raise Exception("Cannot find "+CADENCE_SERVICE)    
        
    connected = False
    while True:
        try:
            connected = False
            print("Connecting to",bleBike.address())
            bleBike.connect() 
            connected = True
            print("Subscribing to notification")
            contents = bleBike.notify(CADENCE_SERVICE, CSC_MEASUREMENT, measurement)
            print("Subscribed!")
            break
        except Exception as e:
            if not connected:
                print("Error connecting", e)
            else:
                print("Error subscribing", e)
                try:
                    bleBike.disconnect()
                except:
                    pass
            time.sleep(1)
            
def processWiFi():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))    
        print("Socket connected")

        for line in socket.makefile:
            if line.startswith("rotation "):
                data = split(line)
                try:
                    processCrankRev(line[2])
                except Exception as e:
                    print(e)
            
def connectWiFi():
    t = Thread(target=processWiFi)
    t.start()            
    
def connectWiimote():
    while True:
        print("Looking for wiimote")
        found = wiiuse.find(wiimotes, 1, 3)
        if found:
            print("Found wiimote")
            connected = wiiuse.connect(wiimotes, 1)
            if connected:
                print("Connected to wiimote")
                break
            print("Can't connect")
            time.sleep(1)
        else:
            time.sleep(4)            

if WIFI:
    connectWiFi()
else:
    connectBLE()
    
wiimotes = wiiuse.init(1)
connectWiimote()
       
print("Starting output thread")       
outputThread = Thread(target=emitter)
outputThread.start()
    
print("Running!")   
if WINDOWS:
    os.system('start /B c:\\gog\\dosbox\\dosbox -c "mount c \\gog\\athlete" -c c:\\s1.bat')
while True:
    if wiimotes[0][0].event == wiiuse.DISCONNECT or wiimotes[0][0].event == wiiuse.UNEXPECTED_DISCONNECT:
        print("Wiimote disconnected")
        break
    r = wiiuse.poll(wiimotes, 1)
    if r:
        w = wiimotes[0][0]
        wiimoteEvent(w)
    else:
        time.sleep(0.03)
    if not WIFI and not bleBike.is_connected():
        print("Cadence disconnected")
        try:
            bleBike.disconnect()
        except:
            pass
        print("Reconnecting")
        connectBLE()

if not WIFI:
    bleBike.disconnect()
