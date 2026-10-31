# SPDX-License-Identifier: GPL-2.0-or-later
"""This PC's specs for the launcher's top bar (HomePage.qml rig pill): the graphics card the game
runs on, the processor, installed memory and the display. Read from the registry and kernel32
(no WMI, which takes seconds to start), on the launcher's GPU-check thread. Anything that can't be
read is left empty, and the pill leaves it out."""
import ctypes
import os
import re
import sys

# Display adapters (GUID_DEVCLASS_DISPLAY).
DISPLAY_CLASS = r'SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'
GPU_VENDORS = ('NVIDIA GeForce ', 'NVIDIA ', 'AMD Radeon ', 'AMD ', 'Intel(R) Arc(TM) ', 'Intel(R) ', 'Intel ')


def short_gpu(name):
    """"NVIDIA GeForce RTX 4090" -> "RTX 4090", "AMD Radeon RX 7900 XTX" -> "RX 7900 XTX"."""
    name = (name or '').strip()
    for prefix in GPU_VENDORS:
        if name.startswith(prefix):
            name = name[len(prefix):].strip()
            break
    return re.sub(r'\s+Graphics$', '', name)


def short_cpu(name):
    """The model: "AMD Ryzen 9 7950X3D 16-Core Processor" -> "7950X3D",
    "13th Gen Intel(R) Core(TM) i9-13900K" -> "i9-13900K"; the whole name when none is found."""
    words = re.sub(r'\((R|TM|tm)\)', '', name or '').split()
    words = [w for w in words if not re.fullmatch(r'\d+-Core|Processor|CPU|@.*|[\d.]+GHz', w, re.I)]
    models = [w for w in words if re.search(r'\d', w) and not re.fullmatch(r'\d+(th|st|nd|rd)', w)
              and not re.fullmatch(r'\d', w)]
    return models[-1] if models else ' '.join(words)


def long_cpu(name):
    """"AMD Ryzen 9 7950X3D 16-Core Processor" -> "Ryzen 9 7950X3D" (no vendor, trademarks or core count)."""
    words = re.sub(r'\((R|TM|tm)\)', '', name or '').split()
    words = [w for w in words if not re.fullmatch(r'AMD|Intel|\d+-Core|Processor|CPU|@.*|[\d.]+GHz|\d+(th|st|nd|rd)|Gen', w, re.I)]
    return ' '.join(words)


CARD_SIZES_GB = (1, 2, 3, 4, 6, 8, 10, 11, 12, 16, 20, 24, 32, 48, 64, 96)


def vram_label_gb(size_bytes):
    """The size the card is sold as: Windows reports a little less (an RTX 4090's 24 GB as 22.5 GiB),
    so the smallest card size at or above it."""
    gib = size_bytes / 2 ** 30
    if gib <= 0:
        return 0
    return next((size for size in CARD_SIZES_GB if size >= gib - 0.25), round(gib))


def driver_label(vendor_name, version):
    """NVIDIA's own number ("32.0.16.2101" -> "621.01"); other vendors keep Windows' version."""
    digits = (version or '').replace('.', '')
    if 'NVIDIA' in (vendor_name or '').upper() and len(digits) >= 5 and digits[-5:].isdigit():
        return f'{digits[-5:-2]}.{digits[-2:]}'
    return version or ''


def resolution_label(width, height):
    """The usual name of an output size: "4K", "1440p", "1080p", else "W × H"."""
    names = {(3840, 2160): '4K', (2560, 1440): '1440p', (1920, 1080): '1080p', (3440, 1440): '3440 × 1440 ultrawide',
             (5120, 1440): '5120 × 1440 super ultrawide', (2560, 1600): '1600p', (1920, 1200): '1200p'}
    return names.get((width, height), f'{width} × {height}' if width and height else '')


def gpu_details(name):
    """(VRAM in bytes, driver version) of the display adapter named `name`, from the registry."""
    if sys.platform != 'win32' or not name:
        return 0, ''
    import winreg
    try:
        root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, DISPLAY_CLASS)
    except OSError:
        return 0, ''
    with root:
        for i in range(64):
            try:
                sub = winreg.EnumKey(root, i)
            except OSError:
                break
            try:
                with winreg.OpenKey(root, sub) as key:
                    desc = winreg.QueryValueEx(key, 'DriverDesc')[0]
                    if desc.strip().lower() != name.strip().lower():
                        continue
                    version = winreg.QueryValueEx(key, 'DriverVersion')[0]
                    try:
                        vram = int(winreg.QueryValueEx(key, 'HardwareInformation.qwMemorySize')[0])
                    except (OSError, ValueError, TypeError):
                        vram = 0
                    return vram, version
            except OSError:
                continue
    return 0, ''


def cpu_name():
    if sys.platform != 'win32':
        return ''
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
            return ' '.join(winreg.QueryValueEx(key, 'ProcessorNameString')[0].split())
    except OSError:
        return ''


def cpu_cores():
    """Physical cores (GetLogicalProcessorInformationEx, RelationProcessorCore), 0 if unknown."""
    if sys.platform != 'win32':
        return 0
    kernel32 = ctypes.windll.kernel32
    size = ctypes.c_ulong(0)
    kernel32.GetLogicalProcessorInformationEx(0, None, ctypes.byref(size))
    buffer = ctypes.create_string_buffer(size.value)
    if not size.value or not kernel32.GetLogicalProcessorInformationEx(0, buffer, ctypes.byref(size)):
        return 0
    cores, offset = 0, 0
    while offset < size.value:
        # SYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX: Relationship (DWORD), Size (DWORD), ...
        relationship, record = ctypes.c_uint32.from_buffer(buffer, offset).value, ctypes.c_uint32.from_buffer(buffer, offset + 4).value
        cores += relationship == 0
        offset += record or size.value
    return cores


def memory_gb():
    """Installed memory in GB (GetPhysicallyInstalledSystemMemory: 32, not the 31 Windows can use)."""
    if sys.platform != 'win32':
        return 0
    kb = ctypes.c_ulonglong(0)
    if not ctypes.windll.kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(kb)):
        return 0
    return round(kb.value / (1024 * 1024))


def collect(gpu_name):
    """The rig as the QML pill shows it. `gpu_name` is the card the GPU check picked (the game's)."""
    vram, driver = gpu_details(gpu_name)
    cpu = cpu_name()
    return {
        'gpu': short_gpu(gpu_name), 'gpuFull': gpu_name or '',
        'vramGb': vram_label_gb(vram),
        'driver': driver_label(gpu_name, driver),
        'cpu': short_cpu(cpu), 'cpuFull': long_cpu(cpu),
        'cores': cpu_cores(), 'threads': os.cpu_count() or 0,
        'memoryGb': memory_gb(),
    }
