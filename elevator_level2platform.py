from elevator_utils import Level2Platform, Channel

def run(motor, target, is_incoming):
    if not isinstance(motor, Level2Platform):
        motor = Level2Platform(motor)

    channel = Channel.LEVEL_TWO_INCOMING if is_incoming else Channel.LEVEL_TWO_OUTCOMING
    hub = ThisHub(broadcast_channel=channel, observe_channels=[Channel.MOTOR])
    last_level2platform = False

    while True:
        data = hub.ble.observe(Channel.MOTOR)
        if data is None or len(data) < 10:
            hub.light.on(Color.RED)
        else:
            level2platform = data[8] if is_incoming else data[9] 
            
            
            if last_level2platform != level2platform:
                motor.track_target(target)
                last_level2platform = level2platform

        motor_is_running = motor.speed() > 0

        if motor_is_running:
            hub.light.on(Color.BLUE)
        else:
            hub.light.on(Color.GREEN)


        level2closed = level2platform and not motor_is_running
        level2opened = not level2platform and not motor_is_running
        data.ble.broadcast((level2closed, level2opened, motor_is_running))