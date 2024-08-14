import json
import random
import re
import string
import numpy
import openvr
import sys
import os
import time
import traceback
import ctypes
import argparse
import zeroconf
import logging
from logging.handlers import RotatingFileHandler
from pythonosc import udp_client, dispatcher, osc_server
from tinyoscquery.queryservice import OSCQueryService
from tinyoscquery.utility import get_open_tcp_port, get_open_udp_port
from tinyoscquery.query import OSCQueryBrowser, OSCQueryClient
from psutil import process_iter
from threading import Thread
from scipy.spatial.transform import Rotation

#TODO VERIFY THIS FUCKING PARAMETER EXPRESSION CONFIG

def get_absolute_path(relative_path) -> str:
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def get_absolute_data_path(relative_path) -> str:
    base_path = os.getenv('APPDATA') or getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    base_path = os.path.join(base_path, 'ObjectTracking')
    if not os.path.exists(base_path):
        os.makedirs(base_path)
    return os.path.join(base_path, relative_path)


def send_desktop_notification(title: str, message: str) -> None:
    logger.info(f"Sent desktop notification: {title} - {message}")
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(0, title, message, 0)


def set_title(title: str) -> None:
    if os.name == 'nt':
        ctypes.windll.kernel32.SetConsoleTitleW(title)


def is_vrchat_running() -> bool:
    """
    Checks if VRChat is running.
    Returns:
        bool: True if VRChat is running, False if not
    """
    _proc_name = "VRChat.exe" if os.name == 'nt' else "VRChat"
    return _proc_name in (p.name() for p in process_iter())


def find_service_by_regex(browser: OSCQueryBrowser, regex) -> zeroconf.ServiceInfo | None:
    for svc in browser.get_discovered_oscquery():
        client = OSCQueryClient(svc)
        host_info = client.get_host_info()
        if host_info is None:
            continue
        if re.match(regex, host_info.name):
            logger.debug(f"Found service by regex: {host_info.name}")
            return svc
    logger.debug(f"Service not found by regex: {regex}")
    return None


def wait_get_oscquery_client() -> OSCQueryClient:
    """
    Waits for VRChat to be discovered and ready and returns the OSCQueryClient.
    Returns:
        OSCQueryClient: OSCQueryClient for VRChat
    """
    logger.info("Waiting for VRChat Client to be discovered ...")
    service_info = None
    while service_info is None:
        browser = OSCQueryBrowser()
        time.sleep(2)  # Wait for discovery
        # TODO: check if multiple VRChat clients are found
        service_info = find_service_by_regex(browser, r"VRChat-Client-[A-F0-9]{6}")
    logger.info(f"Connecting to VRChat Client ({service_info.name}) ...")
    client = OSCQueryClient(service_info)
    logger.info("Waiting for VRChat Client to be ready ...")
    while client.query_node("/avatar/change") is None:
        time.sleep(1)
    logger.info("VRChat Client is ready!")
    return client


def wait_get_oscquery_server() -> osc_server.ThreadingOSCUDPServer:
    logger.info("Starting OSCquery Server ...")
    disp = dispatcher.Dispatcher()
    disp.set_default_handler(osc_message_handler)
    oscQueryServer = osc_server.ThreadingOSCUDPServer((IP, SERVER_PORT), disp)
    Thread(target=oscQueryServer.serve_forever, daemon=True).start()
    # Announce Server
    oscServiceName = "ObjectTracking-" + ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
    logger.info(f"Announcing Server as {oscServiceName} ...")
    oscQueryService = OSCQueryService(oscServiceName, HTTP_PORT, SERVER_PORT)
    oscQueryService.advertise_endpoint("/avatar/change")
    # TODO: add all endpoints
    
    return oscQueryServer
    

def send_parameter(parameter: str, value) -> None:
    """
    Sends a parameter to VRChat via OSC if parameter got updated.
    Parameters:
        parameter (str): Name of the parameter
        value (any): Value of the parameter
    Returns:
        None
    """
    if get_parameter(parameter, None) != value:
        logger.debug(f"<  > {AVATAR_PARAMETERS_PREFIX + parameter} = {value} ({type(value)})")
        oscClient.send_message(AVATAR_PARAMETERS_PREFIX + parameter, value)
    else:
        logger.debug(f"<\\\\> {AVATAR_PARAMETERS_PREFIX + parameter} = {value} ({type(value)})")
    
    if 'oscClientUnity' in globals():
        oscClientUnity.send_message(AVATAR_PARAMETERS_PREFIX + parameter, value)

def send_default_position(tracker_name: str, tracker_config) -> None:
    offset = 0
    for key in ["PX", "PY", "PZ", "RX", "RY", "RZ"]:
        #local
        send_parameter(f"ObjectTracking/{tracker_name}/L{key}", 0)
        
        #remote
        accuracy_bytes, accuracy_bits = divmod(tracker_config[1 + offset], 8)
        for i in range(accuracy_bytes):
            send_parameter(f"ObjectTracking/{tracker_name}/R{key}-Byte{i}", 0)
        for i in range(accuracy_bits):
            send_parameter(f"ObjectTracking/{tracker_name}/R{key}-Bit{i}", 0)
        
        offset += 1

def send_position(tracker_name: str, matrix, tracker_config) -> None:
    px, py, pz, rx, ry, rz = convert_matrix_to_osc_tuple(matrix)
    
    offset = 0
    for key, value in {
        "PX": px,     # 0
        "PY": py,     # 1
        "PZ": pz,     # 2
        "RX": rx*180, # 3
        "RY": ry*180, # 4
        "RZ": rz*180  # 5
    }.items():
        logger.debug(f"Sending {tracker_name}/{key} = {value}")
        
        #local
        value_local = remap(value, tracker_config[7 + offset], tracker_config[19 + offset], 0, 1)
        value_local = clamp(value_local, 0)
        send_parameter(f"ObjectTracking/{tracker_name}/L{key}", value_local)
        
        #remote
        value_remote = remap(value, tracker_config[13 + offset], tracker_config[25 + offset], 0, 1)
        value_remote = clamp(value_remote, 0)
        value_bin = round(value_remote * (2**tracker_config[1 + offset]-1))
        accuracy_bytes, accuracy_bits = divmod(tracker_config[1 + offset], 8)
        for i in range(accuracy_bytes):
            value_bin, byte = divmod(value_bin, 2**8)
            send_parameter(f"ObjectTracking/{tracker_name}/R{key}-Byte{i}", byte)
        for i in range(accuracy_bits):
            value_bin, bit = divmod(value_bin, 2**1)
            send_parameter(f"ObjectTracking/{tracker_name}/R{key}-Bit{i}", bit)
        
        offset += 1


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
    logger.info(f"Avatar changed to {value}")
    global parameters, trackers, tracking_references_raw
    parameters = {}
    trackers = {}
    tracking_references_raw = {}


def osc_message_handler(addr, value) -> None:
    """
    Handles OSC messages.
    Parameters:
        addr (str): Address of the message
        value (any): Value of the message
    Returns:
        None
    """ 
    parameter = addr.removeprefix(AVATAR_PARAMETERS_PREFIX)
    if parameter.startswith("ObjectTracking/"):
        logger.debug(f" ><  {addr}: {value} ({type(value)})")
    if addr == "/avatar/change":
        on_avatar_change(addr, value)
    set_parameter(parameter, value)
    if parameter == "ObjectTracking/config/index" and value == 0:
        logger.info(trackers)
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
            logger.info(f"{device}[{index}] {old} => {new}")
        trackers[device][index] = new
    if re.match(r"ObjectTracking/config/(?!index|value)", parameter) and value > 0:
        set_parameter("ObjectTracking/config/device", parameter.removeprefix("ObjectTracking/config/"))
    if parameter == "ObjectTracking/isStabilized" and value:
        oscClient.send_message("/input/Vertical", 0.0)
    if parameter == "ObjectTracking/goStabilized" and not get_parameter("ObjectTracking/isStabilized", False) and value:
        oscClient.send_message("/input/Vertical", 1.0)


def clamp(n, minn=-1, maxn=1):
    """Clamps a value between a minimum and maximum value"""
    return max(min(maxn, n), minn)


def remap(x: float, in_min: float, in_max: float, out_min: float, out_max: float) -> float:
    if in_max == in_min:
        return 0
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


def rotate_matrix_xz(matrix: numpy.ndarray, pill: numpy.ndarray) -> numpy.ndarray:
    # Convert degrees to radians
    px, py, pz, rx, ry, rz = convert_matrix_to_osc_tuple(pill)
    radians = numpy.deg2rad(ry * 180)

    rotation = numpy.array([
        [numpy.cos(radians), 0, numpy.sin(radians)],
        [0, 1, 0],
        [-numpy.sin(radians), 0, numpy.cos(radians)]
    ])
        
    # position adjustment
    matrix[:3, 3] = numpy.dot(rotation, matrix[:3, 3])
    
    # rotation adjustment
    matrix[:3, :3] = numpy.dot(rotation, matrix[:3, :3])
    matrix[:3, :3] = numpy.dot(rotation, matrix[:3, :3])
        
    return matrix
    
    
def print_matrix(name: str, matrix: numpy.ndarray) -> None:
    px, py, pz, rx, ry, rz = convert_matrix_to_osc_tuple(matrix)
    logger.debug(f"{name}: px: {round(px, 3)}m, py: {round(py, 3)}m, pz: {round(pz, 3)}m, rx: {round(rx*180, 2)}° ({round(rx, 2)}), ry: {round(ry*180, 2)}° ({round(ry, 2)}), rz: {round(rz*180, 2)}° ({round(rz, 2)})")


def compute_tracking_reference_position(tracking_reference_positions):
    tracking_reference_positions = numpy.array(list(tracking_reference_positions.values()))
    tracking_reference_position = numpy.eye(4)
    if len(tracking_reference_positions):
        # Position
        tracking_reference_position[:3, 3] = numpy.sum(tracking_reference_positions[:, 0:3, 3], axis=0) / len(tracking_reference_positions)

        # Rotation
        quaternions = [Rotation.from_matrix(matrix).as_quat(False) for matrix in tracking_reference_positions[:, 0:3, 0:3]]
        q_mean = numpy.array(quaternions).mean(axis=0)
        avg_quaternion =  q_mean / numpy.linalg.norm(q_mean)
        tracking_reference_position[:3, :3] = Rotation.from_quat(avg_quaternion).as_matrix()
    return tracking_reference_position



def relative_matrix(parent: numpy.ndarray, child: numpy.ndarray) -> numpy.ndarray:
    result = numpy.eye(4)
    result[0:3, 0:3] = numpy.dot(numpy.linalg.inv(parent[0:3, 0:3]), child[0:3, 0:3])
    result[0:3, 3] = child[0:3, 3] - parent[0:3, 3]
    return result


def convert_matrix34_to_matrix44(matrix34: openvr.HmdMatrix34_t) -> numpy.ndarray:
    """ Convert OpenVR's 3x4 matrix to a 4x4 NumPy matrix """
    return numpy.array([
        [matrix34.m[0][0], matrix34.m[0][1], -matrix34.m[0][2], matrix34.m[0][3]],
        [matrix34.m[1][0], matrix34.m[1][1], -matrix34.m[1][2], matrix34.m[1][3]],
        [-matrix34.m[2][0], -matrix34.m[2][1], matrix34.m[2][2], -matrix34.m[2][3]],
        [0, 0, 0, 1]
    ])


def set_y_and_xz_rotation_to_zero(matrix: numpy.ndarray) -> numpy.ndarray:
    # set y to zero
    matrix[1, 3] = 0
    # set x and z rotation to 0
    theta = numpy.arctan2(matrix[2, 0], matrix[0, 0])
    matrix[0:3, 0:3] = numpy.array([
        [numpy.cos(theta), 0, numpy.sin(theta)],
        [0, 1, 0],
        [-numpy.sin(theta), 0, numpy.cos(theta)]
    ])
    return matrix


def set_y_and_rotation_to_zero(matrix: numpy.ndarray) -> numpy.ndarray:
    # set y to zero
    matrix[1, 3] = 0
    # set rotation to 0
    matrix[0:3, 0:3] = numpy.eye(3)
    return matrix


def convert_matrix_to_osc_tuple(pose: numpy.ndarray) -> tuple[float, float, float, float, float, float]:
    # position
    x, y, z = pose[0:3, 3]
    x = float(x)
    y = float(y)
    z = float(z)

    # rotation
    yaw, pitch, roll = Rotation.from_matrix(pose[0:3, 0:3]).as_euler("YXZ")
    # x, value range: -0.5 - 0.5
    pitch = float(pitch / numpy.pi)
    # y, value range: -1.0 - 1.0
    yaw = float(yaw / numpy.pi)
    # z, value range: -1.0 - 1.0
    roll = float(roll / numpy.pi)

    return (x, y, z, pitch, yaw, roll)


def get_logger():
    log_level = logging.DEBUG
    if os.path.basename(sys.executable).lower() == "objecttracking.exe":
        log_level = logging.INFO

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            RotatingFileHandler(
                get_absolute_data_path("ObjectTracking.log"), maxBytes=10*1024*1024, backupCount=5
            ),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


logger = get_logger()

# Argument Parser
parser = argparse.ArgumentParser(
    description='ObjectTracking: OpenVR tracking data to VRChat via OSC.')
parser.add_argument('--av3e-ip', required=False, type=str, help="AV3Emulator IP.")
parser.add_argument('--av3e-port', required=False, type=str, help="AV3Emulator Port.")
args = parser.parse_args()

application = openvr.init(openvr.VRApplication_Utility)
openvr.VRApplications().addApplicationManifest(get_absolute_path("app.vrmanifest"))

# first start
if not os.path.isfile(get_absolute_data_path("config.json")):
    try:
        openvr.VRApplications().setApplicationAutoLaunch("Hackebein.ObjectTracking", True)
    except Exception as e:
        pass
    with open(get_absolute_data_path("config.json"), 'w') as f:
        json.dump({
            "IP": "127.0.0.1",
            "Port": 9000,
            "Server_Port": 0,
            "HTTP_Port": 0,
            "UpdateRate": 90
        }, f, indent=4)

openvr.VRInput().setActionManifestPath(get_absolute_data_path("config.json"))
config = json.load(open(get_absolute_data_path("config.json")))

IP = config["IP"]
# shouldn't that be read from zeroconf?
PORT = int(config["Port"])
AV3EMULATOR_IP = args.av3e_ip if args.av3e_ip else IP
AV3EMULATOR_PORT = int(args.av3e_port) if args.av3e_port else None
SERVER_PORT = int(config["Server_Port"] if config["Server_Port"] > 0 else get_open_udp_port()) # OSC QUERY SERVER
HTTP_PORT = int(config["HTTP_Port"] if config["HTTP_Port"] > 0 else get_open_tcp_port()) # OSC QUERY
UPDATE_INTERVAL = 1 / float(config['UpdateRate'])
AVATAR_PARAMETERS_PREFIX = "/avatar/parameters/"
TITLE = "ObjectTracking v0.1.8"

set_title(TITLE)
logger.info(f"IP: {IP} / {AV3EMULATOR_IP}")
logger.info(f"Port: {PORT} / {AV3EMULATOR_PORT}")
logger.info(f"Server Port: {SERVER_PORT}")
logger.info(f"HTTP Port: {HTTP_PORT}")
logger.info(f"Update Rate: {config['UpdateRate']}Hz / Update Interval: {UPDATE_INTERVAL * 1000:.2f}ms")

# tracker config
trackers = {}
# osc recieved parameters
parameters = {}

hmd_raw = None
pill_raw = None
tracking_references_raw = {}
tracking_objects_raw = {}
try:
    logger.info("Waiting for VRChat Client to start ...")
    while not is_vrchat_running():  # TODO: check consistently for this
        time.sleep(1)
    logger.info(f"Waiting for OSCClient to connect to {IP}:{PORT} ...")
    oscClient = udp_client.SimpleUDPClient(IP, PORT)
    if AV3EMULATOR_PORT is not None:
        oscClientUnity = udp_client.SimpleUDPClient(AV3EMULATOR_IP, AV3EMULATOR_PORT)
    
    #logger.info("Waiting for OSCQueryClient to connect to VRChat Client ...")
    #oscQueryClient = wait_get_oscquery_client()
    
    logger.info("Waiting for OSCQueryServer to start ...")
    oscQueryServer = wait_get_oscquery_server()
    
    # TODO: test OSC roundtrip
    
    logger.info("Init complete!")
    cycle_start_time = time.perf_counter()
    while True:
        target_time = UPDATE_INTERVAL
        if get_parameter("ObjectTracking/isRemotePreview", False):
            target_time = 1 / 10
        wait_time = target_time - (time.perf_counter() - cycle_start_time)
        if wait_time > 0:
            if wait_time / target_time < 0.1:
                logger.warning(f"Warning: about {wait_time / target_time * 100:.0f}% frame time left")
            time.sleep(wait_time)
        else:
            logger.warning(f"Warning: {abs(wait_time * 1000):.2f}ms behind schedule, decreasing UpdateRate recommended if this gets spammed")
        cycle_start_time = time.perf_counter()
        try:
            hmd = None
            pill = None
            tracking_objects = {}
            devices = application.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseStanding, 0, openvr.k_unMaxTrackedDeviceCount)
            for i in range(openvr.k_unMaxTrackedDeviceCount):
                if not devices[i].bPoseIsValid:
                    continue
                if devices[i].eTrackingResult != openvr.TrackingResult_Running_OK:
                    continue
                
                serial_number = application.getStringTrackedDeviceProperty(i, openvr.Prop_SerialNumber_String)
                if application.getTrackedDeviceClass(i) == openvr.TrackedDeviceClass_TrackingReference:
                    tracking_references_raw[serial_number] = convert_matrix34_to_matrix44(devices[i].mDeviceToAbsoluteTracking)
                if application.getTrackedDeviceClass(i) == openvr.TrackedDeviceClass_HMD:
                    hmd_raw = convert_matrix34_to_matrix44(devices[i].mDeviceToAbsoluteTracking)
                tracking_objects_raw[serial_number] = convert_matrix34_to_matrix44(devices[i].mDeviceToAbsoluteTracking)
            tracking_reference = compute_tracking_reference_position(tracking_references_raw)
            tracking_objects_raw["Playspace"] = set_y_and_xz_rotation_to_zero(tracking_reference)
            tracking_reference = set_y_and_rotation_to_zero(tracking_reference)
            
            if hmd_raw is not None:
                #hmd = relative_matrix(tracking_reference, hmd_raw)
                if get_parameter("ObjectTracking/isStabilized", False) == False:
                    old_pill_raw = pill_raw
                    pill_raw = set_y_and_xz_rotation_to_zero(hmd_raw)
                    if get_parameter("TrackingType", 0) > 3 and get_parameter("VelocityX", 0) == 0 and get_parameter("VelocityY", 0) == 0 and get_parameter("VelocityZ", 0) == 0:
                        if old_pill_raw is not None:
                            pill_raw[0:3, 0:3] = old_pill_raw[0:3, 0:3]
                if pill_raw is not None:
                    pill = relative_matrix(tracking_reference, pill_raw)
            
            for key, object in tracking_objects_raw.items():
                tracking_objects[key] = relative_matrix(tracking_reference, object)
                        
            if pill is not None:
                for key, tracker in trackers.items():
                    if key == "global":
                        continue
                    if key in tracking_objects:
                        pos = relative_matrix(pill, tracking_objects[key])
                        pos = rotate_matrix_xz(pos, pill)
                        send_position(key, pos, tracker)
                    else:
                        send_default_position(key, tracker)
        except Exception as e:
            logger.info(f"Error: {e}")
            logger.info(traceback.format_exc())
    
except zeroconf._exceptions.NonUniqueNameException as e:
    logger.info("NonUniqueNameException, trying again...")
    os.execv(sys.executable, ['python'] + sys.argv)
except KeyboardInterrupt:
    pass
except Exception:
    logger.info("UNEXPECTED ERROR\n")
    logger.info("Please Create an Issue on GitHub with the following information:\n")
    logger.info(TITLE)
    logger.info("Config:", config)
    logger.info("Trackers:", trackers)
    logger.info("Parameters:", parameters)
    logger.info("Reference:", tracking_reference)
    logger.info("Traceback:")
    logger.info(traceback.format_exc())

try:
    openvr.shutdown()
except Exception as e:
    logger.info("Error shutting down OVR: " + str(e))

if 'oscQueryServer' in globals():
    oscQueryServer.shutdown()
sys.exit()