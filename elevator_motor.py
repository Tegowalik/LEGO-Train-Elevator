from pybricks.pupdevices import Motor, Remote
from pybricks.parameters import Port, Stop, Button, Color, Icon, Direction
from elevator_utils import *
from pybricks.tools import wait, StopWatch, Matrix
from urandom import randint
from pybricks.hubs import ThisHub

from elevator_utils import MotorState as State


MainState = enum(AUTO_ELEVATOR=0, MANUAL_ELEVATOR=1, MANUAL_BRIDGE=3)

main_state_color = {
    MainState.AUTO_ELEVATOR: Color.WHITE,
    MainState.MANUAL_ELEVATOR: Color.GRAY,
    MainState.MANUAL_BRIDGE: Color.BROWN,
}

next_main_state = {
    MainState.AUTO_ELEVATOR: MainState.MANUAL_ELEVATOR,
    MainState.MANUAL_ELEVATOR: MainState.MANUAL_BRIDGE,
    MainState.MANUAL_BRIDGE: MainState.AUTO_ELEVATOR,
}

main_state_char = {
    MainState.AUTO_ELEVATOR: 'A',
    MainState.MANUAL_ELEVATOR: 'M',
    MainState.MANUAL_BRIDGE: 'B',
}

# whenever bluetooth button is pressed -> calibration (update motor angles)
# main button -> manual control
# Remote support???
class Controller:

    def __init__(self, up_down: MotorGroup, levels: dict, motors: dict, configuration: list, main_state_color_matrix=None):
        self.up_down = up_down
        self.levels = levels # maps levels to motor angles
        self.default_levels = levels.copy()
        self.configuration = configuration
        self.other_motor_hub_channels = [c for c in configuration if isinstance(c, int) and c != Channel.MOTOR]
        observe_channels = [Channel.SWITCH, Channel.INCOMING, Channel.OUTCOMING] + self.other_motor_hub_channels
        self.hub = ThisHub(broadcast_channel=Channel.MOTOR, observe_channels=observe_channels)
        self.hub.system.set_stop_button(None)
        self.dt = 100
        self.state = State.WAIT
        self.requests = []
        self.motors = motors
        self.new_level = -1
        self.countdown = False
        self.main_state_color_matrix = main_state_color_matrix

        self.count = 0
        if None in configuration:
            self.group = configuration.index(None)
        elif Channel.MOTOR in configuration:
            self.group = configuration.index(Channel.MOTOR)
        else:
            raise ValueError("Configuration without None/Channel.MOTOR", configuration)

        # determine position proportions
        n = 2 * len(configuration) - 1
        self.position_2 = 2 * self.group / n
        self.position_1 = (2 * self.group + 1) / n
        print('pos1', self.position_1, 'pos2', self.position_2)


        self.max_count = 4 * len(configuration)
        angles = self.up_down.angles()

        def get_nearest_level(init_angle):
            for level, angle in self.levels.items():
                if abs(angle - init_angle) < 1000:
                    return level

            return None

        self.power = 0
        self.remote = None
        self.run = False
        self.level2_incoming = False
        self.level2_outcoming = False
        self.remote_motors = []
        self.main_state = MainState.AUTO_ELEVATOR
        self.set_main_state(self.main_state) # set color
        self.watch = StopWatch()



        if abs(angles[0] - angles[1]) < 10:
            self.target = self.up_down.angle()
            self.level_incoming = get_nearest_level(self.target) or Level.THREE
            self.level_outcoming = self.level_incoming
            print("Start at level ", self.level_outcoming)
        else:
            self.level_incoming = Level.THREE
            self.level_outcoming = Level.THREE
            self.reset()
            self.reset()
            self.reset()
            
            print("Start at levels", self.level_incoming, self.level_outcoming)
            self.target = 0
            # todo this does not work with motor extensions!!, hence always use Level.THREE!
        #wait(10000)



        #self.reset()


    def calibrate(self):
        # the elevator starts from all the way on top
        # semi automated calibration
        # elevator goes to predefined states
        # user finetunes it by button presses
        

        # drive to the top
        self.up_down.run_until_stalled(speed=100)

        self.up_down.reset()
        self.level_incoming = Level.THREE
        self.level_outcoming = Level.THREE
        self.state = State.WAIT

    def button(self, button):
        return button in self.hub.buttons.pressed()

    def connect_remote(self):
        try:
            self.remote = Remote(timeout=5000)
            self.remote.light.on(Color.CYAN)
        except OSError:
            print("Error")

    def set_main_state(self, state):
        if state != self.main_state:
            self.main_state = state
            state_color = main_state_color[state]
            self.hub.light.on(state_color)

            self.set_remote_light(state_color)

    def set_remote_light(self, state):
        try:
            self.remote.light.on(state)
        except Exception:
            pass

    def remote_buttons(self):
        try:
            return self.remote.buttons.pressed()
        except Exception:
            return []

    def config_mode(self):
        self.hub.display.icon(Icon.HAPPY)

        while self.button(Button.BLUETOOTH):
            wait(100)

        try:
            while self.remote.buttons.pressed():
                wait(100)
        except Exception:
            pass
  

        up_down_speed = 0 # todo remove
        speed = 0
        delta = 50
        mode = 5
        modes = [Color.CYAN, Color.GREEN, Color.YELLOW, Color.MAGENTA, Color.WHITE, Color.BLUE]
        port = Port.A
        self.remote.light.on(modes[mode])
        new_level_incoming = self.level_incoming
        new_level_outcoming = self.level_outcoming

        next_port = {
            Port.A: Port.B,
            Port.B: Port.C,
            Port.C: Port.D,
            Port.D: Port.E,
            Port.E: Port.F,
            Port.F: Port.A
        }
        previous_port = {v: k for k, v in next_port.items()}

        def show_port(port):
            if port == Port.A:
                matrix = [100]
            elif port == Port.B:
                matrix = [0, 100]
            elif port == Port.C:
                matrix = [0, 0, 100]
            elif port == Port.D:
                matrix = [0, 0, 0, 100]
            elif port == Port.E:
                matrix = [0, 0, 0, 0, 100]
            elif port == Port.F:
                matrix = [0, 0, 0, 0, 0, 100]

        port_char = {
            Port.A: 'A',
            Port.B: 'B',
            Port.C: 'C',
            Port.D: 'D',
            Port.E: 'E',
            Port.F: 'F'
        }

        side = 0
        side_icon = {
            0: Icon.ARROW_RIGHT,
            1: Icon.ARROW_LEFT
        }
        group = 0
        config_target = self.up_down.angle()

        while True:
            buttons = self.hub.buttons.pressed()
            if Button.BLUETOOTH in buttons:
                wait(300)
                return
            elif Button.CENTER in buttons:
                self.stop()

            buttons = self.remote_buttons()
            self.receive()

            if Button.CENTER in buttons:
                if Button.LEFT in buttons:
                    return

                watch = StopWatch()
                while Button.CENTER in self.remote_buttons():
                    wait(100)
                    if watch.time() > 500:
                        return
                else:
                    # switch the mode
                    mode = (mode + 1) % len(modes)
                    self.remote.light.on(modes[mode])
                    up_down_speed = 0
                    self.hub.display.off()

            if mode == 0:
                self.hub.light.on(Color.GREEN)
                self.hub.display.icon(Icon.FULL)
                # all motors move
                if Button.LEFT_MINUS in buttons:
                    speed -= delta
                elif Button.LEFT_PLUS in buttons:
                    speed += delta
                elif Button.LEFT in buttons:
                    speed = 0

                # check if other hubs are connected
                if not self.remote_motors_connected():
                    speed = 0
                    self.hub.light.blink(Color.RED, [200, 200])
                    wait(300)
                
                self.up_down.run(speed)
                
            elif mode == 1:
                # every motor individual
                count_floor = self.count // 4
                def show_group():
                    if count_floor == self.group:
                        # this group is controlled
                        self.hub.light.on(Color.WHITE)
                    else:
                        self.hub.light.on(Color.BLACK)

                    i = self.count % 4
                    if i == 0:
                        # right bottom
                        icon = Icon.ARROW_RIGHT_DOWN
                    elif i == 1:
                        icon = Icon.ARROW_RIGHT_UP
                    elif i == 2:
                        icon = Icon.ARROW_LEFT_DOWN
                    elif i == 3:
                        icon = Icon.ARROW_LEFT_UP

                    self.hub.display.icon(icon)
                    
                show_group()

                if Button.LEFT_MINUS in buttons:
                    speed -= delta
                elif Button.LEFT_PLUS in buttons:
                    speed += delta
                elif Button.LEFT in buttons:
                    speed = 0
                
                if count_floor == self.group:
                    i = self.count % 4
                    motor = self.up_down.motors[i]
                    run_motor(motor, speed)

                if Button.RIGHT_PLUS in buttons:
                    self.count = (self.count + 1) % (self.max_count)
                    show_group()
                    wait(300)
                elif Button.RIGHT_MINUS in buttons:
                    self.count = (self.count - 1) % (self.max_count)
                    show_group()
                    wait(300)
            elif mode == 2:
                self.hub.display.char("G")
                if Button.LEFT_MINUS in buttons:
                    speed -= delta
                elif Button.LEFT_PLUS in buttons:
                    speed += delta
                elif Button.LEFT in buttons:
                    speed = 0

                if group == self.group:
                    self.hub.light.on(Color.WHITE)
                    self.up_down.run(speed)
                else:
                    self.hub.light.on(Color.BLACK)
                    self.up_down.run(0)
            elif mode == 3:
                mode += 1 # deprecated
            elif mode == 4:
                self.hub.display.icon(Icon.CLOCKWISE)
                if Button.RIGHT in buttons:
                    self.hub.display.icon(Icon.HEART)
                    self.reset()
            elif mode == 5:
                # go to level
                # todo make it more flexible
                if Button.LEFT_MINUS in buttons:
                    new_level_incoming  = ((new_level_incoming - 2) % 3) + 1
                    new_level_outcoming  = ((new_level_outcoming - 2) % 3) + 1
                elif Button.LEFT_PLUS in buttons:
                    new_level_incoming = (new_level_incoming % 3) + 1
                    new_level_outcoming = (new_level_outcoming % 3) + 1
                elif Button.LEFT in buttons:
                    # reset
                    new_level_incoming = self.level_incoming
                    new_level_outcoming = self.level_outcoming
                elif Button.RIGHT in buttons:
                    self.run_target(new_level_incoming, new_level_outcoming)

                if new_level_incoming == new_level_outcoming:
                    self.hub.display.char(str(new_level_incoming))
                else:
                    # todo display diagnols
                    self.hub.display.text(f'{new_level_incoming}-{new_level_outcoming}')
                if buttons:
                    wait(200)

            self.hub.ble.broadcast((mode, speed, self.count))
            wait(100)
                
    def send(self):
        level = encode_levels(self.level_incoming, self.level_outcoming)
        if self.new_level == -1:
            new_level = -1
        elif isinstance(self.new_level, tuple):
            new_level = encode_levels(*self.new_level)
        else:
            new_level = encode_levels(self.new_level, self.new_level)

        data = (level, self.state, self.countdown, new_level, self.ready, int(self.target), self.power, self.run, self.level2_incoming, self.level2_outcoming)
        self.hub.ble.broadcast(data)

    def receive(self):
        self.switch = self.hub.ble.observe(Channel.SWITCH)
        if self.switch is None:
            self.switch = [None, None, None]

        self.incoming = self.hub.ble.observe(Channel.INCOMING)
        self.outcoming = self.hub.ble.observe(Channel.OUTCOMING)

        self.remote_motors = [self.hub.ble.observe(channel) for channel in self.other_motor_hub_channels]

    def remote_motors_connected(self):
        return all(self.remote_motors)

    def remote_motors_done(self):
        return all(x[1] if x is not None else False for x in self.remote_motors)

    def remote_motors_running(self):
        return all(not x[1] if x is not None else False for x in self.remote_motors)

    def remote_motors_level(self, level):
        return all(x[2] == level if x is not None else False for x in self.remote_motors)

    def update_display(self):
        # todo
        pass


    def reset(self):
        print("reset")


        # wait 
        self.hub.light.blink(Color.RED, [1000, 1000])
        while not self.remote_motors_connected() or any(len(x) == 1 if x else True for x in self.remote_motors):
            print("Can not reset")
            wait(100)


        # go up until stalled
        self.hub.light.on(Color.WHITE)


        self.hub.ble.broadcast((True, ))
        self.up_down.run(100)
        print("up")
        wait(100)
        while not self.up_down.load(1):
            print("up")
            wait(400)
            self.hub.ble.broadcast((True, ))

        #  go a bit downwards again
        wait(100)
        self.up_down.run(-100)
        print("down")
        wait(2000)
        while self.up_down.load(-1):
            print("down")
            wait(100)
            self.hub.ble.broadcast((True, ))

        if self.remote_motors:
            # wait for other motors to complete
            print("Wait")
            self.receive()
            while True:
                if all(x is not None and len(x) == 1 and x[0] for x in self.remote_motors):
                    break

                self.hub.ble.broadcast((True, ))

                buttons = self.remote.buttons.pressed()
                if Button.CENTER in buttons:
                    break

                wait(100)
                self.receive()

        # reset internal parameters
        self.up_down.reset_angle(INIT_ANGLE)
        self.level_incoming = Level.THREE
        self.level_outcoming = Level.THREE


        print("Done")
        self.hub.light.on(Color.GREEN)
    
    def run_target(self, level_incoming, level_outcoming=None):
        level_outcoming = level_outcoming or level_incoming
        if level_incoming == self.level_incoming and level_outcoming == self.level_outcoming:
            print("Already at level %s and %s" % (level_incoming, level_outcoming))
            return

        self.ready = True
        print("Run target levels %s - %s from %s -%s" % (level_incoming, level_outcoming, self.level_incoming, self.level_outcoming))

        level2time = 10000 if self.remote_motors else 0
        def waitLevel2():
            watch = StopWatch()
            while watch.time() < level2time:
                self.send()
                wait(100)

        if level_incoming == level_outcoming and self.level_incoming == self.level_outcoming:
            # normal elevator mode (move platform in parallel to floor)
            print('Normal Mode')
            level = level_incoming
            target_angle = self.levels[level_incoming]
            going_down = self.up_down.angle() > target_angle

            self.new_level = level_incoming, level_outcoming
            self.level2_incoming = False
            self.level2_outcoming = False

            if level == Level.TWO:
                print('Going to level TWO')
                if going_down:
                    self.level2_incoming = True
                    self.level2_outcoming = True
                else:
                    print("Go to Level.TWO over Level.TWO_HALF")
                    self.run_target_(self.levels[Level.TWO_HALF])
                    print("Reached Level.TWO_HALF")

                    self.level2_incoming = True
                    self.level2_outcoming = True
                    waitLevel2()

                self.run_target_(self.levels[Level.TWO])
                print("Reached Level.TWO")

            elif self.level_incoming == Level.TWO and going_down:
                print("Release platform")
                waitLevel2() # wait to release the platform
                self.run_target_(target_angle)
            else:
                self.run_target_(target_angle)

        else:
            print('Bridge Mode')
            # bridge mode
            if level_incoming == Level.THREE and level_outcoming == Level.ONE or level_incoming == Level.ONE and level_outcoming == Level.THREE:
                print('Error: Can not use bridge from ONE to THREE or vice versa!')
                self.hub.light.on(Color.RED)
                wait(1000)
                return

            
            self.level2_incoming = False
            self.level2_outcoming = False

            intermediate_target_incoming = level_incoming
            intermediate_target_outcoming = level_outcoming
            if level_incoming == Level.TWO or level_outcoming == Level.TWO:
                if level_incoming == Level.TWO:
                    if self.level_incoming == Level.ONE:
                        intermediate_target_incoming = Level.TWO_HALF
                        print('Going incoming first to TWO_HALF')
                    else:
                        self.level2_incoming = True

                if level_outcoming == Level.TWO:
                    if self.level_outcoming == Level.ONE:
                        intermediate_target_outcoming = Level.TWO_HALF
                        print('Going outcoming first to TWO_HALF')
                    else:
                        self.level2_outcoming = True
                
                if level_incoming == Level.ONE and self.level_incoming == Level.TWO or level_outcoming == Level.ONE and self.level_outcoming == Level.TWO:
                    print("Waiting to release level 2")
                    waitLevel2()
                else:
                    print("no need 2 release", level_incoming, self.level_incoming, level_outcoming, self.level_outcoming)
                    #wait(10000) # todo

            print('Start Running to new bridge position', intermediate_target_incoming, intermediate_target_outcoming, level_incoming, level_outcoming)
            angle_incoming, angle_outcoming = self.levels[intermediate_target_incoming], self.levels[intermediate_target_outcoming]
            self.new_level = intermediate_target_incoming, intermediate_target_outcoming
            self.run_targets_(angle_incoming, angle_outcoming)
            
            if intermediate_target_incoming != level_incoming or intermediate_target_outcoming != level_outcoming:
                self.level_incoming, self.level_outcoming = self.new_level
                self.level2_outcoming = level_outcoming == Level.TWO
                self.level2_incoming = level_incoming == Level.TWO
                print('Go from TWO_HALF to TWO', self.level2_incoming, self.level2_outcoming)
                waitLevel2()
                #wait(1000)

                self.new_level = level_incoming, level_outcoming
                angle_incoming, angle_outcoming = self.levels[level_incoming], self.levels[level_outcoming]
                self.run_targets_(angle_incoming, angle_outcoming)

        self.ready = False
        print('New levels', level_incoming, level_outcoming)
        self.level_incoming = level_incoming
        self.level_outcoming = level_outcoming
    

    def run_target_(self, target_angle):
        self.target = self.up_down.angle()
        if target_angle == self.target:
            print("Already at target!")
            return

        self.run = True
        self.power = 50
        self.send()
        watch = StopWatch()
        max_offset = 1500
        critical_offset = 500
        direction = -1 if self.target > target_angle else 1
        #print("Direction ", direction)
        #self.wait(1000)
        delta = 10

        def mostCriticalAngleOffset():
            return max(abs(self.up_down.angle() - x[3]) if x is not None and len(x) > 3 else max_offset for x in self.remote_motors, default=0)
                
        power_up_down = 100
        max_power = 900
        self.up_down.run(100 * direction)

        def exit():
            self.run = False
            self.up_down.run(0)
            self.target = self.up_down.angle()

        while True:
            buttons = self.hub.buttons.pressed()
            if Button.CENTER in buttons:
                exit()
                return
            if self.remote:
                buttons = self.remote_buttons()
                if Button.CENTER in buttons:
                    exit()
                    return

            self.receive()
            critical_angle = mostCriticalAngleOffset()
            self.target = self.up_down.angle()
            error = abs(self.target - target_angle)
            if error < 10 and critical_angle < 10:
                print("Reached target!!")
                self.hub.light.on(Color.WHITE)
                self.power = 0
                exit()
                return
            elif error < 1000:
                print("Almost there")
                self.hub.light.blink(Color.GREEN, [50, 50])
                self.up_down.track_target(target_angle)
            else:
                if critical_angle >= max_offset:
                    power_up_down = 0
                    self.hub.light.on(Color.RED)
                    print("Stop at c angle ", critical_angle)
                elif critical_angle > critical_offset:
                    power_up_down = max(power_up_down - 2 * delta, 10)
                    self.hub.light.on(Color.ORANGE)
                else:
                    self.hub.light.on(Color.GREEN)
                    power_up_down = min(power_up_down + delta, max_power)
                self.power = power_up_down * direction
                self.up_down.run(self.power)
                #print("Power ", self.power)

            self.send()
            wait(100)

    def run_targets_(self, target_incoming, target_outcoming):
        angles = self.up_down.angles()
        if angles[0] == target_incoming and angles[1] == target_outcoming:
            print("Already at target!")
            return

        current_incoming = self.levels[self.level_incoming]
        current_outcoming = self.levels[self.level_outcoming]
        interpolator_1, angle2progress_1 = interpolate_target_angles(current_incoming, current_outcoming, target_incoming, target_outcoming, self.position_1)
        interpolator_2, angle2progress_2 = interpolate_target_angles(current_incoming, current_outcoming, target_incoming, target_outcoming, self.position_2)
        
        self.target = 0.0 # progress is 0.0%

        self.run = True
        self.power = 50
        self.send()
        watch = StopWatch()

        max_offset = 0.05
        critical_offset_thresh = 0.02

        current_angle_1, current_angle_2 = self.up_down.angles()

        target_angle_1 = interpolator_1(1)
        target_angle_2 = interpolator_2(1)

        direction_1 = -1 if current_angle_1 > target_angle_1 else 1
        direction_2 = -1 if current_angle_2 > target_angle_2 else 1

        ready2track_targets1, ready2track_targets2 = False, False

        power_up_down1 = 0
        power_up_down2 = 0

        delta = 10

        def mostCriticalAngleOffsets():
            angle_1, angle_2 = self.up_down.angles()
            progress_1, progress_2 = angle2progress_1(angle_1), angle2progress_2(angle_2)
            progress_1 = min(max(0, progress_1), 1)
            progress_2 = min(max(0, progress_2), 1)
            for x in self.remote_motors:
                if x is None:
                    print("Warning None in remote_motors")
                elif len(x) < 4:
                    print("Warning: Weird length of x", x)

            offset_1 = max(progress_1 - x[3] if x else max_offset for x in self.remote_motors, default=0)
            offset_2 = max(progress_2 - x[3] if x else max_offset for x in self.remote_motors, default=0)
            return offset_1, offset_2
                
        power_up_down = 100
        max_power = 900
        self.up_down.run(100 * direction_1, 100 * direction_2)

        def exit():
            self.run = False
            self.up_down.run(0)
            self.target = -1

        while True:
            buttons = self.hub.buttons.pressed()
            if Button.CENTER in buttons:
                exit()
                return
            if self.remote:
                buttons = self.remote_buttons()
                if Button.CENTER in buttons:
                    exit()
                    return

            self.receive()
            critical_offset1, critical_offset2 = mostCriticalAngleOffsets()
            critical_offset = max(critical_offset1, critical_offset2)
            current_angle_1, current_angle_2 = self.up_down.angles()

            progress_1, progress_2 = angle2progress_1(current_angle_1), angle2progress_2(current_angle_2)

            if progress_1 < -0.1 or progress_2 < -0.1:
                raise ValueError('This should never happen!', progress_1, progress_2, current_angle_1, current_angle_2)

            self.target = min(1, max(0, min(progress_1, progress_2) + 0.01)) * PROGRESS_FACTOR

            ready2track_targets_remote = all(abs(1.0 - x[3]) < 0.03 if x else False for x in self.remote_motors)
            error = abs(self.target / PROGRESS_FACTOR - 1)
            if error < 0.005 and (critical_offset1 < critical_offset_thresh and critical_offset2 < critical_offset_thresh):
                self.up_down.track_targets(target_angle_1, target_angle_2, power=300)
                while self.up_down.is_running():
                    wait(100)
                    print('Still a bit running')

                print("Reached target!!", error, critical_offset)
                self.hub.light.on(Color.WHITE)

                self.power = 0
                exit()
                # todo last motor movements?
                return
            elif error < 0.01 or (ready2track_targets1 and ready2track_targets2 and ready2track_targets_remote):
                print("Almost there", error, ready2track_targets1, ready2track_targets2, ready2track_targets_remote, critical_offset1, critical_offset2)
                self.hub.light.blink(Color.GREEN, [50, 50])
                self.up_down.track_targets(target_angle_1, target_angle_2)
                self.target = PROGRESS_FACTOR

                if progress_1 > 0.99:
                    ready2track_targets1 = True
                if progress_2 > 0.99:
                    ready2track_targets2 = True
            else:
                if progress_1 > 0.99:
                    power_up_down1 = 0
                    ready2track_targets1 = True
                elif critical_offset1 >= max_offset:
                    power_up_down1 = 0
                    #self.hub.light.on(Color.RED)
                    print("Stop at angle 1 ", critical_offset1)
                elif critical_offset1 > critical_offset_thresh:
                    power_up_down1 = max(power_up_down1 - 2 * delta, 0)
                    #self.hub.light.on(Color.ORANGE)
                else:
                    #self.hub.light.on(Color.GREEN)
                    power_up_down1 = min(power_up_down1 + delta, max_power)

                if progress_2 > 0.99:
                    power_up_down2 = 0
                    ready2track_targets2 = True
                elif critical_offset2 >= max_offset:
                    power_up_down2 = 0
                    self.hub.light.on(Color.RED)
                    print("Stop at angle 2 ", critical_offset2)
                elif critical_offset2 > critical_offset_thresh:
                    power_up_down2 = max(power_up_down2 - 2 * delta, 0)
                    self.hub.light.on(Color.ORANGE)
                else:
                    self.hub.light.on(Color.GREEN)
                    power_up_down2 = min(power_up_down2 + delta, max_power)

                power1 = power_up_down1 * direction_1
                power2 = power_up_down2 * direction_2
                self.up_down.run(power1, power2)
                print("Power", power1, power2)

            self.send()
            wait(100)

    def wait(self, ms):
        watch = StopWatch()
        while watch.time() < ms:
            self.send()
            wait(100)


    def run_(self):
        watch = None
        manual_elevator_new_target = None
        manual_elevator_new_target_incoming = None
        manual_elevator_new_target_outcoming = None
        requested_target = False
        level_color = None
        remote_center_button_pressed_timer = None

        while True:
            buttons = self.hub.buttons.pressed()




            
            if Button.BLUETOOTH in buttons:
                self.hub.light.animate([Color.BLUE, Color.CYAN, Color.MAGENTA], 300)
                if self.remote is None:
                    self.connect_remote()
                try:
                    self.remote.light.on(Color.CYAN)
                except Exception:
                    self.connect_remote()
                self.hub.light.on(Color.GREEN)

            elif Button.CENTER in buttons:
                self.hub.display.icon(Icon.COUNTERCLOCKWISE)
                self.stop()

            self.receive()
            self.ready = False

            def wait_remote_released():
                self.hub.light.on(Color.GREEN)
                self.hub.display.icon(Icon.TRUE)
                try:
                    while self.remote_buttons():
                        wait(100)
                except Exception:
                    return
                wait(500)

            remote_pressed = []
            if self.remote is not None:
                remote_pressed = self.remote_buttons()
                print("Remote %s" % remote_pressed)
                if Button.CENTER in remote_pressed:
                    if Button.LEFT in remote_pressed:
                        self.remote.light.on(Color.MAGENTA)
                        self.config_mode()
                        wait_remote_released()
                        self.remote.light.on(Color.CYAN)
                        self.hub.display.char(main_state_char[self.main_state])
                    else:
                        # main state changed
                        new_state = next_main_state[self.main_state]
                        self.set_main_state(new_state)
                        self.hub.display.char(main_state_char[new_state])

                        self.set_remote_light(Color.GREEN)
                        if self.main_state_color_matrix:
                            self.main_state_color_matrix.on(Color.GREEN)
                        wait(400)
                        self.set_remote_light(main_state_color[self.main_state])

                        if self.main_state_color_matrix:
                            self.main_state_color_matrix.on(main_state_color[self.main_state])

                        requested_target = False
                        manual_elevator_new_target_incoming = None
                        manual_elevator_new_target_outcoming = None
                        manual_elevator_new_target = None
                        remote_center_button_pressed_timer = None
            

            if self.main_state == MainState.AUTO_ELEVATOR:
                # reduce requests based if a train leaved
                self.requests = [r for r in self.requests if self.switch[r]]

                # add new trains to the requests queue
                is_waiting = self.switch[6:]
                for i, s in enumerate(is_waiting):
                    request = i + 1
                    if s and request not in self.requests and s != self.level_incoming:
                        print("Add request %d" % request)
                        self.requests.append(request)

                if self.state == State.WAIT:
                    if self.outcoming and len(self.outcoming) > 4 and self.outcoming[3]:
                        target = self.outcoming[4]
                        if target != self.level_outcoming:
                            print("Train on elevator wants to go to Level %d" % (target))
                            # check if SWITCH gives ok
                            self.ready = True
                            straight = self.switch[3:6]
                            if any(straight):
                                print("Wait for switch to be closed... ", straight)
                            else:
                                print("All switches to CURVED -> ready to go")
                                self.state = State.DRIVE_WITH
                                print("Drive with train to level %d" % (target))
                                self.run_target(target)

                    elif len(self.requests) > 0:# check if a train is requesting the elevator
                        
                        # start the driving
                        target = self.requests.pop(0)
                        print("Go to %d" % target)
                        
                        if target != self.level_outcoming:
                            self.run_target(target)
                            self.state = State.DRIVE_TO
                        # todo level 2
                        else:
                            print("Already be at %d" % target)
                            self.state = State.WAIT_DRIVE_IN
                            self.watch.reset()

                elif self.state == State.DRIVE_TO:
                    # the train is on the way to a waiting train -> check if the train is still there
                    if not self.up_down.is_running():
                        self.state = State.WAIT_DRIVE_IN
                        self.watch.reset()
                        self.level_incoming = target
                        self.level_outcoming = target
                        print("Reached %d" % target)
                
                if self.state == State.WAIT_DRIVE_IN:
                    # wait until a train drove in (incoming sensor was blocked) or maximum timeout

                    if self.incoming and self.incoming[0]:
                        # train drives in
                        self.watch.reset()
                    elif self.outcoming and self.outcoming[3]:
                        # target is selected
                        target = self.outcoming[4]
                        # check if incoming is free
                        if self.incoming and not self.incoming[0] and self.switch and not self.switch[self.level_incoming + 5]:
                            self.state = State.DRIVE_WITH
                            print("Drive with train to %d" % target)
                            self.run_target(target)
                        else:
                            print("Want to drive but entrance still blocked!")


                    elif self.watch.time() > 10000:
                        self.state = State.WAIT



                elif self.state == State.DRIVE_WITH:
                    # the train is driving with a train

                    # check if the elevator reached its target
                    if not self.up_down.is_running() and self.remote_motors_done():
                        self.state = State.RELEASE
                        self.level_incoming, self.level_outcoming = self.new_level
                        self.new_level = -1

                if self.state == State.RELEASE:
                    # check incoming is not blocked for 3s and was blocked at least once
                    if watch is None:
                        watch = StopWatch()
                        self.hub.light.blink(Color.MAGENTA, [1000, 1000])
                    if self.incoming and self.incoming[1] or watch.time() > 20000:
                        self.state = State.WAIT
                        watch = None
                
                if self.state >= 0:
                    self.hub.display.char(str(self.state))
                print("State %d" % self.state)
            

            elif self.main_state == MainState.MANUAL_ELEVATOR:
                print(manual_elevator_new_target)
                if Button.LEFT_PLUS in remote_pressed:
                    if manual_elevator_new_target is None:
                        manual_elevator_new_target = next_level[self.level_incoming]
                    else:
                        manual_elevator_new_target = next_level[manual_elevator_new_target]
                    print("New manual elevator target %s" % manual_elevator_new_target)
                    wait(200)
                elif Button.LEFT_MINUS in remote_pressed:
                    if manual_elevator_new_target is None:
                        manual_elevator_new_target = prev_level[self.level_incoming]
                    else:
                        manual_elevator_new_target = prev_level[manual_elevator_new_target]
                    print("New manual elevator target %s" % manual_elevator_new_target)
                    wait(200)
                elif Button.RIGHT in remote_pressed and manual_elevator_new_target is not None:
                    # run to new target
                    self.set_remote_light(Color.RED)
                    self.main_state_color_matrix.on(Color.WHITE)
                    requested_target = True
                
                if requested_target:
                    self.ready = True
                    straight = self.switch[3:6]
                    if any(straight):
                        print("Wait for switch to be closed... ", straight)
                    else:
                        self.run_target(manual_elevator_new_target)
                        self.set_remote_light(main_state_color[self.main_state])
                        manual_elevator_new_target = None
                        requested_target = False

                # update main state color matrix
                if self.main_state_color_matrix:
                    if manual_elevator_new_target is not None:  
                        level_color = Level2Color[manual_elevator_new_target]        
                        self.main_state_color_matrix.on(level_color)
                        level_color = None
                    else:
                        self.main_state_color_matrix.on(Color.BLACK)
                    
                    # todo timeout?

            elif self.main_state == MainState.MANUAL_BRIDGE:
                if Button.RIGHT_PLUS in remote_pressed:
                    if manual_elevator_new_target_outcoming is None:
                        manual_elevator_new_target_outcoming = next_level[self.level_outcoming]
                    else:
                        manual_elevator_new_target_outcoming = next_level[manual_elevator_new_target_outcoming]
                    print("New manual elevator target outcoming %s" % manual_elevator_new_target_outcoming)
                    wait(200)
                elif Button.RIGHT_MINUS in remote_pressed:
                    if manual_elevator_new_target_outcoming is None:
                        manual_elevator_new_target_outcoming = prev_level[self.level_outcoming]
                    else:
                        manual_elevator_new_target_outcoming = prev_level[manual_elevator_new_target_outcoming]
                    print("New manual elevator target outcoming %s" % manual_elevator_new_target_outcoming)
                    wait(200)
                elif Button.LEFT_PLUS in remote_pressed:
                    if manual_elevator_new_target_incoming is None:
                        manual_elevator_new_target_incoming = next_level[self.level_incoming]
                    else:
                        manual_elevator_new_target_incoming = next_level[manual_elevator_new_target_incoming]
                    print("New manual elevator target incoming %s" % manual_elevator_new_target_incoming)
                    wait(200)
                elif Button.LEFT_MINUS in remote_pressed:
                    if manual_elevator_new_target_incoming is None:
                        manual_elevator_new_target_incoming = prev_level[self.level_incoming]
                    else:
                        manual_elevator_new_target_incoming = prev_level[manual_elevator_new_target_incoming]
                    print("New manual elevator target incoming %s" % manual_elevator_new_target_incoming)
                    wait(200)
                elif Button.RIGHT in remote_pressed and (manual_elevator_new_target_incoming is not None or manual_elevator_new_target_outcoming is not None):
                    # run to new target
                    self.set_remote_light(Color.RED)
                    self.main_state_color_matrix.on(Color.WHITE)
                    requested_target = True
                
                if requested_target:
                    straight = self.switch[3:6]
                    self.ready = True
                    if any(straight):
                        print("Wait for switch to be closed... ", straight, self.ready)
                    else:
                        manual_elevator_new_target_incoming = manual_elevator_new_target_incoming or self.level_incoming
                        manual_elevator_new_target_outcoming = manual_elevator_new_target_outcoming or self.level_outcoming
                        self.run_target(manual_elevator_new_target_incoming, manual_elevator_new_target_outcoming)
                        self.set_remote_light(main_state_color[self.main_state])
                        manual_elevator_new_target_incoming = None
                        manual_elevator_new_target_outcoming = None
                        requested_target = False

                # update main state color matrix
                if not requested_target and self.main_state_color_matrix:
                    matrix = [Color.BLACK] * 9

                    if manual_elevator_new_target_incoming is not None:      
                        level_color = Level2Color[manual_elevator_new_target_incoming]      
                        matrix[0] = level_color
                        matrix[1] = level_color
                        matrix[2] = level_color

                    if manual_elevator_new_target_outcoming is not None:      
                        level_color = Level2Color[manual_elevator_new_target_outcoming]      
                        matrix[6] = level_color
                        matrix[7] = level_color
                        matrix[8] = level_color

                    self.main_state_color_matrix.on(matrix)


            self.send()
            wait(self.dt)
            

    def stop(self):
        self.run_target(Level.THREE)
        self.hub.system.shutdown()


motor1 = Motor(Port.F, reset_angle=False)
motor2 = Motor(Port.B, reset_angle=False)
motor3 = Motor(Port.E, reset_angle=False)
motor4 = Motor(Port.A, reset_angle=False)
up_down = MotorGroup(motor1, motor2, motor3, motor4)

motors = {
    Port.F: motor1,
    Port.B: motor2,
    Port.E: motor3,
    Port.A: motor4,
}

#CONFIGURATION = [None]

color_matrix = ColorLightMatrix(Port.C)

controller = Controller(up_down, levels, motors=motors, configuration=CONFIGURATION, main_state_color_matrix=color_matrix)
controller.run_()