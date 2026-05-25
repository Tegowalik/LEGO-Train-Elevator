from switch_small import *
from elevator_util import *

sensor1 = SwitchSensor(Port.A)
sensor2 = SwitchSensor(Port.B)
sensor3 = SwitchSensor(Port.C)

controller = SwitchController(broadcast_channel=Channel.SWITCH_SENSOR, default_broadcast=False)
controller.register_remote_sensor(sensor1, SensorID.ONE)
controller.register_remote_sensor(sensor2, SensorID.TWO)
controller.register_remote_sensor(sensor3, SensorID.THREE)
controller.run()