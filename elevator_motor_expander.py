from elevator_utils import *
from pybricks.hubs import ThisHub
from pybricks.parameters import Color, Port
from pybricks.pupdevices import Motor
from pybricks.tools import wait

def run(channel, colors, ports, level2_platform=None, is_incoming=False, is_outcoming=False, configuration=CONFIGURATION):
    hub = ThisHub(broadcast_channel=channel, observe_channels=[Channel.MOTOR])
    bottom_left = Motor(ports[0])
    up_left = Motor(ports[1])
    up_right = Motor(ports[2])
    bottom_right = Motor(ports[3])
    motors = MotorGroup(bottom_left, up_left, up_right, bottom_right)
    level = Level.THREE
    new_level_incoming = Level.THREE
    new_level_outcoming = Level.THREE
    error = False
    running = False
    running_power = 0
    old_level2_incoming = False
    old_level2_outcoming = False
    print(configuration)
    print(channel)
    group = configuration.index(channel)
    n = 2 * len(configuration) - 1
    position_2 = 2 * group / n
    position_1 = (2 * group + 1) / n

    #n = len(configuration)
    #configuration = [c for c in configuration if c != channel]
    
    interpolator_1 = None
    interpolator_2 = None
    angle2progress_1 = None
    angle2progress_2 = None
    is_bridge = False
    target_angle_incoming = None
    target_angle_outcoming = None

    if level2_platform and not isinstance(level2_platform, Level2Platform):
        level2_platform = Level2Platform(level2_platform)

    while True:

        observed = hub.ble.observe(Channel.MOTOR)
        print(observed)

        if observed is None:
            # error
            hub.light.on(Color.RED)
            wait(200)
            error = True
            running = False
            running_power = 0
            motors.run(0) # todo better reset!
            continue


        if len(observed) == 10:
            # usual run mode
            hub.light.on(Color.GREEN)

            level = observed[0]
            level_incoming, level_outcoming = decode_levels(level)


            new_level = observed[3]
            if new_level != -1:
                print('Decoding', new_level, level)
                new_level_incoming, new_level_outcoming = decode_levels(new_level)
                if is_incoming:
                    new_level = new_level_incoming
                else:
                    new_level = new_level_outcoming

            angle = observed[5]
            power = observed[6]
            run = observed[7]
            level2_incoming = observed[8]
            level2_outcoming = observed[9]

            print('Going from ', level_incoming, level_outcoming, new_level_incoming, new_level_outcoming)
            if level_incoming == new_level_incoming and level_outcoming == new_level_outcoming:
                print('Already there')
                wait(2000)

                pass
            elif level_incoming == level_outcoming and new_level_incoming == new_level_outcoming:
                is_bridge = False
                if run and angle != motors.angle():
                    motors.track_target(angle)
                else:
                    level = new_level
                    print("Set new level %s" % level)
                    wait(1000)
                    motors.stop()

            else:
                is_bridge = True
                # angle is progress probability (int, *10000)
                # calculate angles for both motor sub groups
                progress = min(angle / PROGRESS_FACTOR + 0.01, 1.0)
                

                if True or interpolator_1 is None:
                    print('Create a new interpolator', level_incoming, level_outcoming, new_level_incoming, new_level_outcoming, position_1, position_2)
  
                    start_angle_incoming = levels[level_incoming]
                    start_angle_outcoming = levels[level_outcoming]

                    target_angle_incoming = levels[new_level_incoming]
                    target_angle_outcoming = levels[new_level_outcoming]

                    interpolator_1, angle2progress_1 = interpolate_target_angles(start_angle_incoming, start_angle_outcoming, target_angle_incoming, target_angle_outcoming, position_1)
                    interpolator_2, angle2progress_2 = interpolate_target_angles(start_angle_incoming, start_angle_outcoming, target_angle_incoming, target_angle_outcoming, position_2)                            


                motor_angle_1, motor_angle_2 = motors.angles()
                progress_1 = angle2progress_1(motor_angle_1)
                progress_2 = angle2progress_2(motor_angle_2)
                error = max(abs(1.0 - p) for p in [progress_1, progress_2])

                print("Running to progress ", progress_1, progress_2, 'error', error)

                if run and progress != -1 and (progress < 1.0 or error > 0.001):
 
                    angle_1 = interpolator_1(progress)
                    angle_2 = interpolator_2(progress)
                    print('Tracking target', angle_1, angle_2)
                    motors.track_targets(angle_1, angle_2)

                else:
                 #   interpolator_1, interpolator_2, angle2progress_1, angle2progress_2 = None, None, None, None
                    level = new_level
                    print("Set new level %s" % level, 'run', run, progress, error, target_angle_incoming, target_angle_outcoming)
                    wait(1000)
                    motors.stop()

            if level2_platform:
                if is_incoming:
                    if level2_incoming and not old_level2_incoming:
                        print('Extend Level 2 Incoming')
                        level2_platform.extend()                    
                    elif not level2_incoming and old_level2_incoming:
                        level2_platform.contract()
                        print('Contract Level 2 Incoming')
                    old_level2_incoming = level2_incoming
                elif is_outcoming:
                    if level2_outcoming and not old_level2_outcoming:
                        level2_platform.extend()     
                        print('Extend Level 2 Outcoming')               
                    elif not level2_outcoming and old_level2_outcoming:
                        level2_platform.contract()
                        print('Contract Level 2 Outcoming') 
                    old_level2_outcoming = level2_outcoming

        elif len(observed) == 3:
            # config mode
            mode = observed[0] # int
            speed = observed[1] # int
            count = observed[2] # int

            if mode == 0:
                # all motors move
                motors.run(speed)
                hub.light.on(Color.WHITE)
            elif mode == 1:
                # each motor individual
                if count == 4 * group:
                    # bottom right
                    hub.light.on(colors[1])
                    run_motor(bottom_right, speed)
                elif count == 4 * group + 1:
                    # upper right
                    hub.light.on(colors[1])
                    run_motor(up_right, speed)
                elif count == 4 * group + 2:
                    # bottom left
                    hub.light.on(colors[0])
                    run_motor(bottom_left, speed)
                elif count == 4 * group + 3:
                    # upper left
                    hub.light.on(colors[0])
                    run_motor(up_left, speed)
                else:
                    motors.run(0)
                    hub.light.on(Color.BLACK)
            elif mode == 2:
                # each group individual
                if count == group:
                    motors.run(speed)
                else:
                    motors.run(0)
            elif mode == 3:
                motors.run(0)
        elif len(observed) == 1:
            hub.light.blink(Color.WHITE, [400, 400])
            motors.run(100)
            wait(100)
            while not motors.load(1):
                print("up")
                hub.ble.broadcast((False, ))
                wait(100)

            motors.run(-100)
            wait(100)
            while motors.load(-1):
                print("down")
                hub.ble.broadcast((False, ))
                wait(100)
            motors.run(0)

            # wait that MOTOR is finished
            hub.light.blink(Color.MAGENTA, [500, 500])
            while True:
                hub.ble.broadcast((True, ))
                wait(100)
                observed = hub.ble.observe(Channel.MOTOR)
                if observed and ((len(observed) == 1 and observed[0]) or len(observed) > 1):
                    break

            hub.light.blink(Color.GREEN, [500, 500])
            # wait that MOTOR is in another mode
            while len(observed) == 1:
                wait(100)
                observed = hub.ble.observe(Channel.MOTOR)
                if not observed:
                    observed = [None]
            motors.reset_angle(INIT_ANGLE)
            hub.light.blink(Color.CYAN, [500, 500])
            print("Finished reset")


        if is_bridge:
            angle_1, angle_2 = motors.angles()
            if angle2progress_1 is not None:
                progress_1 = angle2progress_1(angle_1)
                progress_2 = angle2progress_2(angle_2)
                angle = min(1.0, max(0.0, min(progress_1, progress_2)))

            else:
                progress = -1
        else:
            angle = int(motors.angle())
        hub.ble.broadcast((True, motors.done(), level, angle))
        wait(100)

motor_ports = [Port.F, Port.B,  Port.E, Port.A]
#run(Channel.MOTOR_OUTCOMING, [Color.GRAY, Color.RED], ports=motor_ports, level2_platform=Motor(Port.D), is_outcoming=True)
run(Channel.MOTOR_INCOMING, [Color.BLUE, Color.YELLOW], ports=motor_ports, level2_platform=Motor(Port.C), is_incoming=True)
# todo invert level 2 platform Power for incoming!
