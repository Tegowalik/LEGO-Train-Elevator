from pybricks.parameters import Port, Stop, Icon, Color, Button
from pybricks.pupdevices import Motor, ColorDistanceSensor
from pybricks.hubs import ThisHub
from pybricks.tools import wait
from elevator_utils import enum, Level, Channel, decode_levels

# sends if train requests elevator
# receives whether to move motor to elevator

# SwitchPosition.STRAIGHT means a train would pass the switch in the straight direction
# SwitchPosition.CURVED means a train would pass the switch in the curved direction (either left or right)
SwitchPosition = enum(STRAIGHT=1, CURVED=2)

#initial position curved
class SwitchUnit:

    def __init__(self, sensor_port: Port, motor_port: Port, critical_distance=40):
        self.sensor = ColorDistanceSensor(port=sensor_port)
        self.motor = Motor(port=motor_port)
        self.critical_distance = critical_distance
        self.switch_position = SwitchPosition.CURVED
        self.power = 750
        self.stop_mode = Stop.COAST
        self.calibrate()
        self.move(SwitchPosition.CURVED)
        self.states = []
        self.o = False
        self.o_states = []
        

    def calibrate(self):
        self.motor.reset_angle(0)
        angle1 = self.motor.run_until_stalled(self.power / 5)
        angle2 = self.motor.run_until_stalled(-self.power / 5)

        # move angles a little bit towards each other
        diff = angle1 - angle2
        if diff > 100:
            angle1 = int(angle1 - diff / 5)
            angle2 = int(angle2 + diff / 5)

        other_switch_position = self.other_switch_position(self.switch_position)
        if angle1 < -angle2:
            self.motor.run_target(self.power, angle1, then=self.stop_mode)
            self.angle = {self.switch_position: angle1, other_switch_position: angle2}
        else:
            self.motor.run_target(self.power, angle2, then=self.stop_mode)
            self.angle = {self.switch_position: angle2, other_switch_position: angle1}
        self.motor.stop()

    def move(self, goal_position: SwitchPosition):
        angle = self.angle[goal_position]
        self.motor.run_target(self.power, angle, then=self.stop_mode, wait=True)
        self.switch_position = goal_position

    def other_switch_position(self, position):
        return SwitchPosition.STRAIGHT if position == SwitchPosition.CURVED else SwitchPosition.CURVED
   
    def stop(self):
        self.move(SwitchPosition.CURVED, then=self.stop)

    def state(self):
        s = self.sensor.distance() < self.critical_distance
        if len(self.states) < 10:
            self.states.append(s)
        else:
            self.states = self.states[1:] + [s]
        return s

    def state_stable(self): # todo average
        return any(self.states)

    def is_waiting(self):
        return all(self.states) and not any(self.o_states) and self.switch_position == SwitchPosition.CURVED

    def can_close(self):
        return not any(self.o_states)# no train in front of remote sensors

    def update(self, o):
        self.o = o
        if len(self.o_states) == 25:
            self.o_states = self.o_states[1:] + [o]
        else:
            self.o_states.append(o)


class Controller:

    def __init__(self, dt=100):
        self.units = {}
        self.dt = dt
        self.hub = ThisHub(observe_channels=[Channel.MOTOR, Channel.SWITCH_SENSOR], broadcast_channel=Channel.SWITCH)
        self.hub.system.set_stop_button(None)
        self.level = None # current incoming elevator level

    def add_unit(self, level: Level, unit: SwitchUnit):
        self.units[level] = unit

    def units_iterator(self):
        return sorted(self.units.items(), key=lambda x: x[0])

    def run(self):
        print("Start")
        while True:
            if Button.CENTER in self.hub.buttons.pressed():
                self.stop()

            observed, observed_switch = self.receive()

            states = []
            print("S", observed_switch)
            if observed_switch:
                for o, (l, u) in zip(observed_switch, self.units_iterator()):
                    u.update(o)
                    u.state()
            else:
                print("Have not observed from switch!")
                for unit in self.units.values():
                    unit.state() # tick 

            if observed and len(observed) > 4:
                self.level = decode_levels(observed[0])[0]
                ready2Move = observed[4]
            
                print(self.level, ready2Move)


                if ready2Move:
                    self._move_to_curved()
                    for l, unit in self.units_iterator():
                        states.append(unit.state_stable())
                else:
                    for l, unit in self.units_iterator():
                        if l == self.level:
                            position = SwitchPosition.STRAIGHT
                        else:
                            # if level is not selected (or nothing is received the trains are directed to the backup track)
                            position = SwitchPosition.CURVED
                        #print(unit.switch_position, position)
                        if unit.switch_position != position and not unit.o:
                            print("MOVE")
                            print(unit.switch_position)
                            unit.move(position)

                        state = unit.state_stable()
                        states.append(state)
    
                states += [unit.switch_position == SwitchPosition.STRAIGHT for _, unit in self.units_iterator()]
                states += [unit.is_waiting() for _, unit in self.units_iterator()]
                #print(states)
                self.send(states)
            else:
                # try to move motor to CURVED if possible
                self._move_to_curved()

            self.update_display()
            wait(self.dt)

    def _move_to_curved(self):
        print("Move to curved")
        for level, unit in self.units_iterator():
            can_close = unit.can_close()
            pos = unit.switch_position != SwitchPosition.CURVED
            print('Can close', can_close, 'pos', pos)
            if can_close and pos:
                unit.move(SwitchPosition.CURVED)
        wait(2000)

    def update_display(self):
        # or just update for Level.TWO
        if self.units[Level.TWO].switch_position == SwitchPosition.CURVED:
            self.hub.display.icon(Icon.ARROW_LEFT)
        else:
            self.hub.display.icon(Icon.ARROW_UP)

    def send(self, states):
        self.hub.ble.broadcast(states)

    def receive(self):
        return self.hub.ble.observe(Channel.MOTOR), self.hub.ble.observe(Channel.SWITCH_SENSOR)

    def stop(self):
        self.hub.light.on(Color.RED)
        while not all(unit.switch_position == SwitchPosition.CURVED for unit in self.units.values()):
            self._move_to_curved()
        self.hub.system.shutdown()

controller = Controller(dt=100)
unit1 = SwitchUnit(sensor_port=Port.F, motor_port=Port.E)
unit2 = SwitchUnit(sensor_port=Port.D, motor_port=Port.C)
unit3 = SwitchUnit(sensor_port=Port.B, motor_port=Port.A)

controller.add_unit(Level.ONE, unit1)
controller.add_unit(Level.TWO, unit2)
controller.add_unit(Level.THREE, unit3)

controller.run()