"""Synthetic protocol fixtures; these are not captures from a real device."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.vesync_extended.api import (
    ApiError,
    AuthenticationError,
    Device,
    DeviceOffline,
    ExtendedClient,
    ReadOnlyError,
    command_payload,
    pack_signature,
    parse_state,
    unwrap_response,
)

PURIFIER = Device("test-purifier", "Test purifier", "LAP-P501S-WUSR", "test-p", "US")
HUMIDIFIER = Device("test-humidifier", "Test humidifier", "LUH-N451S-WUS", "test-h", "US")


def test_purifier_missing_light_and_timer_keys_is_valid():
    state = parse_state(
        PURIFIER,
        {
            "powerSwitch": 1,
            "workMode": "pet",
            "fanSpeedLevel": 2,
            "PM25": 12,
            "filterLifePercent": 98,
        },
    )
    assert state.available and state.power and state.mode == "pet"
    assert state.speed == 2 and state.pm25 == 12 and state.filter_life == 98
    assert state.display is None and state.child_lock is None


def test_humidifier_keeps_readings_when_powered_off():
    state = parse_state(
        HUMIDIFIER,
        {
            "powerSwitch": 0,
            "workMode": "auto",
            "humidity": 69,
            "targetHumidity": 45,
            "virtualLevel": 3,
            "screenSwitch": 0,
        },
    )
    assert state.power is False
    assert state.humidity == 69 and state.target_humidity == 45
    assert state.display is False and state.mist_level == 3


def test_tunable_white_light_has_two_independent_brightness_presets():
    state = parse_state(
        HUMIDIFIER,
        {
            "powerSwitch": 0,
            "workMode": "autoPro",
            "humidity": 50,
            "targetHumidity": 60,
            "nightLight": {
                "nightLightSwitch": 1,
                "brightness": 25,
                "brightnessLevel2": 75,
                "nightLightLevel": 2,
                "colorTemperature": 3500,
                "unknownPrivateField": "ignored",
            },
        },
    )
    assert state.power is False and state.night_light is True
    assert state.light_brightness == 25 and state.light_brightness_level2 == 75
    assert state.light_level == 2 and state.light_kelvin == 3500
    assert "ignored" not in repr(state)


@pytest.mark.parametrize("light", [None, [], "on", {}, {"nightLightSwitch": "1"}])
def test_unknown_light_schema_does_not_disable_humidification(light):
    state = parse_state(
        HUMIDIFIER,
        {
            "powerSwitch": 1,
            "workMode": "auto",
            "humidity": 50,
            "targetHumidity": 60,
            "nightLight": light,
        },
    )
    assert state.available and state.night_light is None
    assert state.light_brightness is None and state.light_level is None


def test_light_rejects_invalid_optional_values_without_guessing():
    state = parse_state(
        HUMIDIFIER,
        {
            "powerSwitch": 1,
            "workMode": "auto",
            "humidity": 50,
            "targetHumidity": 60,
            "nightLight": {
                "nightLightSwitch": 0,
                "brightness": True,
                "brightnessLevel2": 101,
                "nightLightLevel": 3,
                "colorTemperature": 6500,
            },
        },
    )
    assert state.available and state.night_light is False
    assert state.light_brightness is None and state.light_brightness_level2 is None
    assert state.light_level is None and state.light_kelvin is None


@pytest.mark.parametrize(
    "settings,expected",
    [
        ({"on": False}, {"nightLightSwitch": 0, "colorMode": "white"}),
        ({"on": True}, {"nightLightSwitch": 1, "colorMode": "white"}),
        (
            {"on": True, "level": 1, "brightness": 25},
            {"nightLightSwitch": 1, "colorMode": "white", "nightLightLevel": 1, "brightness": 25},
        ),
        (
            {"on": True, "level": 2, "brightness": 75},
            {
                "nightLightSwitch": 1,
                "colorMode": "white",
                "nightLightLevel": 2,
                "brightnessLevel2": 75,
            },
        ),
        (
            {"on": True, "kelvin": 1700},
            {"nightLightSwitch": 1, "colorMode": "white", "colorTemperature": 1700},
        ),
        (
            {"on": True, "kelvin": 5500},
            {"nightLightSwitch": 1, "colorMode": "white", "colorTemperature": 5500},
        ),
    ],
)
def test_light_command_changes_only_requested_settings(settings, expected):
    assert command_payload(HUMIDIFIER, "light", settings) == ("setLightStatus", expected)
    with pytest.raises(ValueError):
        command_payload(PURIFIER, "light", settings)


@pytest.mark.parametrize(
    "settings",
    [
        None,
        {},
        {"on": 1},
        {"on": True, "extra": 1},
        {"on": True, "level": 1},
        {"on": True, "level": 2},
        {"on": True, "level": True},
        {"on": True, "level": 3},
        {"on": True, "brightness": 50},
        {"on": True, "level": 1, "brightness": 0},
        {"on": True, "level": 1, "brightness": 101},
        {"on": True, "level": 1, "brightness": True},
        {"on": True, "level": 1, "brightness": 1.0},
        {"on": True, "kelvin": 1600},
        {"on": True, "kelvin": 5600},
        {"on": True, "kelvin": 3050},
        {"on": True, "kelvin": "3000"},
    ],
)
def test_light_command_rejects_unverified_fields_and_ranges(settings):
    with pytest.raises(ValueError):
        command_payload(HUMIDIFIER, "light", settings)


@pytest.mark.parametrize(
    "device,values,expected_mode",
    [
        (PURIFIER, {"powerSwitch": 1, "workMode": "odorShieldBalanced"}, "odorShieldBalanced"),
        (
            HUMIDIFIER,
            {"powerSwitch": 0, "workMode": "autoPro", "humidity": 69, "targetHumidity": 45},
            "autoPro",
        ),
    ],
)
def test_observed_new_modes_are_readable_but_not_writable(device, values, expected_mode):
    # Synthetic non-identifying fixtures using the mode names observed live.
    state = parse_state(device, values)
    assert state.available and state.mode == expected_mode
    with pytest.raises(ValueError):
        command_payload(device, "mode", expected_mode)


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"enabled": True, "mode": "auto"},
        {"powerSwitch": "1", "workMode": "auto"},
        {"powerSwitch": 1, "workMode": "unknown"},
        {"powerSwitch": 1, "workMode": "auto", "humidity": 150, "targetHumidity": 50},
    ],
)
def test_rejects_incompatible_humidifier_schema(data):
    with pytest.raises(ApiError):
        parse_state(HUMIDIFIER, data)


@pytest.mark.parametrize(
    "device,action,value,expected",
    [
        (PURIFIER, "power", True, ("setSwitch", {"powerSwitch": 1, "switchIdx": 0})),
        (HUMIDIFIER, "power", False, ("setSwitch", {"powerSwitch": 0, "id": 0})),
        (
            PURIFIER,
            "speed",
            3,
            ("setLevel", {"levelIdx": 0, "manualSpeedLevel": 3, "levelType": "wind"}),
        ),
        (HUMIDIFIER, "humidity", 40, ("setTargetHumidity", {"targetHumidity": 40, "id": 0})),
        (HUMIDIFIER, "mode", "sleep", ("setHumidityMode", {"workMode": "sleep"})),
        (PURIFIER, "mode", "pet", ("setPurifierMode", {"workMode": "pet"})),
        (PURIFIER, "display", True, ("setDisplay", {"screenSwitch": 1})),
        (HUMIDIFIER, "display", False, ("setDisplay", {"screenSwitch": 0, "id": 0})),
    ],
)
def test_command_fields_match_each_device_family(device, action, value, expected):
    assert command_payload(device, action, value) == expected


@pytest.mark.parametrize(
    "device,action,value",
    [
        (PURIFIER, "speed", 4),
        (PURIFIER, "speed", True),
        (PURIFIER, "speed", 1.2),
        (PURIFIER, "power", 1),
        (HUMIDIFIER, "humidity", 81),
        (HUMIDIFIER, "humidity", "45"),
        (HUMIDIFIER, "child_lock", True),
        (HUMIDIFIER, "warm_mist", 1),
        (HUMIDIFIER, "mist", 9),
        (PURIFIER, "resetFilter", None),
        (HUMIDIFIER, "mode", "humidity"),
    ],
)
def test_unverified_and_invalid_commands_cannot_be_sent(device, action, value):
    with pytest.raises(ValueError):
        command_payload(device, action, value)


def test_inner_offline_error_is_not_reported_as_success():
    with pytest.raises(DeviceOffline) as err:
        unwrap_response({"code": 0, "result": {"code": -11300030}}, bypass=True)
    assert err.value.code == -11300030


@pytest.mark.parametrize(
    "response",
    [
        None,
        {},
        {"code": 0},
        {"code": 0, "result": {}},
        {"code": 0, "result": {"code": -1, "result": {}}},
        {"code": 0, "result": {"code": 0, "result": None}},
    ],
)
def test_invalid_or_failed_response_envelopes_are_rejected(response):
    with pytest.raises(ApiError):
        unwrap_response(response, bypass=True)


def test_successful_empty_write_result_is_accepted():
    assert unwrap_response({"code": 0, "result": {"code": 0, "result": {}}}, bypass=True) == {}


def test_observed_acknowledgment_without_data_is_accepted_only_for_writes():
    # Synthetic envelope matching the live acknowledgment's non-identifying shape.
    acknowledgment = {"code": 0, "result": {"code": 0, "traceId": "synthetic"}}
    assert unwrap_response(acknowledgment, bypass=True, write=True) == {}
    with pytest.raises(ApiError):
        unwrap_response(acknowledgment, bypass=True)


@pytest.mark.parametrize(
    "response",
    [
        {"code": -1, "result": {"code": 0}},
        {"code": 0, "result": {"code": -1}},
        {"code": 0, "result": {}},
        {"code": 0, "result": {"code": 0, "result": None}},
        {"code": 0, "result": {"code": 0, "result": "invalid"}},
        {"code": False, "result": {"code": 0}},
        {"code": 0, "result": {"code": False}},
        {"code": 0, "result": {"code": 0.0}},
    ],
)
def test_write_acknowledgments_still_reject_errors_and_malformed_results(response):
    with pytest.raises(ApiError):
        unwrap_response(response, bypass=True, write=True)


async def test_command_accepts_observed_acknowledgment():
    session = FakeSession({"code": 0, "result": {"code": 0}})
    client = ExtendedClient(make_manager(), session, read_only=False)
    await client.command(PURIFIER, "display", True)


class FakeResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        pass

    async def json(self):
        return self.payload


class FakeSession:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return FakeResponse(next(self.responses))


def make_manager(region="US"):
    return SimpleNamespace(
        auth=SimpleNamespace(token="fake-token", account_id="fake-account"),
        time_zone="America/Chicago",
        country_code="US",
        current_region=region,
        login=AsyncMock(return_value=True),
    )


async def test_read_only_blocks_before_network_call():
    session = FakeSession()
    client = ExtendedClient(make_manager(), session)
    with pytest.raises(ReadOnlyError):
        await client.command(PURIFIER, "power", True)
    assert session.calls == []


async def test_discovery_filters_supported_models_without_mutating_library():
    session = FakeSession(
        {
            "code": 0,
            "result": {
                "list": [
                    {
                        "cid": PURIFIER.cid,
                        "deviceName": "Test",
                        "deviceType": PURIFIER.model,
                        "configModule": "test",
                        "deviceRegion": "US",
                    },
                    {"cid": "classic", "deviceType": "Classic200S", "configModule": "test"},
                ]
            },
        }
    )
    client = ExtendedClient(make_manager(), session)
    assert list(await client.discover()) == [PURIFIER.cid]
    assert session.calls[0][2]["json"]["pageNo"] == 1


async def test_discovery_visits_second_page():
    irrelevant = {"deviceType": "Classic200S"}
    session = FakeSession(
        {"code": 0, "result": {"list": [irrelevant] * 100}},
        {
            "code": 0,
            "result": {
                "list": [
                    {"cid": HUMIDIFIER.cid, "deviceType": HUMIDIFIER.model, "configModule": "test"},
                ]
            },
        },
    )
    client = ExtendedClient(make_manager(), session)
    assert list(await client.discover()) == [HUMIDIFIER.cid]
    assert [call[2]["json"]["pageNo"] for call in session.calls] == [1, 2]


async def test_retry_rebuilds_credentials_and_signature():
    manager = make_manager()

    async def login():
        manager.auth.token = "fresh-token"
        return True

    manager.login.side_effect = login
    session = FakeSession(
        {"code": -11001000},
        {"code": 0, "result": {"code": 0, "result": {}}},
    )
    client = ExtendedClient(manager, session, read_only=False)
    await client.command(PURIFIER, "power", True)
    assert [call[2]["json"]["token"] for call in session.calls] == ["fake-token", "fresh-token"]
    for _, _, request in session.calls:
        assert request["headers"]["_packFileSignature"] == pack_signature(
            request["json"]["traceId"]
        )
        assert request["headers"]["_signOsInfo"] == "Android"


@pytest.mark.parametrize("code", [-11001000, -11001022])
async def test_authentication_retry_is_bounded(code):
    manager = make_manager()
    session = FakeSession({"code": code}, {"code": code})
    client = ExtendedClient(manager, session)
    with pytest.raises(AuthenticationError):
        await client.get_state(PURIFIER)
    assert len(session.calls) == 2
    manager.login.assert_awaited_once()


async def test_humidifier_write_uses_put_without_purifier_signature():
    session = FakeSession({"code": 0, "result": {"code": 0, "result": {}}})
    client = ExtendedClient(make_manager("EU"), session, read_only=False)
    await client.command(HUMIDIFIER, "humidity", 45)
    method, url, request = session.calls[0]
    assert method == "put" and url.startswith("https://smartapi.vesync.eu/")
    assert "_packFileSignature" not in request["headers"]
