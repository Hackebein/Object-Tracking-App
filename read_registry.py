import ctypes
from ctypes import wintypes

# Registry type definitions
HKEY = wintypes.HANDLE
REGSAM = wintypes.DWORD
LPBYTE = ctypes.POINTER(ctypes.c_ubyte)

# Load advapi32.dll (Windows Registry API)
advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

# Function prototypes
RegOpenKeyExW = advapi32.RegOpenKeyExW
RegOpenKeyExW.argtypes = (
    HKEY,              # hKey
    wintypes.LPCWSTR,  # lpSubKey
    wintypes.DWORD,    # ulOptions
    REGSAM,            # samDesired
    ctypes.POINTER(HKEY)  # phkResult
)
RegOpenKeyExW.restype = wintypes.LONG

RegQueryValueExW = advapi32.RegQueryValueExW
RegQueryValueExW.argtypes = (
    HKEY,                 # hKey
    wintypes.LPCWSTR,     # lpValueName
    ctypes.POINTER(wintypes.DWORD),  # lpReserved
    ctypes.POINTER(wintypes.DWORD),  # lpType
    LPBYTE,               # lpData
    ctypes.POINTER(wintypes.DWORD)   # lpcbData
)
RegQueryValueExW.restype = wintypes.LONG

RegCloseKey = advapi32.RegCloseKey
RegCloseKey.argtypes = (HKEY,)
RegCloseKey.restype = wintypes.LONG

# Common registry root handles
HKEY_CLASSES_ROOT = 0x80000000
HKEY_CURRENT_USER = 0x80000001
HKEY_LOCAL_MACHINE = 0x80000002
HKEY_USERS = 0x80000003
HKEY_CURRENT_CONFIG = 0x80000005

# Access mask for reading keys
KEY_READ = 0x20019

def read_registry_raw_qword(hive: int, subkey: str, value_name: str, default: float) -> float:
    """
    Reads (up to) 8 bytes from a Windows registry value, even if it is
    incorrectly labeled as REG_DWORD but actually contains 8 bytes.
    
    :param hive: One of the predefined registry root constants (e.g., HKEY_LOCAL_MACHINE).
    :param subkey: The path to the registry key (e.g., r'SOFTWARE\\MyKey').
    :param value_name: The name of the registry value to read.
    :param default: The default value to return if the registry value cannot be read.
    :return: The registry value as a float, or the default value if the read fails.
    """
    try:
        hkey = HKEY()
        # 1) Open the registry key
        rc = RegOpenKeyExW(hive, subkey, 0, KEY_READ, ctypes.byref(hkey))
        if rc != 0:
            raise OSError(f"RegOpenKeyExW failed with error code {rc}")

        # Prepare variables for the query
        reg_type = wintypes.DWORD()
        data_size = wintypes.DWORD(8)  # We expect up to 8 bytes
        raw_buffer = (ctypes.c_ubyte * 8)()  # 8-byte buffer

        # 2) Query the registry value
        rc = RegQueryValueExW(
            hkey,
            value_name,
            None,
            ctypes.byref(reg_type),
            ctypes.cast(raw_buffer, LPBYTE),
            ctypes.byref(data_size)
        )
        if rc != 0:
            raise OSError(f"RegQueryValueExW failed with error code {rc}")

        # data_size.value tells us how many bytes were read
        # Interpreted as 64-bit double (float in python)
        return ctypes.c_double.from_buffer_copy(bytes(raw_buffer[:data_size.value])).value
    except Exception as e:
        print(f"An error occurred: {e}")
        return default
    finally:
        # 3) Close the key
        RegCloseKey(hkey)

def bytes_to_qword_le(raw: bytes, signed: bool = False) -> int:
    """
    Convert up to 8 bytes of little-endian data into a Python int.
    
    :param raw: Raw bytes from the registry.
    :param signed: Whether to interpret the 64-bit value as signed.
    :return: An integer (could be unsigned or signed, depending on `signed`).
    """
    if len(raw) > 8:
        raise ValueError("Data is longer than 8 bytes; unexpected for a QWORD.")
    # Pad or slice to exactly 8 bytes, then interpret as little-endian
    data_8 = raw.ljust(8, b'\x00')[:8]
    return int.from_bytes(data_8, byteorder='little', signed=signed)
