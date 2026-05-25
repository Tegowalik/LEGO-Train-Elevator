from pybricks.parameters import Color, Stop
from pybricks.pupdevices import ColorLightMatrix
from pybricks.tools import wait
from elevator_util import *

wait_fnc = wait
def enum(**enums):
    return type('Enum', (), enums)

Level = enum(ONE=1, TWO=2, THREE=3, TWO_HALF=5)

Level2Color = {
    Level.ONE: Color.BLUE,
    Level.TWO: Color.GREEN,
    Level.THREE: Color.ORANGE
}

INIT_ANGLE = 20000
#INIT_ANGLE = 10000

levels = {
    Level.ONE: -24400,
    #Level.TWO: 250,
    Level.TWO: 200,
    Level.TWO_HALF: 2000,
    Level.THREE: INIT_ANGLE
}

levels_ = {
    Level.ONE: -5000,
    Level.TWO: 2000,
    Level.TWO_HALF: 2500,
    Level.THREE: INIT_ANGLE
}


Color2Level = {v: k for k, v in Level2Color.items()}

Channel = enum(SWITCH=110, INCOMING=111, OUTCOMING=112, MOTOR=113, MOTOR_INCOMING=114, MOTOR_OUTCOMING=115, SWITCH_SENSOR=116, LEVEL_TWO_INCOMING=117, LEVEL_TWO_OUTCOMING=118)

CONFIGURATION = [Channel.MOTOR_INCOMING, Channel.MOTOR, Channel.MOTOR_OUTCOMING]
#CONFIGURATION = [Channel.MOTOR_INCOMING, Channel.MOTOR]
#CONFIGURATION = [Channel.MOTOR, Channel.MOTOR_OUTCOMING]

MotorState = enum(WAIT=0, DRIVE_TO=1, WAIT_DRIVE_IN=2, DRIVE_WITH=3, RELEASE=4)


next_level = {
    Level.ONE: Level.TWO,
    Level.TWO: Level.THREE,
    Level.THREE: Level.THREE 
}

prev_level = {
    Level.THREE: Level.TWO,
    Level.TWO: Level.ONE, 
    Level.ONE: Level.ONE,
}

level_encode_map = {Level.ONE: 0, Level.TWO: 1, Level.THREE: 2, Level.TWO_HALF: 3}
def encode_levels(level_incoming, level_outcoming):
    """
    Encodes level_incoming and level_outcoming into a single integer (0-127).
    Each level is represented by 3 bits (enough to store four values).
    """
    # Map levels to their encoded values
    incoming_encoded = level_encode_map[level_incoming]
    outgoing_encoded = level_encode_map[level_outcoming]

    # Combine into a single byte (shift and bitwise OR)
    encoded = (incoming_encoded << 3) | outgoing_encoded
    return encoded

def decode_levels(encoded_level):
    """
    Decodes an integer (0-127) into level_incoming and level_outcoming.
    """
    if not (0 <= encoded_level <= 127):
        raise ValueError("Encoded level must be between 0 and 127.")

    # Reverse mapping of the encoding
    level_map = {v: k for k, v in level_encode_map.items()}

    # Extract the incoming and outgoing levels
    incoming_encoded = (encoded_level >> 3) & 0b111  # Top 3 bits
    outgoing_encoded = encoded_level & 0b111        # Bottom 3 bits

    level_incoming = level_map[incoming_encoded]
    level_outcoming = level_map[outgoing_encoded]

    return level_incoming, level_outcoming

class ColorLightMatrices:
    def __init__(self, *args):
        print(args)
        self.matrices = [ColorLightMatrix(port) for port in args]

    def on(self, colors):
        for matrix in self.matrices:
            matrix.on(colors)

    def off(self):
        for matrix in self.matrices:
            matrix.off()


class MotorGroup:

# first two motors are pos 1, other two motors are pos 2
# left right support probably needed
    def __init__(self, *args):
        self.motors = list(args)
        print(self.motors)
        #for motor in self.motors:
        #    motor.reset_angle(INIT_ANGLE)

    def run_target(self, target_angle, power=1000):
        if isinstance(target_angle, (int, float)):
            target_angle = [target_angle] * len(self.motors)

        for ta, motor in zip(target_angle, self.motors):
            if power == 0:
                motor.stop()
            else:
                motor.run_target(power, ta, then=Stop.COAST, wait=False)

    def run_targets(self, target_angle_1, target_angle_2, power=1000):
        self.run_target([target_angle_1, target_angle_1, target_angle_2, target_angle_2], power=power)
    
    def track_target(self, target_angle, power=1000):
        if isinstance(target_angle, (int, float)):
            target_angle = [target_angle] * len(self.motors)

        for ta, motor in zip(target_angle, self.motors):
            #print(ta, power)
            if power == 0:
                motor.stop()
            else:
                motor.track_target(ta)

    def track_targets(self, angle1, angle2, power=1000):
        self.track_target([angle1, angle1, angle2, angle2], power=power)


    def run(self, speed, speed2=None):
        if speed2 is not None:
            speed = [speed, speed, speed2, speed2]
        if isinstance(speed, (int, float)):
            speed = [speed] * len(self.motors)

        for ta, motor in zip(speed, self.motors):
            if ta == 0:
                motor.stop()
            else:
                motor.run(ta)


    def run_time(self, speed, time, then=Stop.BRAKE, wait=True):
        for motor in self.motors:
            motor.run_time(speed, time, then, wait=False)

        if wait:
            while not all(motor.done() for motor in self.motors):
                wait_fnc(100)


    def stop(self):
        for motor in self.motors:
            motor.stop()

    def is_running(self):
        return not all(motor.done() for motor in self.motors)

    def run_until_stalled(self, speed):
        for motor in self.motors:
            motor.run(speed)
            wait(1000)

        running_motors = [m for m in self.motors]
        while running_motors:
            print("Running")
            for motor in running_motors:
                print("Load %d" % motor.load())
                if abs(motor.load()) > 10:
                    motor.hold()
                    running_motors = [r for r in running_motors if r != motor]
                
            
            wait(200)
        

    def reset_angle(self, angle):
        for motor in self.motors:
            motor.reset_angle(angle)

    def done(self):
        return all(motor.done() for motor in self.motors)

    def angle(self):
        return int(sum(motor.angle() for motor in self.motors) / len(self.motors))

    def angles(self):
        n = int(len(self.motors) / 2)
        return int(sum(motor.angle() for motor in self.motors[:n]) / n), int(sum(motor.angle() for motor in self.motors[n:]) / n)

    def stalled(self):
        is_stalled = True
        for motor in self.motors:
            if motor.stalled():
                motor.stop()
            else:
                is_stalled = False
        return is_stalled

        return all(motor.stalled() for motor in self.motors)

    def load(self, direction=None):
        is_load_critical = True
        loads = []
        border = 35 if direction is None or direction > 0 else 10
        for motor in self.motors:
            l = motor.load()
            loads.append(l)
            s = motor.stalled()
            done = False
            if abs(l) > border or s:
                motor.stop()
                print("Motor done")
                done = True
            elif l != 0:
                is_load_critical = False

            if direction and direction > 0 and not done and l != 0:
                if abs(l) < border - 5:
                    motor.run(300 * direction)
                elif abs(l) < border - 2:
                    motor.run(100 * direction)
                else:
                    motor.run(50 * direction)
        return is_load_critical and any(loads)

class Level2Platform():

    def __init__(self, motor):
        self.motor = motor
    
    def extend(self):
        self.motor.run_target(1000, -15000, wait=False, then=Stop.BRAKE)

    def contract(self):
        self.motor.run_target(1000, 0, wait=False, then=Stop.BRAKE)

def run_motor(motor, speed):
    if speed == 0:
        motor.stop()
    else:
        motor.run(speed)

class Delayer:
    def __init__(self, history_len=20):
        self.history = []
        self.history_len = history_len

    def update(self, x):
        if len(self.history) == self.history_len:
            self.history = self.history[1:] + [x]
        else:
            self.history.append(x)

        cleaned = [xx for xx in self.history if xx is not None]
        if cleaned:
            return cleaned[0]
        else:
            return None

def interpolate_target_angles(start_angle_incoming, start_angle_outcoming, target_angle_incoming, target_angle_outcoming, pos):
    m_start = start_angle_outcoming - start_angle_incoming
    n_start = start_angle_incoming
    m_target = target_angle_outcoming - target_angle_incoming
    n_target = target_angle_incoming

    print(m_start, pos, n_start)
    y_start = m_start * pos + n_start
    y_target = m_target * pos + n_target
    print('y_start', y_start, 'y_target', y_target)

    def interpolate(progress):
        return y_start * (1 - progress) + y_target * progress

    def angle2progress(angle):
        # Reverse the interpolate function to solve for progress
        
        if y_start != y_target: 
            return (angle - y_start) / (y_target - y_start)
        else:
            return 1.0
    
    return interpolate, angle2progress

PROGRESS_FACTOR = 1000