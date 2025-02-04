
# -*- coding: utf-8 -*-
import asyncio
from asyncio import tasks
import logging
from cbpi.api import *
import time
import datetime

@parameters([Property.Number(label = "P", configurable = True, description="P Value of PID"),
             Property.Number(label = "I", configurable = True, description="I Value of PID"),
             Property.Number(label = "D", configurable = True, description="D Value of PID"),
             Property.Number(label = "Max_Output", configurable = True, description="Maximum power to use before Boil threshold is reached."),
             Property.Select(label="SampleTime", options=[2,5], description="PID Sample time in seconds. Default: 5 (How often is the output calculation done)"),
             Property.Number(label = "Threshold1", configurable = True, description="When this temperature is reached, power will be set to Max Output1"),
             Property.Number(label = "Max_Output1", configurable = True, description="Power to set after Threshold1 is reached."),
             Property.Number(label = "Threshold2", configurable = True, description="When this temperature is reached, power will be set to Max Output2"),
             Property.Number(label = "Max_Output2", configurable = True, description="Power to set after Threshold2 is reached."),
             Property.Number(label = "Threshold3", configurable = True, description="When this temperature is reached, power will be set to Max Output3 (default: 0"),
             Property.Number(label = "Max_Output3", configurable = True, description="Power to set after Threshold3 is reached (Default: 100)"),
             Property.Number(label = "Boil_Threshold", configurable = True, description="When this temperature is reached, power will be set to Max Boil Output (default: 98 °C/208 F)"),
             Property.Number(label = "Max_Boil_Output", configurable = True, default_value = 85, description="Power when Boil Threshold is reached.")])

class PIDVariablePowerBoil(CBPiKettleLogic):


    async def on_stop(self):
        await self.actor_off(self.heater)
        pass

    async def run(self):
        try:
            self.TEMP_UNIT = self.get_config_value("TEMP_UNIT", "C")
            wait_time = sampleTime = int(self.props.get("SampleTime",5))
            boilthreshold = 98 if self.TEMP_UNIT == "C" else 208

            logging.debug("%s Accepting pid", self.__class__.__name__)
            p = float(self.props.get("P", 117.0795))
            i = float(self.props.get("I", 0.2747))
            d = float(self.props.get("D", 41.58))

            logging.debug("%s Getting thresholds", self.__class__.__name__)
            maxout = int(self.props.get("Max_Output", 100))
            threshold1 = self.props.get("Threshold1")
            maxout1 = self.props.get("Max_Output1")
            threshold2 = self.props.get("Threshold2")
            maxout2 = self.props.get("Max_Output2")
            threshold3 = self.props.get("Threshold3")
            maxout3 = self.props.get("Max_Output3")
            logging.debug("%s Setting threshold1", self.__class__.__name__)
            if threshold1 is not None and maxout1 is not None:
                threshold1 = int(threshold1)
                maxout1 = int(maxout1)
            else:
                threshold1 = None
                maxout1 = None
            logging.debug("%s Setting threshold2", self.__class__.__name__)
            if threshold2 is not None and maxout2 is not None:
                threshold2 = int(threshold2)
                maxout2 = int(maxout2)
            else:
                threshold2 = None
                maxout2 = None
            logging.debug("%s Setting threshold3", self.__class__.__name__)
            if threshold3 is not None and maxout3 is not None:
                    threshold3 = int(threshold3)
                    maxout3 = int(maxout3)
            else:
                threshold3 = None
                maxout3 = None

            logging.debug("%s Setting maxboil", self.__class__.__name__)
            maxtempboil = float(self.props.get("Boil_Threshold", boilthreshold))
            maxboilout = int(self.props.get("Max_Boil_Output", 100))

            logging.debug("%s Setting up kettle variablels", self.__class__.__name__)
            self.kettle = self.get_kettle(self.id)
            self.heater = self.kettle.heater
            heat_percent_old = maxout
            self.heater_actor = self.cbpi.actor.find_by_id(self.heater)
                       
            await self.actor_on(self.heater, maxout)

            logging.debug("%s Calling PIDArduino", self.__class__.__name__)
            pid = PIDArduino(sampleTime, p, i, d, 0, maxout)

            while self.running == True:
                current_kettle_power= self.heater_actor.power
                sensor_value = current_temp = self.get_sensor_value(self.kettle.sensor).get("value")
                target_temp = self.get_kettle_target_temp(self.id)
                if current_temp >= float(maxtempboil):
                    heat_percent = maxboilout
                else:
                    last_threshold = 0
                    heat_percent = heat_percent_threshold = pid.calc(sensor_value, target_temp)
                    logging.debug("%s Testing thresholds, sensor_value = %d", self.__class__.__name__,sensor_value)
                    if threshold1 is not None and maxout1 is not None:
                        if sensor_value >= threshold1 and threshold1 >= last_threshold:
                            logging.debug("%s threshold1 = %d heat_percent = %d", self.__class__.__name__, threshold1, heat_percent)
                            heat_percent_threshold = min(heat_percent, maxout1)
                            last_threshold = threshold1
                    if threshold2 is not None and maxout2 is not None:
                        if sensor_value >= threshold2 and threshold2 >= last_threshold:
                            logging.debug("%s threshold2 = %d heat_percent = %d", self.__class__.__name__, threshold2, heat_percent)
                            heat_percent_threshold = min(heat_percent, maxout2)
                            last_threshold = threshold2
                    if threshold3 is not None and maxout3 is not None:
                        if sensor_value >= threshold3 and threshold3 >= last_threshold:
                            logging.debug("%s threshold3 = %d heat_percent = %d", self.__class__.__name__, threshold3, heat_percent)
                            heat_percent_threshold = min(heat_percent, maxout3)
                            last_threshold = threshold3
                    heat_percent = heat_percent_threshold

                if (heat_percent_old != heat_percent) or (heat_percent != current_kettle_power):
                    await self.actor_set_power(self.heater, heat_percent)
                    heat_percent_old= heat_percent
                await asyncio.sleep(sampleTime)

        except asyncio.CancelledError as e:
            pass
        except Exception as e:
            logging.error("%s Error %s", self.__class__.__name__, e)
            #logging.error("BM_PIDSmartBoilWithPump Error {}".format(e))
        finally:
            self.running = False
            await self.actor_off(self.heater)

# Based on Arduino PID Library
# See https://github.com/br3ttb/Arduino-PID-Library
class PIDArduino(object):

    def __init__(self, sampleTimeSec, kp, ki, kd, outputMin=float('-inf'),
                 outputMax=float('inf'), getTimeMs=None):
        if kp is None:
            raise ValueError('kp must be specified')
        if ki is None:
            raise ValueError('ki must be specified')
        if kd is None:
            raise ValueError('kd must be specified')
        if float(sampleTimeSec) <= float(0):
            raise ValueError('sampleTimeSec must be greater than 0')
        if outputMin >= outputMax:
            raise ValueError('outputMin must be less than outputMax')

        self._logger = logging.getLogger(type(self).__name__)
        self._Kp = kp
        self._Ki = ki * sampleTimeSec
        self._Kd = kd / sampleTimeSec
        self._sampleTime = sampleTimeSec * 1000
        self._outputMin = outputMin
        self._outputMax = outputMax
        self._iTerm = 0
        self._lastInput = 0
        self._lastOutput = 0
        self._lastCalc = 0

        if getTimeMs is None:
            self._getTimeMs = self._currentTimeMs
        else:
            self._getTimeMs = getTimeMs

    def calc(self, inputValue, setpoint):
        now = self._getTimeMs()

        if (now - self._lastCalc) < self._sampleTime:
            return self._lastOutput

        # Compute all the working error variables
        error = setpoint - inputValue
        dInput = inputValue - self._lastInput

        # In order to prevent windup, only integrate if the process is not saturated
        if self._lastOutput < self._outputMax and self._lastOutput > self._outputMin:
            self._iTerm += self._Ki * error
            self._iTerm = min(self._iTerm, self._outputMax)
            self._iTerm = max(self._iTerm, self._outputMin)

        p = self._Kp * error
        i = self._iTerm
        d = -(self._Kd * dInput)

        # Compute PID Output
        self._lastOutput = p + i + d
        self._lastOutput = min(self._lastOutput, self._outputMax)
        self._lastOutput = max(self._lastOutput, self._outputMin)

        # Log some debug info
        self._logger.debug('P: {0}'.format(p))
        self._logger.debug('I: {0}'.format(i))
        self._logger.debug('D: {0}'.format(d))
        self._logger.debug('output: {0}'.format(self._lastOutput))

        # Remember some variables for next time
        self._lastInput = inputValue
        self._lastCalc = now
        return self._lastOutput

    def _currentTimeMs(self):
        return time.time() * 1000

def setup(cbpi):

    '''
    This method is called by the server during startup 
    Here you need to register your plugins at the server
    
    :param cbpi: the cbpi core 
    :return: 
    '''

    cbpi.plugin.register("PIDVariablePowerBoil", PIDVariablePowerBoil)