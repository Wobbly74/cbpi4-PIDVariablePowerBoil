# Craftbeerpi4 Kettle Logic Plugin

## PID Variable Power Boil

This is a simple extension of the standad PIDBoil extension located at https://github.com/PiBrewing/cbpi4-PIDBoil

This extension adds 3 temperature thresholds to restrict power output at. I wrote this so that I could vary the
power of a relatively high wattage element to avoid scorching resulting from thick or high protein mashes. I use
this to ramp my 4500w element at 100% initially to get to strike temperature, then ramp it down to < 50% during
the protein rest stage of the mash betweeen 50-60C, then gradually increase the power during mashing and mashout
before returnbing to 100% power to ramp and conduct the boil.

### Installation:

You can install (or clone) it from the GIT Repo. In case of updates, you will find them here first:
- sudo pip3 install https://github.com/Wobbly74/cbpi4-PIDVariablePowerBoil/archive/main.zip

## Usage:

To use this custom kettle logic, just select it as an alternative to PIDBoil in your kettle setup (assuming that's what you use).

## Parameters:

Existing parameters for PIDBoil have been maintained as-is and continue to be respected as they were. Max_Output
is respected in preference to any of the temperature threshold power levels (so they will never exceed Max_Output).

- Additional Parameters:
	- Threshold1..3: The temperature threshold to trigger this power level. If you want this to start from the very beginning then set this to 0.
    - Max_Output1..3: The maximum power level to apply during this temperature threshold (until next higher threshold or the boil threshold is reached)

The thresholds can be specified in any order - they will be applied in ascending temperature order.

Changelog:

- 22.06.24: Initial version