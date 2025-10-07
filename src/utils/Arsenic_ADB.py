# MITE ADB Functions

# from asyncio.windows_utils import Popen
from subprocess import run, PIPE, CREATE_NO_WINDOW
from subprocess import Popen
import sys
import os
import time
import streamlit as st
from android_backup import AndroidBackup, CompressionType, EncryptionType

################    GET PLATFORM    #################


if sys.platform == "darwin":                                   
    adb = "./src/utils/adb"
if sys.platform == "win32" or sys.platform == "win64":
    adb = "./src/utils/adb.exe"



def file_search_jpg():
    
    #   This runs the adb command to find jpg using 'find' and then greps out all permission denied errors
    pics = run([adb, 'shell', 'find', '-name', '*.jpg', '2>&1 | grep -v "Permission denied"'], stdout=PIPE, stderr=PIPE, universal_newlines=True, creationflags=CREATE_NO_WINDOW)
    # pics = Popen([adb, 'shell', 'find', '-name', '*.jpg', '2>&1 | grep -v "Permission denied"'], stdout=PIPE, stderr=PIPE, universal_newlines=True)
    
    lines = (pics.stdout)
    # lines = lines.split('\n')
    
    # for a in lines:
    #     if a.endswith('.jpg'):
def get_storage_info():
    filesysteminfo = run([adb, "shell", "df"], stdout=PIPE, stderr=PIPE, universal_newlines=True, creationflags=CREATE_NO_WINDOW)
    fsdata = (filesysteminfo.stdout)
    fsdata = fsdata.split('\n')
    for thing in fsdata:
        if "storage" in thing:
            if "emulated" in thing:
                Internal_Store = thing.split()
            else:
                External_Store = thing.split()
    try:            
        internal_store_used = str(round(int(Internal_Store[2])/1024/1024, 2)) + " GB"           #   all reported in GB
        internal_store_total =  str(round(int(Internal_Store[1])/1024/1024, 2)) + " GB"
        external_store_used = str(round(int(External_Store[2])/1024/1024, 2)) + " GB"
        external_store_total = str(round(int(External_Store[1])/1024/1024, 2)) + " GB"
    except UnboundLocalError:
        external_store_used = "0 GB" 
        external_store_total = "0 GB"
    return [internal_store_used, internal_store_total, external_store_used, external_store_total]
    

def ADB_file_search():
    search_files = []
    #   This runs the adb command to find jpg using 'find' and then greps out all permission denied errors - GETS EXTERNAL STORAGE LIKE SD
    try:
        master = run([adb, 'shell', 'find 2>&1 | grep -v "Permission denied"'], stdout=PIPE, stderr=PIPE, universal_newlines=True,encoding='utf8', creationflags=CREATE_NO_WINDOW)
        lines = (master.stdout)
        lines = lines.split('\n')
        primary_files = lines
        search_files.extend(primary_files)
        storage = run([adb, 'shell', 'find storage/emulated/0 2>&1 | grep -v "Permission denied"'], stdout=PIPE, stderr=PIPE, universal_newlines=True, creationflags=CREATE_NO_WINDOW)
        store = (storage.stdout)
        store = store.split('\n')
        search_files.extend(store)
        
    except IndexError:
        master = run([adb, 'shell', 'find', '2>&1 | grep -v "Permission denied"'],  stdout=PIPE, stderr=PIPE, universal_newlines=True, creationflags=CREATE_NO_WINDOW)
        lines = (master.stdout)
        lines = lines.split('\n')
        primary_files = lines
        search_files.extend(primary_files)
        storage = run([adb, 'shell', 'find', 'storage/emulated/0 2>&1 | grep -v "Permission denied"'], stdout=PIPE, stderr=PIPE, universal_newlines=True, creationflags=CREATE_NO_WINDOW)
        store = (storage.stdout)
        store = store.split('\n')
        search_files.extend(store)        
        
        (print('alternative master file collection used'))
    # search_files = sorted(search_files)
    return search_files
    

def application_info():     #   Get's 3rd party apps in list form
    # apps = run([adb, 'shell', 'dumpsys package packages -3'], stdout=PIPE, stderr=PIPE, universal_newlines=True)
    apps = run([adb, 'shell', "pm list packages -u -3"], stdout=PIPE, stderr=PIPE, universal_newlines=True, creationflags=CREATE_NO_WINDOW)
    # apps = run([adb, "shell", "pm dumpsys packages package"], stdout=PIPE, stderr=PIPE, universal_newlines=True)
    lines = (apps.stdout)
    lines = lines.replace('package:', '')
    lines = lines.split('\n')
    
    lines = sorted(lines)
    app_info = lines

    return app_info

def secure_folder_apps(app_list):       # returns list of 3rd party apps in secure folder
    # apps = run([adb, 'shell', "pm list packages -3 --user 150"], stdout=PIPE, stderr=PIPE, universal_newlines=True)     #Security error on new android
    # # apps = run([adb, "shell", "pm dumpsys packages package"], stdout=PIPE, stderr=PIPE, universal_newlines=True)
    # lines = (apps.stdout)
    # lines = lines.replace('package:', '')
    # lines = lines.split('\n')
    
    # lines = sorted(lines)
    # secure_apps = lines

    secure_apps = []
    for thing in app_list:
        thing = thing.replace('package:','')
        hidden_app = run([adb, 'shell', 'dumpsys package ' + thing], stdout=PIPE, stderr=PIPE, universal_newlines=True, creationflags=CREATE_NO_WINDOW)
        lines = hidden_app.stdout
        lines = lines.split('\n')
        for rec in lines:
            if rec.startswith("    User 150:"):
                # print(thing)
                if 'installed=true' in rec:
                    if "samsung" not in thing:
                        if len(thing) > 1:
                            secure_apps.append(thing)
    secure_apps = sorted(secure_apps)
    return secure_apps

def ADB_get_users():          #   gets the users from device and looks for user '150' indicating a secure folder is present
    user_s = run([adb, 'shell', 'pm list users'], stdout=PIPE, stderr=PIPE, universal_newlines=True, creationflags=CREATE_NO_WINDOW)
    lines = (user_s.stdout)
    lines = lines.split('\n')
    users = []
    for line in lines:
        if 'UserInfo' in line:
            users.append(line)
    return users

def make_backup(destination_folder, caseNumber, devicename):
    os.makedirs(destination_folder + "/Mite_Backup")
    back_folder = destination_folder + "/Mite_Backup"
    # backingup = MITE_ADB.ADB_backup(back_folder, casenum, dev_Name)
    backup_file = back_folder + "/" + caseNumber + "_" + devicename + "_backup.ab"       #   name of backup
    # backup_folder = back_folder + "/" + casenum + "_" + dev_Name                    #   output directory for unpacked backup
    backed = Popen([adb, "backup", "-apk", "-all", "-shared", "-f", backup_file], creationflags=CREATE_NO_WINDOW)
    time.sleep(2)
    touchy = Popen([adb, "shell", "input", "tap 220 820"], creationflags=CREATE_NO_WINDOW)
    time.sleep(2)
    password = Popen([adb, "shell", "input", "text 'MITE'"], creationflags=CREATE_NO_WINDOW)
    time.sleep(2)
    touch_2_backup = Popen([adb, "shell", "input", "tap 820 1440"], creationflags=CREATE_NO_WINDOW)     # keyboard on screen touch location (this is empty space when no keyboard present. use it first.)
    touch_3_backup = Popen([adb, "shell", "input", "tap 570 1415"], creationflags=CREATE_NO_WINDOW)     # keyboard not on screen touch location
    Backup_status = st.empty()     
    with Backup_status:
        st.info("Backup is starting")                   
    backsize = os.path.getsize(backup_file)
    time.sleep(5)
    backsize2 = os.path.getsize(backup_file)
    
    while backsize2 != backsize:
        backsize = os.path.getsize(backup_file)
        
        time.sleep(2)
        backsize2 = os.path.getsize(backup_file)
        backgigs = backsize2/1024/1024          # Convert from bytes to GB
        backgigs = format(backgigs,'.2f')       # limits to two decimal places
        backup_size_update = (str(backgigs) + " MB")
        with Backup_status:
            st.info("ADB Backup in Process - Size is: " + backup_size_update)

    return backup_file

def unpack_backup(ABFile,backupFolder):
    try:
        with AndroidBackup(ABFile) as ab:
            print("unpacking backup")
            try:
                ab.unpack(password="MITE", target_dir=backupFolder)
            except Exception:
                ab.unpack(password="", target_dir=backupFolder)
    except AssertionError: 
        print("There was an error unpacking the backup. Use an alternative tool to review the collected data.")

def service_call_for_IDs():         #   Performs a service call to get phonenumber, imei, imsi and iccids
    imei_list = [1,4]               #   These list are the service call row number being queried
    phonenum_list = [8,16,17]          #   phone and sometimes imsi
    iccid_list = [13, 15]
    
    phonenums = []                  #   These lists hold cleaned up results
    iccids = []
    imei = []
    imsi = []

    for it in imei_list:
        phonestuff = run([adb, "shell", "service", "call", "iphonesubinfo " + str(it), " | cut -c 52-66 | tr -d '.[:space:]+'"], stdout=PIPE, stderr=PIPE, universal_newlines=True, creationflags=CREATE_NO_WINDOW)
        phoneids = (phonestuff.stdout)
        phoneids = phoneids.strip("')")
        imei.append(phoneids)

    for it in iccid_list:
        phonestuff = run([adb, "shell", "service", "call", "iphonesubinfo " + str(it), " | cut -c 52-66 | tr -d '.[:space:]+'"], stdout=PIPE, stderr=PIPE, universal_newlines=True, creationflags=CREATE_NO_WINDOW)
        phoneids = (phonestuff.stdout)
        phoneids = phoneids.strip("')")
        if len(phoneids) >= 19 and len(phoneids) < 21:
            iccids.append(phoneids)

    for it in phonenum_list:
        phonestuff = run([adb, "shell", "service", "call", "iphonesubinfo " + str(it), " | cut -c 52-66 | tr -d '.[:space:]+'"], stdout=PIPE, stderr=PIPE, universal_newlines=True, creationflags=CREATE_NO_WINDOW)
        phoneids = (phonestuff.stdout)
        phoneids = phoneids.strip("')")
        if len(phoneids) >= 8 and len(phoneids) < 14:
            phonenums.append(phoneids)
        if len(phoneids) == 15:
            imsi.append(phoneids)
    
    iccids = list(set(iccids))          #remove duplicats from lists
    phonenums = list(set(phonenums))
    imei = list(set(imei))

    return phonenums, imei, imsi, iccids