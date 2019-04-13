#!/usr/bin/env python3

# 2019-04-07 FANCTRL.py

import time
#import atexit
import pigpio
import json
import os
import sys
import datetime
import RPi.GPIO as GPIO
import numpy
import traceback
from pytz import timezone
from tzlocal import get_localzone

def set_procname(newname):
  from ctypes import cdll, byref, create_string_buffer
  libc = cdll.LoadLibrary('libc.so.6')    #Loading a 3rd party library C
  buff = create_string_buffer(len(newname)+1) #Note: One larger than the name (man prctl says that)
  buff.value = newname                 #Null terminated string as it should be
  libc.prctl(15, byref(buff), 0, 0, 0) #Refer to "#define" of "/usr/include/linux/prctl.h" for the misterious value 16 & arg[3..5] are zero as the man page says.

set_procname(b"FANCTRL")


PWM_FREQ = 10           # [Hz] Change this value if fan has strange behavior

SAMPLES = 10
WATCHDOG = 400

# Configurable temperature and fan speed steps
FAN_MIN = 50            # [%] Fan minimum speed.
tempSteps = [30, 45, 50, 60]    # [°C]
speedSteps = [30, 50, 75, 100]   # [%]
# Fan speed will change only of the difference of temperature is higher than hysteresis
hyst = 1

# We must set a speed value for each temperature step
if(len(speedSteps) != len(tempSteps)):
    print("Numbers of temp steps and speed steps are different")
    exit(0)    


class fanctrl:

   def __init__(self, pi, pwmgpio, rpmgpio, filename=None):

      self.pi = pi
      self.pwmgpio = pwmgpio
      self.rpmgpio = rpmgpio
      self.f = None
      self.frpm = None
      
      if filename is not None:
         self.f = open(filename,"a+")
         self.frpm = open(filename+"-rpm","a+")

      # Setup GPIO pin
      GPIO.setmode(GPIO.BCM)
      GPIO.setup(self.pwmgpio, GPIO.OUT, initial=GPIO.LOW)
      self.fan=GPIO.PWM(self.pwmgpio,PWM_FREQ)
      self.fan.start(0);
      
      
      self._rpm = None
      self._duty = 0

      self._pwm_on = bool(self.pi.read(self.pwmgpio))
      tick = self.pi.get_current_tick()
      self._lastpwm_on = 0
      if self._pwm_on:
         self._duty = 100
         self._lastpwm_on = tick
         
      self._lastpwm = tick
      self._lastgoods = []
      self._lastevent = None
      self._lastgoodevent = 0
      self._lastCalculate = 0
      
      self.pi.set_mode(rpmgpio, pigpio.INPUT)
      self.pi.set_pull_up_down(rpmgpio, pigpio.PUD_OFF)

      self._pw = self.pi.callback(pwmgpio, pigpio.EITHER_EDGE, self._pwm)
      self._cb = self.pi.callback(rpmgpio, pigpio.EITHER_EDGE, self._sig)
      self.pi.set_watchdog(rpmgpio, WATCHDOG)
      self.pi.set_watchdog(pwmgpio, WATCHDOG)
      
      self.temperature = 0     



   def _pwm(self, gpio, level, tick):
      try:
         self._pwm_on = bool(self.pi.read(self.pwmgpio))
         if level == 2:
            if tick - self._lastpwm > WATCHDOG * 1000:
               if self._pwm_on:
                  self._duty = 100
               else:
                  self._duty = 0
         else:
            if not self._pwm_on:
               self._duty = (tick - self._lastpwm) / (tick - self._lastpwm_on) * 100
               self._lastpwm_on = tick
            self._lastpwm = tick
            self._lastevent = None
      except:
         print("Unexpected error:", sys.exc_info()[0])
         traceback.print_exc()
         sys.stdout.flush()
         pass
            
   def _sig(self, gpio, level, tick):
      try:
         if level == 2:
            self._lastgoods = []
            if bool(self.pi.read(self.rpmgpio)):
               if self._duty > 0:
                  self._rpm = 0
               else:
                  self._rpm = None
            else:
               self._rpm = -1
         else:
            if self._pwm_on and bool(self.pi.read(self.pwmgpio)) and abs(tick - self._lastpwm) > 500:
               if self._lastevent is not None:
                  if tick - self._lastevent > 5000:
                     self._lastgoods.append(tick - self._lastevent)
               self._lastevent = tick
            
            if abs(tick - self._lastCalculate) > WATCHDOG * 1000 and len(self._lastgoods) > SAMPLES:
               self._calculate()
               self._lastCalculate = tick
                     
      except:
         print("Unexpected error:", sys.exc_info()[0])
         traceback.print_exc()
         sys.stdout.flush()
         pass
         
   def _calculate(self):
      elements = self._lastgoods.copy()
      self._lastgoods = []
      self._rpm = 1 / (numpy.mean(elements) / 1000000) / 4 * 60


   def run(self):
      i = 0
      cpuTempOld=0
      fanSpeedOld=0
      while True:
         try: 
            tFile = open('/sys/class/thermal/thermal_zone0/temp')
            cpuTemp = float(tFile.read()) / 1000
            tFile.close()

            self.temperature = cpuTemp

            # Calculate desired fan speed
            if abs(cpuTemp-cpuTempOld > hyst):
               
                # Below first value, fan will run at min speed.
                if(cpuTemp < tempSteps[0]):
                   fanSpeed = 0

                # Above last value, fan will run at max speed
                elif(cpuTemp >= tempSteps[len(tempSteps)-1]):
                    fanSpeed = speedSteps[len(tempSteps)-1]

                # If temperature is between 2 steps, fan speed is calculated by linear interpolation
                else:       
                     for i in range(0,len(tempSteps)-1):
                          if((cpuTemp >= tempSteps[i]) and (cpuTemp < tempSteps[i+1])):
                               fanSpeed = round((speedSteps[i+1]-speedSteps[i])\
                                          /(tempSteps[i+1]-tempSteps[i])\
                                          *(cpuTemp-tempSteps[i])\
                                          +speedSteps[i],1)

                if fanSpeed != fanSpeedOld:
                     if fanSpeedOld or fanSpeed >= FAN_MIN or fanSpeed == 0:
                          self.fan.ChangeDutyCycle(fanSpeed)
                          fanSpeedOld = fanSpeed
                          #print("Speed: {0:3}% Temp: {1:4.2f}°C".format(int(fanSpeedOld), cpuTemp))
            
            
            status = "Unknown"
            
            if self._rpm is None:
               status = "Fan stopped" # "Duty: {:3.3f}%: Fan stopped: 0 RPM".format(self._duty)
               fanSpeed = 0
            elif self._rpm < 0:
               status = "Fan sensor error" # "Duty: {:3.3f}%: Fan sensor error".format(self._duty)
            elif self._rpm == 0:
               status = "Fan critical" # "Duty: {:3.3f}%: Fan critical: 0 RPM".format(self._duty)
            else:
               status = "Fan ok" # "Duty: {:3.3f}%: {:6.2f} RPM".format(self._duty, self._rpm)

            data = { 
               "dutyasked": fanSpeed, 
               "time": datetime.datetime.now().isoformat(),
               "duty": self._duty,
               "rpm": self._rpm,
               "temperature": self.temperature,
               "status": status
            }

            self.f.seek(0)
            self.f.truncate()
            json.dump(data, self.f, indent=4)
            self.f.flush()
            
            self.frpm.seek(0)
            self.frpm.truncate()
            if self._rpm is None:
               self.frpm.write("U")
            else:
               self.frpm.write(str(int(self._rpm)))
            self.frpm.flush()

         except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print("Exception: {0}".format(e))
            print(exc_type, fname, exc_tb.tb_lineno)
            sys.stdout.flush()
            pass

         time.sleep(1)

   def cancel(self):
      """Cancel the DHT22 sensor."""

      self.fan.stop()

      self.pi.set_watchdog(self.rpmgpio, 0)
      self.pi.set_watchdog(self.pwmgpio, 0)

      if self.f is not None:
         self.f.close()

      if self.frpm is not None:
         self.frpm.close()
      
         
if __name__ == "__main__":

   import time
   import pigpio
   import FANCTRL
   
   print('START')

   try:

      pi = pigpio.pi()

      s = FANCTRL.fanctrl(pi, 18, 6, filename="/dev/shm/FANCTRL")

      s.run()

   except KeyboardInterrupt:
      print('SIGINT termination')
      pass

   except Exception as e:
      exc_type, exc_obj, exc_tb = sys.exc_info()
      fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
      print("Exception: {0}".format(e))
      print(exc_type, fname, exc_tb.tb_lineno)
      sys.stdout.flush()
      pass
   

   s.cancel()

   pi.stop()

