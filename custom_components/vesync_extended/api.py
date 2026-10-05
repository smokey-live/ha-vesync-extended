"""Small VeSync client for the device families missing from pyvesync 3.4.2.

Reuse pyvesync authentication, without changing its global device map. Commands
use an explicit allowlist and validate both layers of VeSync's response envelope.
No raw API payloads, device identifiers, or credentials are logged here.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from typing import Any

from aiohttp import ClientError, ClientSession
from pyvesync import VeSync
from pyvesync.const import REGION_API_MAP
from pyvesync.models.base_models import DefaultValues
from pyvesync.models.vesync_models import RequestDeviceListModel
from pyvesync.utils.errors import ErrorTypes, VeSyncError, VeSyncLoginError
from pyvesync.utils.helpers import Helpers

from .const import (
    HUMIDIFIER_MODELS,
    HUMIDIFIER_MODES,
    HUMIDIFIER_STATUS_MODES,
    PURIFIER_MODELS,
    PURIFIER_MODES,
    PURIFIER_STATUS_MODES,
)

BYPASS_ENDPOINT = "/cloud/v2/deviceManaged/bypassV2"
# Candidate algorithm from pyvesync PR #532. Kept local to the new purifiers.
_CERT_SHA1 = "2CA4647FA8C5C9475B13FBD47984E525F38AD3B8"
_OFFLINE_CODES = {-11300030, -11300027}


class ApiError(Exception):
    """Cloud request or response failed; messages never contain raw payloads."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class AuthenticationError(ApiError):
    """Account needs to authenticate again."""


class DeviceOffline(ApiError):
    """An individual device is unavailable."""


class ReadOnlyError(ApiError):
    """Controls are disabled for this entry."""


def pack_signature(trace_id: str) -> str:
    """Build the candidate purifier signature reported by PR #532."""
    digest = hashlib.sha256((trace_id + _CERT_SHA1).encode()).hexdigest()
    return f"v0001-{digest}"


@dataclass(frozen=True)
class Device:
    """Information needed to address one cloud device; never serialize publicly."""

    cid: str
    name: str
    model: str
    config_module: str
    region: str
    firmware: str | None = None

    @property
    def is_purifier(self) -> bool:
        return self.model in PURIFIER_MODELS

    @property
    def status_method(self) -> str:
        return "getPurifierStatus" if self.is_purifier else "getHumidifierStatus"


@dataclass
class DeviceState:
    """Normalized, non-identifying values used by entities and diagnostics."""

    available: bool = False
    power: bool | None = None
    mode: str | None = None
    speed: int | None = None
    humidity: int | None = None
    target_humidity: int | None = None
    mist_level: int | None = None
    pm25: float | None = None
    filter_life: int | None = None
    display: bool | None = None
    child_lock: bool | None = None
    error_code: int | None = None
    error_reason: str | None = None
    # Field names are useful when extending support, without exposing identifiers.
    response_fields: list[str] = field(default_factory=list)


def _number(value: Any, minimum: float, maximum: float) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return value if minimum <= value <= maximum else None


def _integer(value: Any, minimum: int, maximum: int) -> int | None:
    number = _number(value, minimum, maximum)
    return int(number) if number is not None and number == int(number) else None


def _switch(value: Any) -> bool | None:
    if value is True or value == 1:
        return True
    if value is False or value == 0:
        return False
    return None


def parse_state(device: Device, data: dict[str, Any]) -> DeviceState:
    """Parse only documented fields. Missing optional fields remain unknown."""
    power = _switch(data.get("powerSwitch"))
    mode = data.get("workMode")
    modes = PURIFIER_STATUS_MODES if device.is_purifier else HUMIDIFIER_STATUS_MODES
    if power is None or not isinstance(mode, str) or mode not in modes:
        raise ApiError("Unsupported device status schema")
    state = DeviceState(
        available=True,
        power=power,
        mode=mode,
        display=_switch(data.get("screenSwitch")),
        child_lock=_switch(data.get("childLockSwitch")),
        error_code=_integer(data.get("errorCode"), 0, 2**31 - 1),
        response_fields=sorted(data),
    )
    if device.is_purifier:
        state.speed = _integer(data.get("fanSpeedLevel"), 0, 3)
        state.pm25 = _number(data.get("PM25"), 0, 10000)
        state.filter_life = _integer(data.get("filterLifePercent"), 0, 100)
    else:
        state.humidity = _integer(data.get("humidity"), 0, 100)
        state.target_humidity = _integer(data.get("targetHumidity"), 30, 80)
        state.mist_level = _integer(data.get("virtualLevel"), 0, 9)
        if state.humidity is None or state.target_humidity is None:
            raise ApiError("Unsupported humidifier status schema")
    return state


def command_payload(device: Device, action: str, value: Any) -> tuple[str, dict]:
    """Restrict all writes to understood fields, values, and exact device models."""
    if device.model not in PURIFIER_MODELS | HUMIDIFIER_MODELS:
        raise ValueError("Unsupported device model")
    if action in {"power", "display", "child_lock"}:
        if not isinstance(value, bool):
            raise ValueError("Switch value must be a boolean")
        if action == "power":
            index = "switchIdx" if device.is_purifier else "id"
            return "setSwitch", {"powerSwitch": int(value), index: 0}
        if action == "display":
            data = {"screenSwitch": int(value)}
            if not device.is_purifier:
                data["id"] = 0
            return "setDisplay", data
        if not device.is_purifier:
            raise ValueError("Humidifier child lock has not been verified")
        return "setChildLock", {"childLockSwitch": int(value)}
    if action == "mode":
        modes = PURIFIER_MODES if device.is_purifier else HUMIDIFIER_MODES
        if value not in modes:
            raise ValueError("Unsupported mode")
        if device.is_purifier and value == "manual":
            # pyvesync enters manual mode using a speed command, not a mode write.
            return "setLevel", {"levelIdx": 0, "manualSpeedLevel": 1, "levelType": "wind"}
        method = "setPurifierMode" if device.is_purifier else "setHumidityMode"
        return method, {"workMode": value}
    if action == "speed" and device.is_purifier:
        if _integer(value, 1, 3) is None:
            raise ValueError("Purifier speed must be 1, 2, or 3")
        return "setLevel", {"levelIdx": 0, "manualSpeedLevel": value, "levelType": "wind"}
    if action == "humidity" and not device.is_purifier:
        if _integer(value, 30, 80) is None:
            raise ValueError("Target humidity must be an integer from 30 to 80")
        return "setTargetHumidity", {"targetHumidity": value, "id": 0}
    # Mist controls are withheld until the physical/virtual level discrepancy
    # (5 in the device report versus 9 in Homebridge) is tested on a real 450S.
    raise ValueError("Unsupported or unverified action")


def unwrap_response(response: Any, *, bypass: bool, write: bool = False) -> dict:
    """Reject outer and inner errors, including false-success write responses."""
    if not isinstance(response, dict) or type(response.get("code")) is not int:
        raise ApiError("Invalid VeSync response envelope")
    layers = [response]
    if bypass:
        inner = response.get("result")
        if isinstance(inner, dict) and "code" in inner:
            layers.append(inner)
    for layer in layers:
        code = layer.get("code")
        if type(code) is not int:
            raise ApiError("Invalid VeSync response code")
        if code != 0:
            if code in _OFFLINE_CODES:
                raise DeviceOffline("Device offline", code)
            raise ApiError("VeSync rejected the request", code)
    if bypass:
        if len(layers) != 2:
            raise ApiError("Missing device response envelope")
        # Live setDisplay acknowledgments contain both success codes but omit
        # the inner result. Reads still require data, and explicit null or
        # malformed results remain errors. State must be confirmed separately.
        if write and "result" not in layers[-1]:
            return {}
        result = layers[-1].get("result")
    else:
        result = response.get("result")
    if not isinstance(result, dict):
        raise ApiError("Missing VeSync result")
    return result


class ExtendedClient:
    """Authenticate once and serialize requests to the owned VeSync devices."""

    def __init__(self, manager: VeSync, session: ClientSession, *, read_only: bool = True):
        self.manager = manager
        self.session = session
        self.read_only = read_only
        self.devices: dict[str, Device] = {}
        self._lock = asyncio.Lock()

    async def login(self) -> None:
        """Authenticate with the existing pyvesync login implementation."""
        try:
            if not await self.manager.login():
                raise AuthenticationError("VeSync login failed")
        except VeSyncLoginError as err:
            raise AuthenticationError("VeSync login failed") from err
        except VeSyncError as err:
            raise ApiError("VeSync authentication service failed") from err

    async def discover(self) -> dict[str, Device]:
        """Read the complete list and select exact models missing from the built-in integration."""
        async with self._lock:
            page = 1
            discovered: dict[str, Device] = {}
            while page <= 20:

                def build_request(page_no=page):
                    request = RequestDeviceListModel(
                        token=self.manager.auth.token,
                        accountID=self.manager.auth.account_id,
                        timeZone=self.manager.time_zone,
                        pageNo=page_no,
                        pageSize=100,
                        traceId=DefaultValues.newTraceId(),
                    )
                    return request.to_dict(), Helpers.req_header_bypass()

                response = await self._request(
                    "/cloud/v1/deviceManaged/devices", build_request, "post"
                )
                result = unwrap_response(response, bypass=False)
                items = result.get("list")
                if not isinstance(items, list):
                    raise ApiError("Missing device list")
                for item in items:
                    if not isinstance(item, dict):
                        raise ApiError("Invalid device list item")
                    model = item.get("deviceType")
                    if model not in PURIFIER_MODELS | HUMIDIFIER_MODELS:
                        continue
                    cid = item.get("cid") or item.get("uuid") or item.get("macID")
                    config = item.get("configModule")
                    if not isinstance(cid, str) or not isinstance(config, str):
                        raise ApiError("Missing device addressing fields")
                    discovered[cid] = Device(
                        cid,
                        item.get("deviceName") or model,
                        model,
                        config,
                        item.get("deviceRegion") or self.manager.current_region,
                        item.get("currentFirmVersion"),
                    )
                if len(items) < 100:
                    break
                page += 1
            else:
                raise ApiError("Device list exceeds supported pagination limit")
            self.devices = discovered
            return discovered

    async def get_state(self, device: Device) -> DeviceState:
        """Read device status without setting anything."""
        async with self._lock:
            response = await self._bypass(device, device.status_method, {}, write=False)
        return parse_state(device, response)

    async def command(self, device: Device, action: str, value: Any) -> None:
        """Send an allowed command; never optimistically claim it succeeded."""
        if self.read_only:
            raise ReadOnlyError("Controls are disabled while read-only mode is enabled")
        method, data = command_payload(device, action, value)
        async with self._lock:
            await self._bypass(device, method, data, write=True)

    async def _bypass(self, device: Device, method: str, data: dict, *, write: bool) -> dict:
        def build_request():
            trace_id = DefaultValues.newTraceId()
            body = {
                "acceptLanguage": "en",
                "accountID": self.manager.auth.account_id,
                "appVersion": DefaultValues.appVersion,
                "cid": device.cid,
                "configModule": device.config_module,
                "configModel": device.config_module,
                "deviceId": device.cid,
                "deviceRegion": device.region,
                "debugMode": False,
                "method": "bypassV2",
                "phoneBrand": DefaultValues.phoneBrand,
                "phoneOS": DefaultValues.phoneOS,
                "traceId": trace_id,
                "timeZone": self.manager.time_zone,
                "token": self.manager.auth.token,
                "userCountryCode": self.manager.country_code,
                "payload": {"method": method, "source": "APP", "data": data},
            }
            headers = Helpers.req_header_bypass()
            if device.is_purifier:
                headers |= {
                    "_packFileSignature": pack_signature(trace_id),
                    "_signOsInfo": "Android",
                }
            return body, headers

        # Homebridge uses PUT for humidifier writes; pyvesync uses POST for purifiers.
        http_method = "put" if write and not device.is_purifier else "post"
        response = await self._request(BYPASS_ENDPOINT, build_request, http_method)
        return unwrap_response(response, bypass=True, write=write)

    async def _request(self, endpoint: str, build_request, method: str) -> dict:
        for attempt in range(2):
            body, headers = build_request()
            base = REGION_API_MAP[self.manager.current_region]
            try:
                async with asyncio.timeout(20):
                    async with self.session.request(
                        method, base + endpoint, json=body, headers=headers
                    ) as response:
                        if response.status == 401:
                            payload = {"code": -11001022}
                        elif response.status != 200:
                            raise ApiError(f"VeSync HTTP error {response.status}")
                        else:
                            payload = await response.json()
            except (ClientError, ValueError) as err:
                raise ApiError("Could not connect to VeSync") from err
            if not isinstance(payload, dict):
                raise ApiError("Invalid VeSync response")
            try:
                token_error = Helpers.parse_error_code(payload).error_type == ErrorTypes.TOKEN_ERROR
                # Newer backends also use this code, as documented by Homebridge.
                token_error |= payload.get("code") == -11001022
            except (TypeError, KeyError, ValueError) as err:
                raise ApiError("Invalid VeSync response") from err
            if not token_error:
                return payload
            if attempt == 0:
                await self.login()
            else:
                raise AuthenticationError("VeSync session expired")
        raise AuthenticationError("VeSync session expired")
