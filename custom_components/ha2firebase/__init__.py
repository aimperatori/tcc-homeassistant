# General
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any
import re

from os.path import exists
from datetime import datetime
from datetime import timedelta

import sqlite3
from sqlite3 import Error

# Firebase
import firebase_admin
from firebase_admin import db
from firebase_admin import storage
from firebase_admin import credentials

# Home Assistant

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import event as event_helper, state as state_helper
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_values import EntityValues
from homeassistant.helpers.entityfilter import (
    INCLUDE_EXCLUDE_BASE_FILTER_SCHEMA,
    convert_include_exclude_filter,
)
from homeassistant.helpers.typing import ConfigType


DOMAIN = "ha2firebase"


def getCozinhaTemperatura(conn):

    sql = """
            SELECT state, created, entity_id
            FROM "states"
            WHERE entity_id = "sensor.sensor_cozinha_temperature"
            AND created BETWEEN DATETIME(datetime(), '-30 second') AND DATETIME(datetime(), '+30 second')
            ORDER BY created DESC
    """

    now = datetime.now()
    date  = now.strftime('%Y-%m-%d')

    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()

    ref = db.reference("collectedData/temperatura/"+ date)

    for row in rows:
        json = {
            'value': row[0],
            'created': re.findall("[0-2][0-4]:[0-5][0-9]:[0-5][0-9]", row[1])[0]
        }
        ref.push(json)


def getCozinhaUmidade(conn):

    sql = """
            SELECT state, created, entity_id
            FROM "states"
            WHERE entity_id = "sensor.sensor_cozinha_umidade"
            AND created BETWEEN DATETIME(datetime(), '-30 second') AND DATETIME(datetime(), '+30 second')
            ORDER BY created DESC
    """

    now = datetime.now()
    date  = now.strftime('%Y-%m-%d')

    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()

    ref = db.reference("collectedData/umidade/"+ date)

    for row in rows:
        json = {
            'value': row[0],
            'created': re.findall("[0-2][0-4]:[0-5][0-9]:[0-5][0-9]", row[1])[0]
        }
        ref.push(json)


def getCozinhaGasFumaca(conn):

    sql = """
            SELECT state, created, entity_id
            FROM "states"
            WHERE entity_id = "sensor.sensor_cozinha_gasfumaca"
            AND created BETWEEN DATETIME(datetime(), '-5 minutes') AND DATETIME()
            AND CAST(state AS INTEGER) >= "1000"
            ORDER BY created DESC
    """

    now = datetime.now()
    date  = now.strftime('%Y-%m-%d')

    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()

    ref = db.reference("collectedData/gas_fumaca/"+ date)

    for row in rows:
        json = {
            'value': row[0],
            'created': re.findall("[0-2][0-4]:[0-5][0-9]:[0-5][0-9]", row[1])[0]
        }
        ref.push(json)


def getMovimento(conn):

    sql = """
            SELECT state, created, entity_id, state_Id, old_state_id
            FROM "states"
            WHERE entity_id = "sensor.sensor_entrada_movimento"
            AND created BETWEEN DATETIME(datetime(), '-5 minutes') AND DATETIME()
            AND state = 'on'
            ORDER BY created DESC
    """

    now = datetime.now()
    date  = now.strftime('%Y-%m-%d')

    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()

    ref = db.reference("collectedData/movimento/"+ date)

    for row in rows:
        json = {
            'value': row[0],
            'created': re.findall("[0-2][0-4]:[0-5][0-9]:[0-5][0-9]", row[1])[0]
        }
        ref.push(json)


### CAMERA ###

def incTime(_curTime):
    hour, min, sec = _curTime.split('-')

    if sec == '59':
        sec = '00'
        min = str(int(min) + 1)
    else:
        sec = str(int(sec) + 1)

    if min == '60':
        min = '00'
        hour = str(int(hour) + 1)

    return hour.zfill(2) +'-'+ min.zfill(2) +'-'+ sec.zfill(2)

def formatFilename(date, time):
    return '/share/motioneye/Camera2/'+ date + '/' + time + '.jpg'

def formatNameStorage(date, time):
    return 'image/'+ date + '/' + time +'.jpg'

def sendCameraImages():

    bucket = storage.bucket()

    now = datetime.now()
    date  = now.strftime('%Y-%m-%d')
    _from = str((now + timedelta(minutes=-5)).strftime('%H-%M-%S'))
    _to   = str(now.strftime('%H-%M-%S'))

    newTime = _from

    fileList = []
    flag = False

    while newTime != _to:

        filename = formatFilename(date, newTime)

        if exists(filename):
            flag = True
            blob = bucket.blob(formatNameStorage(date, newTime))

            blob.upload_from_filename(filename)
            blob.make_public()

            fileList.append(blob.public_url)
            # print("your file url", blob.public_url)
            
        newTime = incTime(newTime)

    if flag:
        json = {
            'from': _from.replace('-', ':'),
            'to': _to.replace('-', ':'),
            'files': fileList
        }

        ref = db.reference("camera/"+ date)

        ref.push(json)
        # print(json)


### SETUP ###
def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    
    cred = credentials.Certificate("/config/custom_components/ha2firebase/homeassistantoff-firebase-adminsdk-hv04o-19145ba217.json")
    firebase_admin.initialize_app(cred, {'storageBucket': 'homeassistantoff.appspot.com', 'databaseURL': 'https://homeassistantoff-default-rtdb.firebaseio.com/'})
    
    def handle_sendCollectedData(call):

        conn = sqlite3.connect("/config/home-assistant_v2.db")

        getCozinhaTemperatura(conn)
        getCozinhaUmidade(conn)
        getCozinhaGasFumaca(conn)
        getMovimento(conn)

    def handle_sendDetectionImages(call):
        sendCameraImages()
    

    hass.services.register(DOMAIN, "sendCollectedData", handle_sendCollectedData)
    hass.services.register(DOMAIN, "sendDetectionImages", handle_sendDetectionImages)
    
    return True
