from pyexpat.errors import messages
import requests
from requests.auth import HTTPBasicAuth
import json
import yaml
from google_drive_downloader import GoogleDriveDownloader as gdd
import os
import time

### load all of our config files ###
with open("config.yml", "r") as yamlfile:
    config = yaml.load(yamlfile, Loader=yaml.FullLoader)
with open("lists.yml", "r") as yamlfile:
    userlist = yaml.load(yamlfile, Loader=yaml.FullLoader)
with open("keys.yml", "r") as yamlfile:
    keys = yaml.load(yamlfile, Loader=yaml.FullLoader)
with open("printers.yml", "r") as yamlfile:
    printers = yaml.load(yamlfile, Loader=yaml.FullLoader)

### jira authentical information that gets pulled in from the config ###
auth = HTTPBasicAuth(config['jira_user'], config['jira_password'])

### Get the list of issues in the jira project ###
def issueList():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("Checking for new submissions...")
    url = config['base_url'] + "/rest/api/2/" + config['search_url']
    headers = {
       "Accept": "application/json"
    }
    
    response = requests.request(
       "GET",
       url,
       headers=headers,
       auth=auth
    )

    # parse all open projects:
    openissues = json.loads(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
    issues= []
    for issue in openissues['issues']:
        issues.append(issue['self'])
    return issues

### Gets the files and puts them where they need to be ###
def getGcode():
    for issue in issueList():
        id = issue.split("/")
        singleID = id[-1]
        url = issue
        headers = {
           "Accept": "application/json"
        }
        
        response = requests.request(
           "GET",
           url,
           headers=headers,
           auth=auth
        )

        # parse all open projects:
        singleIssue = json.loads(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
        user = singleIssue['fields']['reporter']['name']
        
        #parsing class key value
        start = "*Class Key* \\\\"
        end = "\n\n*Description of print*"
        s = singleIssue['fields']['description']
        classKey = s[s.find(start)+len(start):s.rfind(end)]
        
        ## keys can be validated and update the key logs but keys do not change if a print is to be printed or not yet.
        
        
        ##If someone is nice they go in here
        if user in userlist["NICE"] and config["use_nice_list"] == True:
            printIsGoodToGo(singleIssue, singleID, classKey)
        #if they are naughty they go in here
        elif user in userlist["NAUGHTY"] and config["use_naughty_list"] == True:
            printIsNoGo(singleID, singleID)
            if os.path.exists("jiradownloads/" + singleID + ".gcode"):
                os.remove("jiradownloads/" + singleID + ".gcode")
        # if they are a new user they go in here
        else :
            if config["use_naughty_list"] == True:
                printIsGoodToGo(singleIssue, singleID, classKey)
            elif config["use_nice_list"] == True:
                printIsNoGo(singleIssue, singleID)
            elif config["use_naughty_list"] == False and config["use_naughty_list"] == False:
                printIsGoodToGo(singleIssue, singleID, classKey)

### if the jira project has a google drive link in the description download it ###
def downloadGoogleDrive(file_ID, singleID):
    if config['Make_files_anon'] == True:
        gdd.download_file_from_google_drive(file_id=file_ID, dest_path="jiradownloads/" + singleID + ".gcode")
        file = open("jiradownloads/" + singleID + ".gcode", "r")
    else:
        gdd.download_file_from_google_drive(file_id=file_ID, dest_path="jiradownloads/" + file_ID + "__" + singleID + ".gcode")
        file = open("jiradownloads/" + file_ID + "__" + singleID + ".gcode", "r")
    
    if checkGcode(file.read()) == "Bad G-code":
        print("Go check the gcode file");
        time.sleep(120);
        commentStatus(singleID, config['messages']['wrongConfig'])
        changeStatus(singleID, "11")
        changeStatus(singleID, "21")
        changeStatus(singleID, "131")
        if os.path.exists("jiradownloads/" + singleID + ".gcode"):
            os.remove("jiradownloads/" + singleID + ".gcode")
    else:
        changeStatus(singleID, "11")
        commentStatus(singleID, config['messages']['downloadedFile'])

### Downloads the files that getGcode wants ###
def download(gcode, singleID, filename):
    url = gcode
    
    headers = {
       "Accept": "application/json"
    }
    
    response = requests.request(
       "GET",
       url,
       headers=headers,
       auth=auth
    )
    if checkGcode(response.text) == "Bad G-code":
        commentStatus(singleID, config['messages']['wrongConfig'])
        changeStatus(singleID, "11")
        changeStatus(singleID, "21")
        changeStatus(singleID, "131")
    else:
        if config['Make_files_anon'] == True:
            text_file = open("jiradownloads/" + singleID + ".gcode", "w")
        else:
            text_file = open("jiradownloads/" + filename + "__" + singleID + ".gcode", "w")
            
        for injectGcode in config['inject_gcode']
            injection == injection + injectGcode +" \n";
            
        n = text_file.write(response.text + injection.text)
        text_file.close()
        changeStatus(singleID, "11")
        commentStatus(singleID, config['messages']['downloadedFile'])
        

### Check if gcode fits the requirements that we have set in the config ###
def checkGcode(file):
    status = True
    for code_check in config['gcode_check_text']:
        code_to_check = config['gcode_check_text'][code_check]
        print(code_to_check)
        if code_to_check not in file:
            status = False
        if status == False:
            print("File is bad at: " + code_check)
            return "Bad G-code"
    if status == True:
        print("File checkedout as good")
        return "Valid G-code"
### If the print is a no go and shouldn't continue ###
def printIsNoGo(singleIssue, singleID):
    attachments = str(singleIssue).split(',')
    if any(config['base_url'] + "/secure/attachment" in s for s in attachments):
        print("Downloading " + singleID)
        matching = [s for s in attachments if config['base_url'] + "/secure/attachment" in s]
        attachment = str(matching[0]).split("'")
        filename = attachment[3].rsplit(config['ticketStartString'], 1)[-1]
        download(attachment[3], singleID, filename)
    elif any("https://drive.google.com/file/d/" in s for s in attachments):
        print("Downloading " + singleID + " from google drive")
        matching = [s for s in attachments if "https://drive.google.com/file/d/" in s]
        attachment = str(str(matching[0]).split("'"))
        start = "https://drive.google.com/file/d/"
        end = "/view?usp=sharing"
        downloadGoogleDrive(attachment[attachment.find(start)+len(start):attachment.rfind(end)], singleID)
    else:
        commentStatus(
            singleID,
            config['messages']['noFile']
        )
        changeStatus(singleID, "11")
        changeStatus(singleID, "111")

### things to do when a print is good to go ###
def printIsGoodToGo(singleIssue, singleID, classKey):
    attachments = str(singleIssue).split(',')
    if any(config['base_url'] + "/secure/attachment" in s for s in attachments):
        print("Downloading " + singleID)
        matching = [s for s in attachments if config['base_url'] + "/secure/attachment" in s]
        attachment = str(matching[0]).split("'")
        filename = attachment[3].rsplit('EHSL3DPR-', 1)[-1]
        download(attachment[3], singleID, filename)
        if validateClassKey(classKey, 5, 1) == "Valid key":
            print("Skip payment, they had a valid class key")
        else:
            print("payment")
    elif any("https://drive.google.com/file/d/" in s for s in attachments):
        print("Downloading " + singleID + " from google drive")
        matching = [s for s in attachments if "https://drive.google.com/file/d/" in s]
        attachment = str(str(matching[0]).split("'"))
        start = "https://drive.google.com/file/d/"
        end = "/view?usp=sharing"
        downloadGoogleDrive(attachment[attachment.find(start)+len(start):attachment.rfind(end)], singleID)
        if validateClassKey(classKey, 5, 1) == "Valid key":
            print("Skip payment, they had a valid class key")
        else:
            print("payment")
    else:
        commentStatus(
            singleID,
            config['messages']['noFile']
        )
        changeStatus(singleID, "11")
        changeStatus(singleID, "111")
### class keys are used when you want to do bulk class orders ###
def validateClassKey(key, cost, count):
    for singlekey in keys["CLASSKEYS"]:
        if keys["CLASSKEYS"][singlekey]["key"] == key:
            if keys["CLASSKEYS"][singlekey]["active"] == True:
                if count > 0:
                    keys['CLASSKEYS'][singlekey]['printCount'] = keys['CLASSKEYS'][singlekey]['printCount'] + count
                with open("keys.yml", 'w') as f:
                    yaml.safe_dump(keys, f, default_flow_style=False)
                if cost > 0:
                    keys['CLASSKEYS'][singlekey]['classCost'] = keys['CLASSKEYS'][singlekey]['classCost'] + cost
                with open("keys.yml", 'w') as f:
                    yaml.safe_dump(keys, f, default_flow_style=False)
                return "Valid key"
    return "Bad key"
### change the status of the jira ticket, you need to have the status IDs for your setup and change them throughout the project ###
def changeStatus(singleID, id):
    """
    Here are the status that we have for our system right now at the University of Utah

    Start Progress: 11 (From Open to In Progress)
    Ready for review: 21 (From In Progress to UNDER REVIEW)
    Stop Progress: 111 (From In Progress to CANCELLED)
    Approve : 31 (From Under Review to APPROVED)
    Reject: 131 (From Under Review to REJECTED)
    Done: 41  (From APPROVED to DONE)
    Reopen: 121  (From Cancelled to OPEN)
    Start progress : 141  (From REJECTEDto IN PROGRESS)
    """
    simple_singleID = singleID.rsplit('__', 1)[-1]
    url = config['base_url'] + "/rest/api/2/issue/" + simple_singleID + "/transitions"
    headers = {
       "Content-type": "application/json",
       "Accept" : "application/json"
    }
    data = {
        "update": {
            "comment": [{
                "add": {
                    "body": "The ticket is resolved"
                }
            }]
        },
        "transition": {
            "id":id
        }
    }
    
    response = requests.request(
        "POST",
        url,
        headers=headers,
        json = data,
        auth=auth
    )
### a simple function call to be used whenever you want to comment on a ticket ###
def commentStatus(singleID, comment):
    simple_singleID = singleID.rsplit('__', 1)[-1]
    url = config['base_url'] + "/rest/api/2/issue/" + simple_singleID + "/comment"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    payload = {
        "body": comment
    }

    response = requests.request(
       "POST",
       url,
       json=payload,
       headers=headers,
       auth=auth
    )

### When someone asks what their print status if we reply ###
def askedForStatus():
    os.system('cls' if os.name == 'nt' else 'clear')
    print("Checking for status updates...")
    url = config['base_url'] + "/rest/api/2/" + config['printing_url']
    headers = {
       "Accept": "application/json"
    }
    
    response = requests.request(
       "GET",
       url,
       headers=headers,
       auth=auth
    )

    # parse all open projects:
    openissues = json.loads(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
    for issue in openissues['issues']:
        url = issue['self']
        headers = {
           "Accept": "application/json"
        }
        
        response = requests.request(
           "GET",
           url,
           headers=headers,
           auth=auth
        )

        ticketID = url[url.find("issue/")+len("issue/"):url.rfind("")]
        singleIssue = json.loads(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
        comment = singleIssue['fields']['comment']['comments'][-1]['body']
        for trigger in config['requestUpdate']:
            if str(comment).find(trigger) != -1:
                print(comment)
                directory = r'jiradownloads'
                for filename in sorted(os.listdir(directory)):
                    if filename.find(ticketID):
                        commentStatus(ticketID, config["messages"]["statusInQueue"])
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
                        status = json.loads(json.dumps(json.loads(response.text), sort_keys=True, indent=4, separators=(",", ": ")))
                        if str(status['job']['file']['name']).find(ticketID) != -1:
                            base = config['messages']['statusUpdate'] + "\n"
                            completion = "Completion: " + str(round(status['progress']['completion'], 2)) + "%" + "\n"
                            eta = "Print time left: " + str(time.strftime('%H:%M:%S', time.gmtime(status['progress']['printTimeLeft']))) + "\n"
                            material = "Cost: $" + str(round(status['job']['filament']['tool0']['volume'] * printers['farm_printers'][printer]['materialDensity'] * config['payment']['costPerGram'],2)) + "\n"
                            end =  config['messages']['statusUpdateEnd']
                            
                            printerStatusUpdate = base + completion + eta + material + end
                            commentStatus(ticketID, printerStatusUpdate)
                            print(printerStatusUpdate)
                    except requests.exceptions.RequestException as e:  # This is the correct syntax
                        print("Skipping " + printer + " due to network error.")
                return
