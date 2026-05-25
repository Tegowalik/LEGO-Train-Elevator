from switch import *
from elevator_util import *

sensor1 = SwitchSensor(Port.A)
motor1 = SwitchMotor(Port.B, probabilities=1)

sensor2 = SwitchSensor(Port.C)
motor2 = SwitchMotor(Port.D, probabilities=1)

sensor3 = SwitchSensor(Port.E)
motor3 = SwitchMotor(Port.F, probabilities=1)

remoteSensor1 = SwitchRemoteSensor(Channel.SWITCH, Level.ONE)
post_sensors = {'c': remote_sensor1}
smart_sensor = SmartSensor(switch_sensor, post_sensors)

controller = SwitchController()
controller.register_sensor(remote_sensor1, motor1)