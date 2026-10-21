import atexit
import datetime
import time
from os.path import join, dirname, realpath

import can
import cantools
from RPi import GPIO
from can import Listener
from cantools.database import Message

from common.can_classes import primary_ID_TSAC_STATUS, HvStatus, primary_ID_BMS_SET, \
    Toggle  # Depends on handcart-sw repo (libcan-sw messages)
from common.charger.littlesic.LittleSIC import HYC_State, ID_HYC_Status, ID_HYC_Actual
from settings import dbc_primary  # Depends on handcart-sw repo

BYPASS_TSON = False
CHARGING = True
SIMULATION_ENABLED = False  # set to true to enable simulation of processed log

if SIMULATION_ENABLED:
    import pandas
    import scipy
    from matplotlib import pyplot as plt
    from pandas import DataFrame

TARGET_VOLTAGE = 590
SET_CHARGE_A = 10
SET_DISCHARGE_A = -1  # Has to be negative

MIN_TARGET_VOLTAGE = 400
MAX_TARGET_VOLTAGE = 600
MIN_CHARGE_A = 0
MAX_CHARGE_A = 13
MAX_DISCHARGE_A = -20  # MAX has to be negative. It is confusing, I know..
MIN_DISCHARGE_A = 0

SIMULATION_FILENAME = "out.csv"

dataset = [[5, 1]]  # [A, s(time)]

littlesic_dbc_file = join(dirname(realpath(__file__)), "LittleSIC.dbc")
dbc_littlesic = cantools.database.load_file(littlesic_dbc_file)

bus = can.interface.Bus(channel='can0', interface='socketcan')

ts_status = HvStatus.IDLE  # The TS status
is_enabled = False
charger_status: HYC_State = None

# Set GPIO pins
GPIO.setmode(GPIO.BCM)
GPIO.setup(20, GPIO.OUT)  # PON
GPIO.setup(21, GPIO.OUT)  # SD
GPIO.setup(19, GPIO.OUT)  # DISCHARGE RELAY

GPIO.output(19, GPIO.LOW)  # Discharge closed
GPIO.output(21, GPIO.HIGH)  # Enable shutdown relay

if not CHARGING:
    input("WARNING !!!! DISCHARGE MODE ENABLED (press a key to continue)")
    input("Read again: WARNING !!!! DISCHARGE MODE ENABLED (press a key to continue)")


def exit_handler():
    """
    Called whether the program is exiting. It stops the charger and manages shutdown in the proper order. Charger status set to 0x00 > wait 1s > ask TS OFF to bms > open PON relay (remove power to charger)
    """
    global is_enabled

    is_enabled = False
    print("Started quitting procedure")
    print("Setting charger to status 0x00..", end="")
    msg_ctrl.data[0] = 0x00
    task.modify_data(msg_ctrl)
    time.sleep(1)
    print("Done")

    if not BYPASS_TSON:
        print("Asking TS OFF to bms..", end="")
        message_ts_off: cantools.database.can.message = dbc_primary.get_message_by_frame_id(
            primary_ID_BMS_SET)
        data_ts_off = message_ts_off.encode(
            {
                "status": Toggle.OFF.value,
            }
        )
        bms_ts_off = can.Message(arbitration_id=message_ts_off.frame_id,
                                 data=data_ts_off,
                                 is_extended_id=False)

        bus.send(bms_ts_off)
        print("Done")
        time.sleep(.5)

    print("Closing discharge resistor..", end="")
    GPIO.output(19, GPIO.LOW)
    print("Done")

    print("Disabling charger by opeining PON relay..", end="")
    GPIO.output(20, GPIO.LOW)
    print("Done")


atexit.register(exit_handler)  # Register exit handler, it will be called when the program exits


class Can_rx_Listener(Listener):
    def on_message_received(self, msg):
        if msg.arbitration_id == primary_ID_TSAC_STATUS:
            message = dbc_primary.decode_message(msg.arbitration_id, msg.data)
            global ts_status
            ts_status = HvStatus(int(message.get('mainboardStatus').value))

        elif msg.arbitration_id == ID_HYC_Status:
            message = dbc_littlesic.decode_message(msg.arbitration_id, msg.data)
            global charger_status
            charger_status = HYC_State(message.get("status"))

        elif msg.arbitration_id == ID_HYC_Actual:
            global is_enabled
            if is_enabled:
                data = dbc_littlesic.decode_message(msg.arbitration_id, msg.data)
                print(
                    f"Actual: {data.get('uActual'):.2f}V {data.get('iActual'):.2f}A {(data.get('uActual') * data.get('iActual')) / 1000:.3f}W")


# Setup a can listener, which asyncrounously receives messages
l = Can_rx_Listener()
notif = can.Notifier(bus, [l])

# Define control message with idle status
msg_ctrl = can.Message(arbitration_id=0x100,
                       data=[0x00],
                       is_extended_id=False)

# Send periodically the status message
task = bus.send_periodic(msg_ctrl, 0.1)

time.sleep(.2)  # Wait for possible messages




if SIMULATION_ENABLED:
    def print_sim_data_info(dfr: DataFrame):
        duration = dfr["_timestamp"].values[-1]  # seconds
        max_i = dfr["current_interp"].max()
        avg_i = dfr["current_interp"].mean()
        ah = scipy.integrate.simpson(dfr["current_interp"], x=dfr["_timestamp"] / 3600)
        max_power_600 = max_i * 604
        avg_power_600 = avg_i * 604

        print("Simulation info:")
        print(f"Expected duration = {duration:.2f}s = {duration / 60:.2f}minutes")
        print(f"Max set current = {max_i:.2f}A")
        print(f"Average set current = {avg_i:.2f}A")
        print(f"Expected capacity to be discharged = {ah:.2f}Ah")
        print(f"Maximum power discharged = {max_power_600:.1f}W = {max_power_600 / 1000:.1f}kW")
        print(f"Average power discharged = {avg_power_600:.1f}W = {avg_power_600 / 1000:.1f}kW")

    if CHARGING:
        print("script is in CHARGING mode, you cannot simulate, set CHARGING=False")
        exit()

    df = pandas.read_csv(SIMULATION_FILENAME)
    print("WARNING, SIMULATION MODE in DISCHARGE press a key to continue")
    input("")

    # Calclulate sampling interval average over entire dataset. Taking last timestamp over number of points
    interval_csv = round(df["_timestamp"].values[-1] / len(df["_timestamp"].values), 2)
    if interval_csv < 0.1:
        print(f"Error: inverval too low: {interval_csv}")
        exit()

    print_sim_data_info(df)

    input(f"Calculated data sampling from csv is {interval_csv} [seconds], if correct, press a key to continue")

if charger_status is None:
    # If it is None, it didn't receive any message. Maybe it is disabled?
    print("Charger PON seems disabled, enabling PON..", end="")
    GPIO.output(20, GPIO.HIGH)  # PON ON
    print("Done")

time.sleep(2)  # Wait for possible messages

if charger_status == HYC_State.ERROR:
    # If the charger is in error state, reset it by setting 0x01 to the first byte
    # of ctrl message
    print("Charger is in ERROR, trying to reset it..", end="")
    msg_ctrl.data[0] = 0x01
    task.modify_data(msg_ctrl)

    while charger_status == HYC_State.ERROR:
        # Wait for charger to exit ERROR state
        time.sleep(.1)

    print("Done")
    msg_ctrl.data[0] = 0x00  # set control message to OFF
    task.modify_data(msg_ctrl)

print("Opening discharge resistor..", end="")
GPIO.output(19, GPIO.HIGH)
print("Done")

if not BYPASS_TSON:
    # Do TS-ON on accumulator
    input("Press something to do TS-ON")

    m: cantools.database.can.message = dbc_primary.get_message_by_frame_id(primary_ID_BMS_SET)
    data = m.encode(
        {
            "status": Toggle.ON.value,
        }
    )
    bms_ts_on = can.Message(arbitration_id=m.frame_id,
                            data=data,
                            is_extended_id=False)

    bus.send(bms_ts_on)
    bus.send(bms_ts_on)
    bus.send(bms_ts_on)
    bus.send(bms_ts_on)
    bus.send(bms_ts_on)

    print("Waiting for precharge..", end="")

    while not ts_status == HvStatus.TS_ON:
        time.sleep(0.1)

    print("Done")
else:
    print("BYPASS TS ON is enabled. Not doing TS ON nor checking if TS ON")

input(f"Press a key to start {'charging' if CHARGING else 'discharging'}")


def get_target_data(discharge_a=SET_DISCHARGE_A):
    m: Message = dbc_littlesic.get_message_by_name("HYC_Target")

    if not (MIN_TARGET_VOLTAGE <= TARGET_VOLTAGE <= MAX_TARGET_VOLTAGE):
        print(f"Target V out of range : {TARGET_VOLTAGE}")
        exit()

    if CHARGING:
        if not (MIN_CHARGE_A <= SET_CHARGE_A <= MAX_CHARGE_A):
            print(f"Max charge current out of range : {SET_CHARGE_A}")
            exit()
        data = m.encode({
            "uTarget": TARGET_VOLTAGE,
            "iTarget": SET_CHARGE_A
        })
    else:
        if not (MAX_DISCHARGE_A <= discharge_a <= MIN_DISCHARGE_A):
            print(f"Max discharge current out of range : {discharge_a}")
            exit()
        else:
            data = m.encode({
                "uTarget": TARGET_VOLTAGE,
                "iTarget": discharge_a
            })

    return data


if True:
    data = get_target_data()

    m: Message = dbc_littlesic.get_message_by_name("HYC_Target")
    msg_target = can.Message(arbitration_id=m.frame_id,
                             data=data,
                             is_extended_id=False)

    task_target = bus.send_periodic(msg_target, 1)

if True:
    # Start charge (or discharge)
    msg_ctrl.data[0] = 0x02 if CHARGING else 0x04
    task.modify_data(msg_ctrl)
    is_enabled = True

print(f"{'Charging' if CHARGING else 'Discharging'}.. "
      f"target V: {TARGET_VOLTAGE}, "
      f"max A: {SET_CHARGE_A if CHARGING else SET_DISCHARGE_A}")

if True:
    # Set fan speed if needed
    m: Message = dbc_littlesic.get_message_by_name("HYC_Alive")

    data = m.encode({
        "AliveCnt": 0,
        "fanMin": 50,
        "fanMax": 100
    })

    msg_fan = can.Message(arbitration_id=m.frame_id,
                          data=data,
                          is_extended_id=False)

    task_fan = bus.send_periodic(msg_fan, 0.1)


def simulate_data():
    plt.ion()
    fig, ax = plt.subplots()
    line, = ax.step(df["_timestamp"], df["current_interp"], where="post", label="set current")

    df["progress"] = [0.0 for i in range(len(df))]
    line2, = ax.step(df["_timestamp"], df["progress"], where="post", label="charger current")
    plt.legend()
    plt.show()

    t_start = datetime.datetime.now().timestamp()
    t_next = t_start
    t_now = t_start

    for index, value in enumerate(df["_timestamp"].values):
        while t_now <= t_next:
            time.sleep(.0001)
            t_now = datetime.datetime.now().timestamp()

        i_set = -float(df["current_interp"].values[index])
        # Update target message of the charger
        d = get_target_data(discharge_a=i_set)

        m: Message = dbc_littlesic.get_message_by_name("HYC_Target")
        msg_target = can.Message(arbitration_id=m.frame_id,
                                 data=d,
                                 is_extended_id=False)

        task_target.modify_data(msg_target)

        df["progress"].values[index] = df["current_interp"].values[index]
        line2.set_ydata(df["progress"])
        plt.draw()
        # print(f"now: {t_now}\tcalc: {t_next}\tdiff:{t_next - t_now:.4f}")
        print(f"I_SET={i_set:.2f}\tt_diff:{t_next - t_now:.4f}")
        plt.pause(.0001)
        t_next = t_start + float(value)


if SIMULATION_ENABLED:
    simulate_data()
else:
    while 1:
        time.sleep(0.1)
        pass
