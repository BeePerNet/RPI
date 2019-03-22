#!/usr/bin/env python3

# read_RPM.py
# 2016-01-20
# Public Domain

import time
import pigpio # http://abyz.co.uk/rpi/pigpio/python.html
import numpy
import traceback

class reader:

   SAMPLES = 10
   WATCHDOG = 400
   """
   A class to read speedometer pulses and calculate the RPM.
   """
   def __init__(self, rpmgpio, pwmgpio):
      self.pi = pigpio.pi()
      self.rpmgpio = rpmgpio
      self.pwmgpio = pwmgpio

      tick = self.pi.get_current_tick()

      self._rpm = None
      self._duty = 0

      self._pwm_on = bool(self.pi.read(self.pwmgpio))
      self._lastpwm_on = 0
      if self._pwm_on:
         self._duty = 100
         self._lastpwm_on = tick
         
      self._lastpwm = tick
      self._laston = None
      self._lastgood = None
      self._lastgoods = []
      self._lastgoodsduty = []
      self._lastevent = 0
      self._lastgoodevent = 0
      self._lastCalculate = 0
      self._lastCalculateduty = 0
      
      self.pi.set_mode(rpmgpio, pigpio.INPUT)

      self._pw = self.pi.callback(pwmgpio, pigpio.EITHER_EDGE, self._pwm)
      self._cb = self.pi.callback(rpmgpio, pigpio.EITHER_EDGE, self._sig)
      self.pi.set_watchdog(rpmgpio, self.WATCHDOG)
      self.pi.set_watchdog(pwmgpio, self.WATCHDOG)
      

   def _pwm(self, gpio, level, tick):
      try:
         self._pwm_on = bool(self.pi.read(self.pwmgpio))
         if level == 2:
            if tick - self._lastpwm > self.WATCHDOG * 1000 / 2:
               if self._pwm_on:
                  self._lastgoodsduty.append(100)
               else:
                  self._lastgoodsduty.append(0)
         else:
            if not self._pwm_on:
               self._lastgoodsduty.append((tick - self._lastpwm) / (tick - self._lastpwm_on) * 100)
               self._lastpwm_on = tick
            self._lastpwm = tick
            self._laston = None
            self._lastgood = None
         if tick - self._lastCalculateduty > self.WATCHDOG * 1000 and len(self._lastgoodsduty) > 0:
            self._calculateduty() 
            self._lastCalculateduty = tick
      except:
         print("Unexpected error:", sys.exc_info()[0])
         traceback.print_exc()
         pass
            
   def _sig(self, gpio, level, tick):
      try:
         if self._duty == 0 and tick - self._lastpwm > self.WATCHDOG * 1000:
            self._rpm = None
         elif self._duty > 0 and self._duty < 100 and tick - self._lastevent > self.WATCHDOG * 1000:
            self._rpm = -1
         elif tick - self._lastgoodevent > self.WATCHDOG * 1000:
            self._rpm = 0
         if level == 1:
            self._laston = tick
            self._lastevent = tick
         elif level == 0 and self._laston is not None:
            diff = tick - self._laston
            if diff > 100 and diff < 3000:
               self._lastgoodevent = tick
               if self._lastgood is not None:
                  self._lastgoods.append(self._laston - self._lastgood)
                  self._lastgood = self._laston
                  self._laston = None                     
               else:
                  self._lastgood = self._laston

            if tick - self._lastCalculate > self.WATCHDOG * 1000 and len(self._lastgoods) > self.SAMPLES:
               self._calculate()
               self._lastCalculate = tick
                     
      except:
         print("Unexpected error:", sys.exc_info()[0])
         traceback.print_exc()
         pass
         
   def _calculateduty(self):
      elements = self._lastgoodsduty.copy()
      self._lastgoodsduty = []
      #print("copy:{}".format(len(copy)))
      #print("elements:{}".format(elements))

      self._duty = numpy.mean(elements)
               
   def _calculate(self):
      #, dtype=numpy.float64, , dtype=numpy.int32
      elements = self._lastgoods.copy()
      self._lastgoods = []
      #print("copy:{}".format(len(copy)))
      #print("elements:{}".format(elements))

      mean = numpy.mean(elements)
      #sd = numpy.std(elements, ddof=1)
      
      #print("count: {:10}, mean:{:10}, sd {:10}".format(len(elements), mean, sd))

      #final_list = [x for x in elements if (x > 0) and (x < mean + sd) and (x > mean - sd)]        
      #print("final_list:{}".format(final_list))
      #self._rpm = 1 / (numpy.mean(final_list) / 1000000) / 4 * 60
      self._rpm = 1 / (mean / 1000000) / 4 * 60
         
         
   def get_RPM(self):
      return self._rpm
   RPM = property(get_RPM)
   
   def cancel(self):
      """
      Cancels the reader and releases resources.
      """
      self.pi.set_watchdog(self.rpmgpio, 0) # cancel watchdog
      self.pi.set_watchdog(self.pwmgpio, 0) # cancel watchdog
      self._cb.cancel()
      self._pw.cancel()
      
   def __str__(self):
      if self._rpm is None:
         return "Duty: {:3.3f}%: Fan stopped: 0 RPM".format(self._duty)
      elif self._rpm < 0:
         return "Duty: {:3.3f}%: Fan sensor error".format(self._duty)
      elif self._rpm == 0:
         return "Duty: {:3.3f}%: Fan critical: 0 RPM".format(self._duty)
      else:
         return "Duty: {:3.3f}%: {:6.2f} RPM".format(self._duty, self._rpm)
      

if __name__ == "__main__":

   import time
   import read_RPM_pwm

   PWS_GPIO = 9
   RPM_GPIO = 11
   SAMPLE_TIME = 2.0

   p = read_RPM_pwm.reader(RPM_GPIO, PWS_GPIO)

   try:
      while 1:

         time.sleep(SAMPLE_TIME)

         print(p)
         
   finally:

      p.cancel()

      pi.stop()

