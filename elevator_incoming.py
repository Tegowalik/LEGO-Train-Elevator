from elevator_utils import *
from pybricks.hubs import ThisHub
from pybricks.parameters import Port, Color
from pybricks.pupdevices import ColorLightMatrix, ColorSensor, ColorDistanceSensor
from pybricks.tools import wait

sensor = ColorDistanceSensor(Port.A)
matrix_wait = ColorLightMatrix(Port.B) # shows per line which level is waiting
matrix_countdown = ColorLightMatrices(Port.C)
matrix_ok = ColorLightMatrix(Port.D)


hub = ThisHub(broadcast_channel=Channel.INCOMING, observe_channels=[Channel.MOTOR, Channel.SWITCH])

history_len = 10
is_blocked_history = [False] * history_len

TRUE = [Color.GREEN] * 9
FALSE = [Color.RED, Color.BLACK, Color.RED, Color.BLACK, Color.RED, Color.BLACK, Color.RED, Color.BLACK, Color.RED]

switchDelayer = Delayer(10)
motorDelayer = Delayer(10)

while True:
    r = sensor.distance()
    print(r)
    wait(400)
    is_blocked = r < 50
    is_blocked_history = [is_blocked] + is_blocked_history[:-1]
    is_blocked_stable = all(is_blocked_history)
    hub.ble.broadcast((is_blocked, is_blocked_stable))
    print(is_blocked)

    
    # receive MOTOR
    observed = hub.ble.observe(Channel.MOTOR)
    observed = motorDelayer.update(observed)
    #print(observed)
    if observed and len(observed) > 3:
        hub.light.on(Color.GREEN)

        level = observed[0]
        level = decode_levels(level)[0] # use incoming level

        color = Level2Color[level]
        hub.light.on(color)
        state = observed[1]
        new_level = observed[3]
        if new_level != False:
            new_level = decode_levels(new_level)[0]
        run = observed[7]
        if state in [MotorState.WAIT, MotorState.WAIT_DRIVE_IN, MotorState.RELEASE]:
            # indicate the countdown to indicate whether trains might still go on the elevator
           # color = Level2Color[level]
            if is_blocked:
                matrix = Color.MAGENTA
            else:
                matrix = Color.GREEN
            #print(matrix)
            matrix_countdown.on(matrix)
        elif state in [MotorState.DRIVE_TO, MotorState.DRIVE_WITH] and new_level:
            # new color
            new_color = Level2Color[new_level]
            matrix_countdown.on(new_color)
        else:
            matrix_countdown.off() 

        if run:
            matrix_ok.on(FALSE)
        else:
            matrix_ok.on(TRUE)
    else:
        # error 
        hub.light.blink(Color.RED, [200, 200])
        matrix_ok.on(Color.RED)
        wait(400)
        continue

    observed = hub.ble.observe(Channel.SWITCH)
    observed = switchDelayer.update(observed)
    print(observed)
    if observed and len(observed) >= 3:
        matrix = []
        is_waiting_ = observed[6:]
        for is_waiting, level in zip(reversed(is_waiting_), [Level.THREE, Level.TWO, Level.ONE]):
            if is_waiting:
                color = Level2Color[level] # todo indicate also next 
            else:
                color = Color.BLACK

            matrix += [color]
        matrix = 3*matrix
        matrix_wait.on(matrix)
    wait(100)
