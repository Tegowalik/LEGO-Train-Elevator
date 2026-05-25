from elevator_utils import *
from pybricks.pupdevices import ColorDistanceSensor, ColorLightMatrix
from pybricks.hubs import ThisHub
from pybricks.parameters import Port, Color, Button
from pybricks.tools import wait
from urandom import choice
from umath import ceil, floor

hub = ThisHub(broadcast_channel=Channel.OUTCOMING, observe_channels=[Channel.MOTOR, Channel.INCOMING])

sensor1 = ColorDistanceSensor(Port.A) # BLUE
sensor2 = ColorDistanceSensor(Port.C) # GREEN
sensor3 = ColorDistanceSensor(Port.B) # ORANGE

sensors = {
    Level.ONE: sensor1,
    Level.TWO: sensor2,
    Level.THREE: sensor3
}
levels = {v: k for k, v in sensors.items()}

matrix = ColorLightMatrix(Port.D)

# IDLE -> Wait for incoming train to pass incoming sensors
# COUNTDOWN -> Train passed incoming sensor -> timeout if train does not drive to the start, Selection process
# MOVE -> Elevator moves
# OUT -> Train goes out
State = enum(IDLE=1, COUNTDOWN=2, MOVE=3, OUT=4)
StateColor = {
    -1: Color.BLACK,
    State.IDLE: Color.WHITE,
    State.COUNTDOWN: Color.CYAN,
    State.MOVE: Color.VIOLET,
    State.OUT: Color.GREEN
}

state = State.IDLE
old_state = state
current_level = Level.THREE


def get_selected_color(level_data, current_level):
    highest_level = None
    if level_data[Level.THREE]:
        highest_level = Level.THREE
    elif level_data[Level.TWO]:
        highest_level = Level.TWO
    elif level_data[Level.ONE]:
        highest_level = Level.ONE
    
    if highest_level and highest_level != current_level:
        return Level2Color[highest_level]
    return Color.BLACK

def random_color():
    return choice([Color.BLUE, Color.GREEN, Color.ORANGE])

hub.system.set_stop_button(None)

history_len = 50 # todo longer

color_history = None
def reset_color_history():
    global color_history
    color_history = [None] * history_len
def append_to_color_history(color):
    global color_history
    color_history = [color] + color_history[:-1]

reset_color_history()

selected_level = False
threshold = 30 # 10 cm
motorDelayer = Delayer()
incomingDelayer = Delayer()
while True:
    # read input
    level_data = {level: sensor.distance() < threshold for level, sensor in sensors.items()}

    buttons = hub.buttons.pressed()
    if Button.CENTER in buttons:
        hub.system.shutdown()

    observed = hub.ble.observe(Channel.MOTOR)
    observed = motorDelayer.update(observed)
    if observed:
        current_level = observed[0]
        current_level= decode_levels(current_level)[1] # use outcoming level
    else:
        # Error
        hub.light.blink(Color.RED, [200, 200])
        matrix.on(Color.RED)
        print("Observed", observed, motorDelayer.history)
        wait(4000)
        state = -1
        continue

    observed = hub.ble.observe(Channel.INCOMING)
    observed = incomingDelayer.update(observed)
    if observed and len(observed) == 2:
        observed_incoming = observed[0]
    else:
        # Error
        hub.light.blink(Color.MAGENTA, [400, 400])
        matrix.on(Color.MAGENTA)
        print("Observed", observed, incomingDelayer.history)
        wait(4000)
        state = -1
        continue

    if state == -1:
        hub.light.blink(Color.GREEN, [500, 500])
        matrix.off()

    print(level_data, state, selected_level, observed_incoming, current_level)
    # update state
    if state in [-1, State.IDLE]:
        # check if move to COUNTDOWN
        if observed_incoming or any(level_data.values()):
            state = State.COUNTDOWN
            reset_color_history()
        else:
            state = State.IDLE

    if state == State.COUNTDOWN:
        selected_color = get_selected_color(level_data, current_level)
        append_to_color_history(selected_color)
        print(selected_color)

        if (len(set(color_history)) == 1 and None not in color_history) or (selected_color != Color.BLACK and len(set(color_history[:20])) == 1):
            # only a single color was selected in (relevant) history
            print("To MOVE")
            state = State.MOVE
            if selected_color == Color.BLACK:
                # a random color gets picked different to the current one
                current_color = Level2Color.get(current_level)
                color_candidates = [color for color in Color2Level if color != current_color]
                selected_color = choice(color_candidates)
                #todo this should be decided by MOTOR! -> use new_level entry during this state!
            selected_level = Color2Level[selected_color]

    if state == State.MOVE:
        if selected_level == current_level:
            state = State.OUT

    if state == State.OUT:
        selected_color = get_selected_color(level_data, current_level)
        #append_to_color_history(selected_color)
        if observed_incoming:
            state = State.COUNTDOWN
        elif selected_color == Color.BLACK:
            state = State.IDLE

    # update matrix
    if state == State.IDLE:
        if old_state != state:
            matrix.off()
    elif state == State.COUNTDOWN:
        # to indicate the progress, we use a the 9 matrix lights
        matching_colors = sum(color == selected_color for color in color_history)
        # matching_colors is always > 0 because selected_color is in color_history
        number_of_lights = floor(history_len / matching_colors)

        if selected_color == Color.BLACK: 
            # random colors
            matrix.on([random_color() if i >= number_of_lights else Color.NONE for i in range(9)])
        else:
            matrix.on([selected_color if i >= number_of_lights else Color.NONE for i in range(9)])

    elif state == State.MOVE:
        if old_state != state:
            matrix.on(selected_color)
    elif state == State.OUT:
        if old_state != state:
            matrix.on(Color.GREEN)

    # update light
    hub.light.on(StateColor[state])

    # send
    data = list(level_data.values()) # todo
    data.append(state == State.MOVE)
    data.append(selected_level)
    print("Broadcast ", data)
    hub.ble.broadcast(data)


    # sleep
    wait(100)
    old_state = state

