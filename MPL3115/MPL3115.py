#!/usr/bin/env python3

# 2019-04-07 MPL3115.py

import time
#import atexit
import json
import os
import sys
import datetime
import smbus
from pytz import timezone
from tzlocal import get_localzone

def set_procname(newname):
  from ctypes import cdll, byref, create_string_buffer
  libc = cdll.LoadLibrary('libc.so.6')    #Loading a 3rd party library C
  buff = create_string_buffer(len(newname)+1) #Note: One larger than the name (man prctl says that)
  buff.value = newname                 #Null terminated string as it should be
  libc.prctl(15, byref(buff), 0, 0, 0) #Refer to "#define" of "/usr/include/linux/prctl.h" for the misterious value 16 & arg[3..5] are zero as the man page says.

set_procname(b"FANCTRL")


# Delay between calls (200ms)
SLEEP = 1 / 5

######################
# Various registers  #
######################

# Device Address
MPL3115A2_ADDRESS= 0x60

# Device Identifier (int 196)
MPL3115A2_WHOAMI = 0x0C


MPL3115A2_CTRL_REG1 = 0x26
MPL3115A2_CTRL_REG1_SBYB = 0x01
MPL3115A2_CTRL_REG1_OS128 = 0x38
MPL3115A2_CTRL_REG1_ALT = 0x80
MPL3115A2_CTRL_REG1_BAR = 0x00

MPL3115A2_PT_DATA_CFG = 0x13
MPL3115A2_PT_DATA_CFG_TDEFE = 0x01
MPL3115A2_PT_DATA_CFG_PDEFE = 0x02
MPL3115A2_PT_DATA_CFG_DREM = 0x04

MPL3115A2_REGISTER_STATUS_TDR = 0x02
MPL3115A2_REGISTER_PRESSURE_MSB = 0x01
MPL3115A2_REGISTER_TEMP_MSB = 0x04


class sensor:

   def __init__(self, pi = None, busid = 1, LED=None, power=None, filename=None):

      self.pi = pi
      self.LED = LED
      self.power = power
      self.f = None
      
      if filename is not None:
         self.f = open(filename,"a+")

      if filename is not None:
         self.ftemp = open(filename+"-temperature","a+")

      if filename is not None:
         self.fpres = open(filename+"-pressure","a+")

      if power is not None:
         pi.write(power, 1)  # Switch sensor on.
         time.sleep(2)

      self.powered = True

      self.pres = -999
      self.temp = -999
      self.count = 0

      # Get I2C bus
      self.bus = smbus.SMBus(busid)

      # Check device identifier (also check that the wire are correctly plugged)
      whoami = self.bus.read_i2c_block_data(MPL3115A2_ADDRESS, MPL3115A2_WHOAMI, 1)
      if (whoami[0] != 196):
         exit("Not Adafruit_MPL3115A2")

      # Initialize device capabilities 
      self.bus.write_byte_data(MPL3115A2_ADDRESS, MPL3115A2_CTRL_REG1, MPL3115A2_CTRL_REG1_SBYB | MPL3115A2_CTRL_REG1_OS128)

      # Delay
      time.sleep(SLEEP)

      # Initialize device capabilities 
      self.bus.write_byte_data(MPL3115A2_ADDRESS, MPL3115A2_PT_DATA_CFG, MPL3115A2_PT_DATA_CFG_TDEFE | MPL3115A2_PT_DATA_CFG_PDEFE | MPL3115A2_PT_DATA_CFG_DREM)

      # Delay
      time.sleep(SLEEP)

   def temperature(self):
      """Return current temperature."""
      return self.temp

   def pressure(self):
      """Return current relative humidity."""
      return self.pres

   def writefile(self):
      try: 
         data = { 
            "count": self.count, 
            "time": datetime.datetime.now().isoformat(),
            "pressure": self.pressure(),
            "temperature": self.temperature()
         }

         self.f.seek(0)
         self.f.truncate()
         json.dump(data, self.f, indent=4)
         self.f.flush()
         
         self.ftemp.seek(0)
         self.ftemp.truncate()
         self.ftemp.write(str(int(self.temperature()*1000)))
         self.ftemp.flush()
         
         self.fpres.seek(0)
         self.fpres.truncate()
         self.fpres.write(str(int(self.pressure()*1000)))
         self.fpres.flush()
         
      except Exception as e:
         exc_type, exc_obj, exc_tb = sys.exc_info()
         fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
         print("Exception: {0}".format(e))
         print(exc_type, fname, exc_tb.tb_lineno)
         sys.stdout.flush()
         pass


   def trigger(self):
      """Trigger a new relative humidity and temperature reading."""
      if self.powered:
         if self.LED is not None:
            self.pi.write(self.LED, 1)

         # Read 2 bytes from MPL3115A2_ADDRESS at MPL3115A2_REGISTER_TEMP_MSB (temperature sensor)
         data = self.bus.read_i2c_block_data(MPL3115A2_ADDRESS, MPL3115A2_REGISTER_TEMP_MSB, 2)
         #print data 		# Debug output
         temp = ((data[0] * 256) + (data[1] & 0xF0)) / 16
         self.temp = temp / 16.0
         # Reads 4 bytes from MPL3115A2_ADDRESS at MPL3115A2_CTRL_REG1_BAR
         data = self.bus.read_i2c_block_data(MPL3115A2_ADDRESS, MPL3115A2_CTRL_REG1_BAR, 4)

         # Convert the data to 20-bits
         pres = ((data[1] * 65536) + (data[2] * 256) + (data[3] & 0xF0)) / 16
         self.pres = (pres / 4.0) / 1000.0
         
         self.count += 1
         
         self.writefile()

   def cancel(self):
      """Cancel the DHT22 sensor."""

      if self.f is not None:
         self.f.close()
         
      if self.ftemp is not None:
         self.ftemp.close()
      if self.fpres is not None:
         self.fpres.close()

if __name__ == "__main__":

   import time
   import MPL3115
   
   print('START')

   try:

      INTERVAL = 1

      s = MPL3115.sensor(filename="/dev/shm/MPL3115")

      while True:

         s.trigger()
         
         time.sleep(INTERVAL)

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

