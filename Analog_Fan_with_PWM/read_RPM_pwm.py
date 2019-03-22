#!/usr/bin/env python3

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

      self._pw = self.pi.callback(pwmgpio, pigpio.EITHER_EDGE, self._pwm)
      self._cb = self.pi.callback(rpmgpio, pigpio.EITHER_EDGE, self._sig)
      self.pi.set_watchdog(rpmgpio, self.WATCHDOG)
      self.pi.set_watchdog(pwmgpio, self.WATCHDOG)
      

   def _pwm(self, gpio, level, tick):
      try:
         self._pwm_on = bool(self.pi.read(self.pwmgpio))
         if level == 2:
            if tick - self._lastpwm > self.WATCHDOG * 1000:
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
         pass
            
   def _sig(self, gpio, level, tick):
      try:
         if level == 2:
            if bool(self.pi.read(self.rpmgpio)):
               if self._duty > 0:
                  self._rpm = 0
               else:
                  self._rpm = None
            else:
               self._rpm = -1
         else:
            if self._pwm_on and bool(self.pi.read(self.pwmgpio)) and tick - self._lastpwm > 1000:
               if self._lastevent is not None:
                  if tick - self._lastevent > 5000:
                     self._lastgoods.append(tick - self._lastevent)
               self._lastevent = tick
            
            if tick - self._lastCalculate > self.WATCHDOG * 1000 and len(self._lastgoods) > self.SAMPLES:
               self._calculate()
               self._lastCalculate = tick
                     
      except:
         print("Unexpected error:", sys.exc_info()[0])
         traceback.print_exc()
         pass
         
   def _calculate(self):
      elements = self._lastgoods.copy()
      self._lastgoods = []
      self._rpm = 1 / (numpy.mean(elements) / 1000000) / 4 * 60
         
         
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

