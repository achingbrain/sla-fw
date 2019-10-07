import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from sl1fw import defines


def get_save_path() -> Optional[Path]:
    """
    Dynamic USB path, first usb device or None

    :return: First usb device path or None
    """
    usbs = [p for p in Path(defines.mediaRootPath).glob("*") if p.is_mount()]
    if len(usbs) == 0:
        return None
    return usbs[0]


def save_logs_to_usb(a64_serial: str) -> None:
    """
    Save logs to USB Flash drive

    :param a64_serial: A64 serial used to name the file
    """
    save_path = get_save_path()
    if save_path is None or not save_path.parent.exists():
        raise FileNotFoundError(save_path)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    serial = re.sub("[^a-zA-Z0-9]", "_", a64_serial)
    log_file = save_path / f"log.{serial}.{timestamp}.txt.xz"

    try:
        subprocess.check_call(["export_logs.bash", log_file])
    except Exception as exception:
        raise Exception(N_("Saving logs failed")) from exception
