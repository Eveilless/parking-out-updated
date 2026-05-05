import os
from os import listdir
from os.path import isfile, join
import requests
import json
import time
import subprocess
import cv2
import shutil
from dotenv import load_dotenv

print("starting")
time.sleep(45)

while True:
    try:
        load_dotenv("/home/pi/parking-in/.env")

        SERVER = os.getenv('SERVER')
        iddev_1loop = os.getenv('IDLOOP1')
        iddev_2loop = os.getenv('IDLOOP2')
        
        IPCam = os.getenv('IP_CAM')
        LPR = os.getenv('LPR')

        if SERVER == None or IPCam == None:
            print("Error config .env")
            print(SERVER)
            print(iddev_1loop)
            print(iddev_2loop)
            
            print(IPCam)
            print(LPR)
        else:
            print(SERVER)
            print(iddev_1loop)
            print(iddev_2loop)
            
            print(IPCam)
            print(LPR)
            break
    except Exception as e:
        time.sleep(1)
        print(e)

RTSP = IPCam
LPR_URL = LPR
iddev = iddev_1loop

print(SERVER)
print(iddev)
print(RTSP)
print(LPR_URL)

URL_time = SERVER+"/get-time"
URL_offline = SERVER+"/send-offline"
URL_picture = SERVER+"/update-picture"

flag_update_time = 0

namaImg = ""
namaImgLPR = ""

def stream(sourceCam, sourceLPR):
    global namaImg
    global namaImgLPR
    #print(sourceCam)
    #print(namaImg)
    #print(sourceLPR)
    #print(namaImgLPR)
    
    cap = cv2.VideoCapture(sourceCam)
    cap.set(cv2.CAP_PROP_FPS, 3000)   #timeout
    
    flagCapture = False
    
    if(cap.isOpened()):
        ret, frame = cap.read()

        if ret == True:
            print("Capturing cam")
            #cv2.moveWindow('Streaming', 0,0) #disable jika run di linux server
            cv2.imwrite(namaImg,frame)
            #cv2.imshow('Streaming', frame)  #disable jika run di linux server
            im = cv2.imread(namaImg)
            rezim = cv2.resize(im, (1280,720))
            cv2.imwrite(namaImg,rezim)
            
            flagCapture = True
        else:
            print("release cam and start again")
            cap.release()
            cap = cv2.VideoCapture(sourceCam)
            time.sleep(0.1)
            
        cap.release()
        cv2.destroyAllWindows()
        
    cap = cv2.VideoCapture(sourceLPR)
    cap.set(cv2.CAP_PROP_FPS, 3000)   #timeout
    
    if(cap.isOpened()):
        ret, frame = cap.read()

        if ret == True:
            print("Capturing LPR")
            #cv2.moveWindow('Streaming', 0,0) #disable jika run di linux server
            cv2.imwrite(namaImgLPR,frame)
            #cv2.imshow('Streaming', frame)  #disable jika run di linux server
            im = cv2.imread(namaImgLPR)
            rezim = cv2.resize(im, (1280,720))
            cv2.imwrite(namaImgLPR,rezim)
            
            flagCapture = True
        else:
            print("release lpr and start again")
            namaImgLPR = namaImg
            cap.release()
            cap = cv2.VideoCapture(sourceLPR)
            time.sleep(0.1)
            
        cap.release()
        cv2.destroyAllWindows()
    else:
        print("LPR no open")
        cap.release()
        cv2.destroyAllWindows()
        time.sleep(0.1)
    
    return flagCapture

RTSP_URL = RTSP

updateTimeFlag = 0
while True:
    updateTimeFlag = updateTimeFlag+1
    
    if updateTimeFlag > 15:
        updateTimeFlag = 0
    
    if updateTimeFlag == 1:
        try:
            getTime = requests.get(URL_time, timeout=3)
            print(getTime.text)
            
            parse = getTime.json()
            if parse["status"] == "success":
                flag_update_time = flag_update_time + 1
                if flag_update_time == 1:
                    timeServer = parse["message"]
                    #sudo date -s '2021-01-04 13:04:00'
                    print(timeServer)
                    proc = subprocess.Popen(["sudo", "date", "-s", timeServer],stdout=subprocess.PIPE, universal_newlines=True)
                    out, err = proc.communicate()
                    #out = out.split(' ')
                    print(out)
                if flag_update_time >= 10:
                    flag_update_time = 0
        except Exception as e:
            print(e)
            time.sleep(1)
            
            
    flagOpen = False
    arrayTicket = []
    try:
        PATH_folder = 'parking-in/'
        #print("open file txt")
        with open(PATH_folder+"ticket-offline.txt", "r") as f:
            lines = f.readlines()
            for line in lines:
                arrayTicket.append(line)
        with open(PATH_folder+"ticket-offline.txt", "w") as f:
            flagOpen = True
            for line in lines:
                #print(line)
                ticketCode = str(line.strip("\n"))
                if len(ticketCode) > 10:
                    #print("sending")
                    sendTicket = requests.post(URL_offline, data={"ticket":ticketCode}, timeout=3)
                    print(sendTicket.text)
                    parseJson = sendTicket.json()
                    if parseJson["status"] == "success":
                        #print("---")
                        #print(ticketCode)
                        if line.strip("\n") != ticketCode:
                            f.write(line)
            f.close()
    except Exception as e:
        with open(PATH_folder+"ticket-offline.txt", "w") as f:  #mencegah file ticket terhapus
            for tck in arrayTicket:
                #print(tck)
                f.write(tck)
            f.close()
        print(e)
        
    
    flagOpen = False
    arrayTicket = []
    try:
        PATH_folder = ''
        #print("open file txt")
        with open(PATH_folder+"ticket-offline.txt", "r") as f:
            lines = f.readlines()
            for line in lines:
                arrayTicket.append(line)
        with open(PATH_folder+"ticket-offline.txt", "w") as f:
            flagOpen = True
            for line in lines:
                #print(line)
                ticketCode = str(line.strip("\n"))
                if len(ticketCode) > 10:
                    #print("sending")
                    sendTicket = requests.post(URL_offline, data={"ticket":ticketCode}, timeout=3)
                    print(sendTicket.text)
                    parseJson = sendTicket.json()
                    if parseJson["status"] == "success":
                        #print("---")
                        #print(ticketCode)
                        if line.strip("\n") != ticketCode:
                            f.write(line)
            f.close()
    except Exception as e:
        with open(PATH_folder+"ticket-offline.txt", "w") as f:  #mencegah file ticket terhapus
            for tck in arrayTicket:
                #print(tck)
                f.write(tck)
            f.close()
        print(e)
    
    
    ###capture and upload image here
    try:
        PATH_folder = 'parking-in/'
        data = listdir(PATH_folder)
        #print(data)

        for x in data:
            print(x[-5:])
            if x[-5:] == ".tyto":
                # check if file exists
                if os.path.exists(PATH_folder+x):
                    #print("open file "+x)
                    dataX = open(PATH_folder+x, 'r').read()
                    #print(dataX)
                    dataXSplit = dataX.split("\n")
                    #print(dataXSplit)
                    ticketCode = dataXSplit[0]
                    namaImg = ticketCode+".jpg"
                    namaImgLPR = "lpr"+ticketCode+".jpg"
                    #print(namaImg)
                    #print(namaImgLPR)
                    #namaImg = "image.jpg"
                    flagCap = False
                    if len(RTSP_URL) < 10:     #fungsi nonaktifkan capture camera
                        flagCap = False
                    else:
                        flagCap = stream(RTSP_URL, LPR_URL)
                    
                    if flagCap:
                        #print("Send with Image")
                        files = {'foto': open(namaImg, 'rb'), 'lpr': open(namaImgLPR, 'rb')}
                        sendData = requests.post(URL_picture, data={"ticket_code":ticketCode}, files=files, timeout=5)
                        print(sendData.text)
                        
                        shutil.copy(namaImg, "/home/pi/parking-in/ipcam")
                        shutil.copy(namaImgLPR, "/home/pi/parking-in/lpr")
                        os.remove(namaImg)
                        os.remove(namaImgLPR)
                    SendOK = True
                    os.remove(PATH_folder+x)
                    
    except Exception as e:
        print(e)
        print("Error Connect", "to Server or Cam")
        
    
    try:
        PATH_folder = ''
        data = listdir(PATH_folder)
        #print(data)

        for x in data:
            #print(x[-5:])
            if x[-5:] == ".tyto":
                # check if file exists
                if os.path.exists(PATH_folder+x):
                    #print("open file "+x)
                    dataX = open(PATH_folder+x, 'r').read()
                    #print(dataX)
                    dataXSplit = dataX.split("\n")
                    #print(dataXSplit)
                    ticketCode = dataXSplit[0]
                    namaImg = ticketCode+".jpg"
                    namaImgLPR = "lpr"+ticketCode+".jpg"
                    #print(namaImg)
                    #print(namaImgLPR)
                    #namaImg = "image.jpg"
                    flagCap = False
                    if len(RTSP_URL) < 10:     #fungsi nonaktifkan capture camera
                        flagCap = False
                    else:
                        flagCap = stream(RTSP_URL, LPR_URL)
                    
                    if flagCap:
                        #print("Send with Image")
                        files = {'foto': open(namaImg, 'rb'), 'lpr': open(namaImgLPR, 'rb')}
                        sendData = requests.post(URL_picture, data={"ticket_code":ticketCode}, files=files, timeout=5)
                        print(sendData.text)
                        
                        shutil.copy(namaImg, "/home/pi/parking-in/ipcam")
                        shutil.copy(namaImgLPR, "/home/pi/parking-in/lpr")
                        os.remove(namaImg)
                        os.remove(namaImgLPR)
                    SendOK = True
                    os.remove(PATH_folder+x)
                    
    except Exception as e:
        print(e)
        print("Error Connect", "to Server or Cam")
    
    time.sleep(1)
