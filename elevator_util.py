from pybricks.parameters import Color, Stop
from pybricks.pupdevices import ColorLightMatrix
from pybricks.tools import wait
wait_fnc = wait
def enum(**enums):
    return type('Enum', (), enums)



Level = enum(ONE=1, TWO=2, THREE=3, TWO_HALF=21)

Level2Color = {
    Level.ONE: Color.BLUE,
    Level.TWO: Color.GREEN,
    Level.THREE: Color.ORANGE
}

Color2Level = {v: k for k, v in Level2Color.items()}

MotorState = enum(WAIT=0, DRIVE_TO=1, WAIT_DRIVE_IN=2, DRIVE_WITH=3, RELEASE=4)