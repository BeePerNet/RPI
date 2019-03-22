#!/usr/bin/python
# -*- coding: utf-8 -*-

import RPi.GPIO as GPIO
import time
import sys
#import os

FAN_PIN = 9
WAIT_TIME = 1
PWM_FREQ = 10

GPIO.setmode(GPIO.BCM)
GPIO.setup(FAN_PIN, GPIO.OUT, initial=GPIO.LOW)

#GPIO.setup(11, GPIO.IN, pull_up_down=GPIO.PUD_UP)

fan=GPIO.PWM(FAN_PIN,PWM_FREQ)
fan.start(0);
i = 0

hyst = 1
tempSteps = [50, 70]
speedSteps = [0, 100]
cpuTempOld=0

try:
    while True:
        fanSpeed=float(input("Fan Speed: "))
        fan.ChangeDutyCycle(fanSpeed)


except(KeyboardInterrupt):
    print("Fan ctrl interrupted by keyboard")
    GPIO.cleanup()
    sys.exit()
    
