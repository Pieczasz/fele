"""Find the running League client: port and password from its lockfile, or from the client process's arguments.

The lockfile exists only while the client runs: `LeagueClient:<pid>:<port>:<password>:<protocol>`.
The password is a per-session token for 127.0.0.1; it is never logged or returned by the API.
"""

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

LOCKFILES = (
    Path("/Applications/League of Legends.app/Contents/LoL/lockfile"),  # macOS
    Path("C:/Riot Games/League of Legends/lockfile"),  # Windows default install
)
LOCKFILE_PARTS = 5
_ARG = re.compile(r"--(app-port|remoting-auth-token)=([^\s\"]+)")


@dataclass(frozen=True)
class Lcu:
    port: int
    password: str = field(repr=False)
    protocol: str = "https"

    @property
    def base_url(self) -> str:
        return f"{self.protocol}://127.0.0.1:{self.port}"


def parse_lockfile(text: str) -> Lcu | None:
    parts = text.strip().split(":")
    if len(parts) != LOCKFILE_PARTS or not parts[2].isdigit():
        return None
    return Lcu(int(parts[2]), parts[3], parts[4] or "https")


def parse_process_args(args: str) -> Lcu | None:
    found = dict(_ARG.findall(args))
    port, token = found.get("app-port"), found.get("remoting-auth-token")
    return Lcu(int(port), token) if port and port.isdigit() and token else None


def _process_args() -> str:
    try:
        out = subprocess.run(["/bin/ps", "-A", "-o", "args="], capture_output=True, text=True, timeout=3, check=False)
    except OSError, subprocess.SubprocessError:
        return ""
    return "\n".join(line for line in out.stdout.splitlines() if "LeagueClientUx" in line)


def find_client() -> Lcu | None:
    """The running client, or None. FELE_LCU_LOCKFILE overrides the default locations (tests use it)."""
    override = os.environ.get("FELE_LCU_LOCKFILE")
    for path in (Path(override),) if override else LOCKFILES:
        try:
            lcu = parse_lockfile(path.read_text(encoding="utf-8"))
        except OSError:
            continue
        if lcu:
            return lcu
    return None if override else parse_process_args(_process_args())
