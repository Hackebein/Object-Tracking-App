import json
import math
import re
import numpy
import openvr
import sys
import os
import time
import traceback
import ctypes
import argparse
import zeroconf
from pythonosc import udp_client, dispatcher, osc_server
from tinyoscquery.queryservice import OSCQueryService
from tinyoscquery.utility import get_open_tcp_port, get_open_udp_port
from tinyoscquery.query import OSCQueryBrowser, OSCQueryClient
from psutil import process_iter
from threading import Thread
from scipy.spatial.transform import Rotation


# TODO: code style
def get_absolute_path(relative_path) -> str:
    """
    Gets absolute path from relative path
    Parameters:
        relative_path (str): Relative path
    Returns:
        str: Absolute path
    """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def send_desktop_notification(title: str, message: str) -> None:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, title, message, 0)


def cls() -> None:
    """
    Clears Console.
    Returns:
        None
    """
    os.system('cls' if os.name == 'nt' else 'clear')


def set_title(title: str) -> None:
    if os.name == 'nt':
        ctypes.windll.kernel32.SetConsoleTitleW(title)


def is_running() -> bool:
    """
    Checks if VRChat is running.
    Returns:
        bool: True if VRChat is running, False if not
    """
    _proc_name = "VRChat.exe" if os.name == 'nt' else "VRChat"
    return _proc_name in (p.name() for p in process_iter())


def stop() -> None:
    """
    Stops the program.
    Returns:
        None
    """
    try:
        openvr.shutdown()
    except Exception as e:
        print("Error shutting down OVR: " + str(e))

    if oscQueryServer:
        oscQueryServer.shutdown()
    # if oscqs:
    #    oscqs.stop()
    sys.exit()


def wait_get_oscquery_client() -> OSCQueryClient:
    """
    Waits for VRChat to be discovered and ready and returns the OSCQueryClient.
    Returns:
        OSCQueryClient: OSCQueryClient for VRChat
    """
    service_info = None
    print("Waiting for VRChat Client to be discovered ...")
    while service_info is None:
        browser = OSCQueryBrowser()
        time.sleep(1)  # Wait for discovery
        service_info = browser.find_service_by_name("VRChat")
    print("Connecting to VRChat Client ...")
    client = OSCQueryClient(service_info)
    print("Waiting for VRChat Avatar to be ready ...")
    while client.query_node(AVATAR_CHANGE_PARAMETER) is None:
        time.sleep(1)
    print("Connected to VRChat Client successful!")
    return client


def wait_get_oscquery_server() -> osc_server.ThreadingOSCUDPServer:
    print("Starting OSCquery Server ...")
    disp = dispatcher.Dispatcher()
    disp.set_default_handler(osc_message_handler)
    server = osc_server.ThreadingOSCUDPServer((IP, SERVER_PORT), disp)
    Thread(target=server.serve_forever, daemon=True).start()
    print("Announcing Server as HackOSC ...")
    OSCQueryService("HackOSC", HTTP_PORT, SERVER_PORT).advertise_endpoint(AVATAR_CHANGE_PARAMETER)
    return server
    

def send_parameter(parameter: str, value) -> None:
    """
    Sends a parameter to VRChat via OSC.
    Parameters:
        parameter (str): Name of the parameter
        value (any): Value of the parameter
    Returns:
        None
    """
    #print(f"Sending {parameter} = {value} ({type(value)})")
    debug_osc_message_out(AVATAR_PARAMETERS_PREFIX + parameter, value)
    oscClient.send_message(AVATAR_PARAMETERS_PREFIX + parameter, value)


def send_ot_float_local(name: str, axe: str, accuracy: int, value: float):
    """Sends a local float"""
    # TODO: support accuracy
    value = clamp(value, 0)
    send_parameter(f"ObjectTracking/{name}/L{axe}", value)


def send_ot_float_remote(name: str, axe: str, accuracy: int, value: float):
    """Sends a remote float"""
    # int for 8 bits
    # bool for 1 bit
    value = clamp(value, 0)
    value_bin = round(value * (2**accuracy-1))
    accuracy_bytes, accuracy_bits = divmod(accuracy, 8)
    for i in range(accuracy_bytes):
        value_bin, byte = divmod(value_bin, 2**8)
        send_parameter(f"ObjectTracking/{name}/R{axe}-Byte{i}", byte)
    for i in range(accuracy_bits):
        value_bin, bit = divmod(value_bin, 2**1)
        send_parameter(f"ObjectTracking/{name}/R{axe}-Bit{i}", bit)


def debug_osc_message_in(addr, value) -> None:
    if "/" in addr.removeprefix(AVATAR_PARAMETERS_PREFIX) and not addr.removeprefix(AVATAR_PARAMETERS_PREFIX).startswith("ObjectTracking/LHR-"):
        print(f"< {addr}: {value}")
    pass


def debug_osc_message_out(addr, value) -> None:
    #print(f"> {addr}: {value}")
    pass


def set_parameter(parameter: str, value) -> None:
    """
    Caches a parameter.
    Parameters:
        parameter (str): Name of the parameter
        value (any): Value of the parameter
    Returns:
        None
    """
    global parameters
    parameters[parameter] = value


def get_parameter(parameter: str, fallback):
    """
    Caches a parameter.
    Parameters:
        parameter (str): Name of the parameter
        fallback (any): Fallback value
    Returns:
        Any
    """
    global parameters
    return parameters.get(parameter, fallback)


def on_avatar_change(addr, value) -> None:
    """
    Resets all parameters and trackers when the avatar changes.
    Parameters:
        parameter (str): Name of the parameter
        value (any): Value of the parameter
    Returns:
        None
    """
    parameters = {}
    trackers = {}


def osc_message_handler(addr, value) -> None:
    """
    Handles OSC messages.
    Parameters:
        addr (str): Address of the message
        value (any): Value of the message
    Returns:
        None
    """
    debug_osc_message_in(addr, value)
    parameter = addr.removeprefix(AVATAR_PARAMETERS_PREFIX)
    if addr == AVATAR_CHANGE_PARAMETER:
        on_avatar_change(addr, value)
    set_parameter(parameter, value)
    if parameter == "ObjectTracking/config/index" and value != 0:
        device = get_parameter("ObjectTracking/config/device", 0)
        index = value
        new = get_parameter("ObjectTracking/config/value", 0)
        old = None
        if trackers.get(device, None) is None:
            trackers[device] = {}
        if trackers[device].get(index, None) is not None:
            old = trackers[device][index]
        if old != new:
            print(f"{device}[{index}] {old} => {new}")
        trackers[device][index] = new
    if re.match(r"ObjectTracking/config/(?!index|value)", parameter) and value > 0:
        set_parameter("ObjectTracking/config/device", parameter.removeprefix("ObjectTracking/config/"))
    if parameter == "ObjectTracking/isStabilized" and value:
        oscClient.send_message("/input/Vertical", 0.0)
    if parameter == "ObjectTracking/goStabilized" and value:
        oscClient.send_message("/input/Vertical", 1.0)


def clamp(n, minn=-1, maxn=1):
    """Clamps a value between a minimum and maximum value"""
    return max(min(maxn, n), minn)


def remap(x: float, in_min: float, in_max: float, out_min: float, out_max: float) -> float:
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


def ovr_pose_to_osc_pose(ovr, relative=False):
    """Converts OpenVR pose to OSC pose"""
    ovr = numpy.array(list(ovr))

    # position
    x, y, z = ovr[0:3, 3]
    x = float(x)
    y = float(y)
    z = float(z)

    # rotation
    # TODO: research (Transform.rotationOrder) this could have changed to XYZ by end of unity 2019???
    pitch, roll, yaw = Rotation.from_matrix(ovr[0:3, 0:3]).as_euler("YXZ")
    roll = float(-roll / math.pi)  # value range: -0.5 - 0.5
    pitch = float(-pitch / math.pi)  # value range: -1.0 - 1.0
    yaw = float(yaw / math.pi)  # value range: -1.0 - 1.0
    
    if relative:
        x, y, z, roll, pitch, yaw = (
            (numpy.array([x, y, z, roll, pitch, yaw]) - numpy.array(playspace_center))
            -
            (numpy.array(avatar_root) - numpy.array(playspace_center))
        ).tolist()
        x, z = rotate((0, 0), (x, z), math.radians(avatar_root[4]))

    return (x, y, z, roll, pitch, yaw)


def debug_position(name, px, py, pz, rx, ry, rz):
    """Prints a position and rotation to the console"""
    print(f"{name}: px: {round(px, 3)}m, py: {round(py, 3)}m, pz: {round(pz, 3)}m, rx: {round(rx, 2)}, ry: {round(ry, 2)}, rz: {round(rz, 2)}")


def rotate(origin, point, angle):
    """
    Rotate a point counterclockwise by a given angle around a given origin.

    The angle should be given in radians.
    """
    ox, oy = origin
    px, py = point

    qx = ox + math.cos(angle) * (px - ox) - math.sin(angle) * (py - oy)
    qy = oy + math.sin(angle) * (px - ox) + math.cos(angle) * (py - oy)
    return qx, qy


# Argument Parser
parser = argparse.ArgumentParser(
    description='ObjectTracking: OpenVR tracking data to VRChat via OSC.')
parser.add_argument('-d', '--debug', required=False, action='store_true', help='prints values for debugging')
parser.add_argument('-i', '--ip', required=False, type=str, help="set OSC ip. Default=127.0.0.1")
parser.add_argument('-p', '--port', required=False, type=str, help="set OSC port. Default=9000")
args = parser.parse_args()

first_launch_file = get_absolute_path("first_launch")
config_path = get_absolute_path("config.json")
manifest_path = get_absolute_path("app.vrmanifest")
application = openvr.init(openvr.VRApplication_Utility)
openvr.VRInput().setActionManifestPath(config_path)
openvr.VRApplications().addApplicationManifest(manifest_path)
if os.path.isfile(first_launch_file):
    openvr.VRApplications().setApplicationAutoLaunch("Hackebein.ObjectTracking", True)
    os.remove(first_launch_file)

config = json.load(open(config_path))
trackers = {}
#trackers = {
#    'global': {1: 1},
#    'LHR-32E2511E': {1: 9, 2: 8, 3: 9, 4: 7, 5: 7, 6: 7, 7: -6, 8: -6, 9: -6, 10: -180, 11: -180, 12: -180, 13: -5, 14: 0, 15: -5, 16: -180, 17: -180, 18: -180, 19: 6, 20: 6, 21: 6, 22: 180, 23: 180, 24: 180, 25: 5, 26: 5, 27: 5, 28: 180, 29: 180, 30: 180},
#}
parameters = {}

IP = args.ip if args.ip else config["IP"]
PORT = int(args.port if args.port else config["Port"])
SERVER_PORT = int(config["Server_Port"] if config["Server_Port"] > 0 else get_open_udp_port())
HTTP_PORT = int(config["HTTP_Port"] if config["HTTP_Port"] > 0 else get_open_tcp_port())
UPDATEINTERVAL = 1 / float(config['UpdateRate'])
AVATAR_PARAMETERS_PREFIX = "/avatar/parameters/"
AVATAR_CHANGE_PARAMETER = "/avatar/change"
TITLE="ObjectTracking v0.0.0" + (" (Debug)" if args.debug else "")

set_title(TITLE)
print(TITLE)
print(f" IP: {IP}")
print(f" Port: {PORT}")
print(f" Server Port: {SERVER_PORT}")
print(f" HTTP Port: {HTTP_PORT}")
print(f" Update Rate: {config['UpdateRate']}Hz / Update Interval: {UPDATEINTERVAL * 1000:.2f}ms")
print("")

playspace_center = [.0, .0, .0, .0, .0, .0]
avatar_root = [.0, .0, .0, .0, .0, .0]
try:
    print("Waiting for VRChat Client to start ...")
    while not is_running():  # TODO: check consistently for this
        time.sleep(1)
    print(f"Waiting for OSCClient({IP}:{PORT}) to start ...")
    oscClient = udp_client.SimpleUDPClient(IP, PORT)
    
    print("Waiting for OSCQueryClient to connect to VRChat Client...")
    oscQueryClient = wait_get_oscquery_client()
    
    print("Waiting for OSCQueryServer to start ...")
    oscQueryServer = wait_get_oscquery_server()
    
    print("Init complete!")
    cycle_start_time = time.perf_counter()
    while True:
        wait_time = UPDATEINTERVAL - (time.perf_counter() - cycle_start_time)
        if wait_time > 0:
            if wait_time / UPDATEINTERVAL < 0.1:
                print(f"Warning: about {wait_time / UPDATEINTERVAL * 100:.0f}% frame time left, consider decreasing UpdateRate")
            time.sleep(wait_time)
        else:
            print(f"Warning: {abs(wait_time * 1000):.2f}ms behind schedule, decreasing UpdateRate recommended")
        cycle_start_time = time.perf_counter()
        tracking_reference_positions = {"PX": [], "PY": [], "PZ": [], "RX": [], "RY": [], "RZ": []}
        devices = application.getDeviceToAbsoluteTrackingPose(
            openvr.TrackingUniverseStanding, 0, openvr.k_unMaxTrackedDeviceCount)
        try:
            for i in range(openvr.k_unMaxTrackedDeviceCount):
                if not devices[i].bPoseIsValid:
                    continue
                if devices[i].eTrackingResult != openvr.TrackingResult_Running_OK:
                    continue
                if (application.getTrackedDeviceClass(i) == openvr.TrackedDeviceClass_TrackingReference):
                    px, py, pz, rx, ry, rz = ovr_pose_to_osc_pose(devices[i].mDeviceToAbsoluteTracking)
                    # debug_position(f"Basestation {device_name}", px, py, pz, rx, ry, rz)
                    tracking_reference_positions["PX"].append(px)
                    # tracking_reference_positions["PY"].append(0)
                    tracking_reference_positions["PZ"].append(pz)
                    # tracking_reference_positions["RX"].append(0)
                    # tracking_reference_positions["RY"].append(0)
                    # tracking_reference_positions["RZ"].append(0)
            playspace_center = [sum(values) / len(values) if len(values) else 0 for key, values in tracking_reference_positions.items()]
            # vielleicheicht v und ^ zusammen legen als generelle offset position für ein object?
            for i in range(openvr.k_unMaxTrackedDeviceCount):
                if not devices[i].bPoseIsValid:
                    continue
                if devices[i].eTrackingResult != openvr.TrackingResult_Running_OK:
                    continue
                if (application.getTrackedDeviceClass(i) == openvr.TrackedDeviceClass_HMD):
                    px, py, pz, rx, ry, rz = (numpy.array(ovr_pose_to_osc_pose(devices[i].mDeviceToAbsoluteTracking)) - numpy.array(playspace_center)).tolist()
                    #debug_position(f"HMD", px, py, pz, rx, ry, rz)
                    if get_parameter("VelocityZ", 0) > 0:
                        avatar_root[4] = ry
                    if not get_parameter("ObjectTracking/isStabilized", False):
                        avatar_root[3] = rx
                        avatar_root[5] = rz
            for i in range(openvr.k_unMaxTrackedDeviceCount):
                if not devices[i].bPoseIsValid:
                    continue
                if devices[i].eTrackingResult != openvr.TrackingResult_Running_OK:
                    continue
                device_name = application.getStringTrackedDeviceProperty(i, openvr.Prop_SerialNumber_String)
                if device_name not in trackers:
                    continue
                tracker = trackers[device_name]
                px, py, pz, rx, ry, rz = ovr_pose_to_osc_pose(devices[i].mDeviceToAbsoluteTracking, True)
                #debug_position(f"{device_name} (world)", px, py, pz, rx, ry, rz)
                #px, py, pz, rx, ry, rz = (
                #    (numpy.array([px, py, pz, rx, ry, rz]) - numpy.array(playspace_center))
                #    -
                #    (numpy.array(avatar_root) - numpy.array(playspace_center))
                #).tolist()
                #debug_position(f"{device_name} (local1)", px, py, pz, rx, ry, rz)
                #print(avatar_root[4])
                #px, pz = rotate((0, 0), (px, pz), math.radians(avatar_root[4]))
                #debug_position(f"{device_name} (local2)", px, py, pz, rx, ry, rz)

                offset = 0
                value_local = remap(px, tracker[7 + offset], tracker[19 + offset], 0, 1)
                value_remote = remap(px, tracker[13 + offset], tracker[25 + offset], 0, 1)
                axe = "PX"
                # print(f"{device_name} {axe} {value_local} {value_remote}")
                send_ot_float_local(device_name, axe, 32, value_local)
                send_ot_float_remote(device_name, axe, tracker[1 + offset], value_remote)

                offset += 1
                value_local = remap(py, tracker[7 + offset], tracker[19 + offset], 0, 1)
                value_remote = remap(py, tracker[13 + offset], tracker[25 + offset], 0, 1)
                axe = "PY"
                # print(f"{device_name} {axe} {value_local} {value_remote}")
                send_ot_float_local(device_name, axe, 32, value_local)
                send_ot_float_remote(device_name, axe, tracker[1 + offset], value_remote)

                offset += 1
                value_local = remap(pz, tracker[7 + offset], tracker[19 + offset], 0, 1)
                value_remote = remap(pz, tracker[13 + offset], tracker[25 + offset], 0, 1)
                axe = "PZ"
                # print(f"{device_name} {axe} {value_local} {value_remote}")
                send_ot_float_local(device_name, axe, 32, value_local)
                send_ot_float_remote(device_name, axe, tracker[1 + offset], value_remote)

                offset += 1
                value_local = remap(rx, tracker[7 + offset] / 180, tracker[19 + offset] / 180, 0, 1)
                value_remote = remap(rx, tracker[13 + offset] / 180, tracker[25 + offset] / 180, 0, 1)
                axe = "RX"
                # print(f"{device_name} {axe} {value_local} {value_remote}")
                send_ot_float_local(device_name, axe, 32, value_local)
                send_ot_float_remote(device_name, axe, tracker[1 + offset], value_remote)

                offset += 1
                value_local = remap(ry, tracker[7 + offset] / 180, tracker[19 + offset] / 180, 0, 1)
                value_remote = remap(ry, tracker[13 + offset] / 180, tracker[25 + offset] / 180, 0, 1)
                axe = "RY"
                # print(f"{device_name} {axe} {value_local} {value_remote}")
                send_ot_float_local(device_name, axe, 32, value_local)
                send_ot_float_remote(device_name, axe, tracker[1 + offset], value_remote)

                offset += 1
                value_local = remap(rz, tracker[7 + offset] / 180, tracker[19 + offset] / 180, 0, 1)
                value_remote = remap(rz, tracker[13 + offset] / 180, tracker[25 + offset] / 180, 0, 1)
                axe = "RZ"
                # print(f"{device_name} {axe} {value_local} {value_remote}")
                send_ot_float_local(device_name, axe, 32, value_local)
                send_ot_float_remote(device_name, axe, tracker[1 + offset], value_remote)

        except Exception as e:
            print(f"Error: {e}")
            print(traceback.format_exc())
    
except zeroconf._exceptions.NonUniqueNameException as e:
    print("NonUniqueNameException, trying again...")
    os.execv(sys.executable, ['python'] + sys.argv)
except KeyboardInterrupt:
    stop()
except Exception:
    print("UNEXPECTED ERROR\n")
    print("Please Create an Issue on GitHub with the following information:\n")
    print(TITLE)
    print("Config:", config)
    print("Trackers:", trackers)
    print("Parameters:", parameters)
    print("Playspace Center:", playspace_center)
    print("Avatar Root:", avatar_root)
    print("Traceback:")
    traceback.print_exc()
    input("\nPress ENTER to exit")
    stop()
