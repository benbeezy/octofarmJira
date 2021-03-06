import requests
import time
from requests.auth import HTTPBasicAuth
import json
import yaml
import jira
import os
import time
from datetime import datetime

### importing confits ###
with open("config.yml", "r") as yamlfile:
    config = yaml.load(yamlfile, Loader=yaml.FullLoader)
with open("printers.yml", "r") as yamlfile:
    printers = yaml.load(yamlfile, Loader=yaml.FullLoader)

### This will look at the prints we have waiting and see if a printer is open for it ###
def TryPrintingFile(file):
    for printer in printers['farm_printers']:
        apikey = printers['farm_printers'][printer]['api']
        printerIP = printers['farm_printers'][printer]['ip']
        materialType = printers['farm_printers'][printer]['materialType']
        materialColor = printers['farm_printers'][printer]['materialColor']
        materialDensity = printers['farm_printers'][printer]['materialDensity']
        printerType = printers['farm_printers'][printer]['printerType']
        
        url = "http://" + printerIP + "/api/job"

        headers = {
            "Accept": "application/json",
            "Host": printerIP,
            "X-Api-Key": apikey
        }
        try:
            response = requests.request(
                "GET",
                url,
                headers=headers
            )
            status = json.loads(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
            if str(status['state']) == "Operational" and str(status['progress']['completion']) != "100.0":
                uploadFileToPrinter(apikey, printerIP, file)
                return
        except requests.exceptions.RequestException as e:  # This is the correct syntax
            print("Skipping " + printer + " due to network error")
            print("code needed to reboot printer is it's having this issue")
### Get the status of the printer you are asking about ###
def GetStatus(ip, api):
    apikey = api
    printerIP = ip
    url = "http://" + printerIP + "/api/job"

    headers = {
        "Accept": "application/json",
        "Host": printerIP,
        "X-Api-Key": apikey
    }
    try:
        response = requests.request(
            "GET",
            url,
            headers=headers
        )
        status = json.loads(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
        return status
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        print(printerIP + "'s raspberry pi is offline and can't be contacted over the network")
        status = "offline"
        return status
### get the name of the printer you are asking about ###
def GetName(ip, api):
    apikey = api
    printerIP = ip
    url = "http://" + printerIP + "/api/printerprofiles"
    name = ip
    headers = {
        "Accept": "application/json",
        "Host": printerIP,
        "X-Api-Key": apikey
    }
    try:
        response = requests.request(
            "GET",
            url,
            headers=headers
        )
        status = json.loads(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))

        name = status["profiles"]["_default"]["name"]
        return name
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        print(printerIP + "'s raspberry pi is offline and can't be contacted over the network")
        status = "offline"
        return name
### probably shouldn't be in the octoprint file but this gets the receipt printer stuff ###
def receiptPrinter(scrapedprNumber, ticketNumber, scrapedPatronName, printer=''):
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    from escpos.printer import Usb

    patronName = scrapedPatronName
    try:
        patronName = str(patronName)
        patronName = patronName.title()
    except:
        patronName = ''

    if len(patronName) > 0:
        firstName = patronName.split(' ')[0]
        lastName = patronName.split(' ')[-1]
        if firstName != lastName:
            patronName = firstName[0] + ', ' + lastName

    try:
        # try to reconnect to printer
        p = Usb(0x0416, 0x5011, 0, 0x81, 0x03)
    except:
        alreadyConnected = True
    try:
        # try to center printing alignment
        p.set(align='center')
    except:
        alreadyAligned = True
    # create new image large enough to fit super long names
    img = Image.new('RGB', (2400, 400), color=(0, 0, 0))
    fnt = ImageFont.truetype(r"recources/arialbd.ttf", 110, encoding="unic")
    tiny = ImageFont.truetype(r"recources/arial.ttf", 20, encoding="unic")
    d = ImageDraw.Draw(img)
    d.text((32, 0), scrapedprNumber, font=fnt, fill=(255, 255, 255))
    firstFew = patronName[:8]
    if 'y' in firstFew or 'g' in firstFew or 'p' in firstFew or 'q' in firstFew:
        d.text((32, 121), patronName, font=fnt, fill=(255, 255, 255))
    else:
        d.text((32, 128), patronName, font=fnt, fill=(255, 255, 255))
    d.text((32, 256), ticketNumber, font=fnt, fill=(255, 255, 255))
    d.text((34, 355), printer, font=tiny, fill=(255, 255, 255))

    imageBox = img.getbbox()
    cropped = img.crop(imageBox)
    inverted = ImageOps.invert(cropped)
    rotated = inverted.rotate(270, expand=True)

    try:
        # print image
        p.image(rotated)
        # cut point
        p.text("\n\n-                              -\n\n")
    except:
        print("\nThe receipt printer is unplugged or not powered on, please double check physical connections.")
        raise ValueError
### Uploads a file to a printer ###
def uploadFileToPrinter(apikey, printerIP, file):
    openFile = open('jiradownloads/' + file + '.gcode', 'rb')
    fle = {'file': openFile, 'filename': file}
    url = "http://" + printerIP + "/api/files/{}".format("local")
    payload = {'select': 'true', 'print': 'true'}
    header = {'X-Api-Key': apikey}
    response = requests.post(url, files=fle, data=payload, headers=header)

    if os.path.exists("jiradownloads/" + file + ".gcode"):
        # print(config['Save_printed_files'])
        if config['Save_printed_files'] == False:
            os.remove("jiradownloads/" + file + ".gcode")
        else:
            os.replace("jiradownloads/" + file + ".gcode", "archive_files/" + file + ".gcode")
        if ticketText != config['messages']['printStarted']:
            # filenamerefrenced
            jira.commentStatus(file, ticketText)
        printerName = GetName(printerIP, apikey)
        print("Now printing: " + file + " on " + printerName + " at " + printerIP)
        
    if config["reciept_printer"]["print_physical_reciept"] == True:
        try:
            printerName = GetName(printerIP, apikey)
            receiptPrinter(projectNumber, ticketNumber, patronName, printerName)
        except:
            print("There was a problem printing the receipt " + projectNumber)
### Resets the connection to a printer, done as a safety check and status clear ###
def resetConnection(apikey, printerIP):
    url = "http://" + printerIP + "/api/connection"
    disconnect = {'command': 'disconnect'}
    connect = {'command': 'connect'}
    header = {'X-Api-Key': apikey}
    response = requests.post(url, json=disconnect, headers=header)
    time.sleep(30)
    response = requests.post(url, json=connect, headers=header)
### If a print is complete update people and mark as ready for new file ###
def PrintIsFinished():
    for printer in printers['farm_printers']:
        apikey = printers['farm_printers'][printer]['api']
        printerIP = printers['farm_printers'][printer]['ip']
        url = "http://" + printerIP + "/api/job"
        headers = {
            "Accept": "application/json",
            "Host": printerIP,
            "X-Api-Key": apikey
        }
        try:
            response = requests.request(
                "GET",
                url,
                headers=headers
            )
            if("State" not in response.text):
                if (json.loads(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))):
                    status = json.loads(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
                else:
                    status = "offline"
            else:
                print(printer + " is having issues and the pi is un-reachable, if this continues restart the pi")
                status = "offline"
        except requests.exceptions.RequestException as e:  # This is the correct syntax
            print(printer + "'s raspberry pi is offline and can't be contacted over the network")
            status = "offline"

        """
        I might want to change some of this code when I am in front of the printers to make it so each printers status get's printed out
        """
        if status != "offline":
            if status['state'] == "Operational":
                if str(status['progress']['completion']) == "100.0":
                    volume = status['job']['filament']['tool0']['volume']
                    grams = volume * printers['farm_printers'][printer]['materialDensity']
                    print(printer + " is finishing up")
                    file = os.path.splitext(status['job']['file']['display'])[0]
                    resetConnection(apikey, printerIP)
                    try:
                        response = "{color:#00875A}Print completed successfully!{color}\n\nPrint was harvested at "
                        response += "Filament Usage ... " + str(grams) + "g"
                        response += "Actual Cost ... (" + str(grams) + "g * $" + str(config["payment"]["costPerGram"]) + "/g) = $"
                        cost = grams * config["payment"]["costPerGram"]
                        cost = str(("%.2f" % (cost)))
                        response += cost + " " + config["messages"]["finalMessage"]
                        jira.commentStatus(file, response)
                    except FileNotFoundError:
                        print("This print was not started by this script, I am ignoring it: " + file)
                    jira.changeStatus(file, "21")  # filenamerefrenced
                    jira.changeStatus(file, "31")  # filenamerefrenced
                    if config['payment']['prepay'] == True:
                        jira.changeStatus(file, "41")  # filenamerefrenced
                else:
                    print(printer + " is ready")
                    continue
            elif status['state'] == "Printing":
                print(printer + " is printing")
            else:
                print(printer + " is offline")

### for each file in the list see if a printer is open for it ###
def eachNewFile():
    directory = r'jiradownloads'
    for filename in sorted(os.listdir(directory)):
        if filename.endswith(".gcode"):
            TryPrintingFile(os.path.splitext(filename)[0])
        else:
            continue
