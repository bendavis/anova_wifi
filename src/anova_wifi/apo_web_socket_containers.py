from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

class APOAnovaCommand(str, Enum):
    EVENT_APO_WIFI_LIST = "EVENT_APO_WIFI_LIST"
    EVENT_APO_STATE = "EVENT_APO_STATE"

@dataclass
class APOSystemInfo:
    online: bool
    hardwareVersion: str
    powerMains: int
    powerHertz: int
    firmwareVersion: str
    uiHardwareVersion: str
    uiFirmwareVersion: str
    firmwareUpdatedTimestamp: str
    lastConnectedTimestamp: str
    lastDisconnectedTimestamp: str
    triacsFailed: bool

@dataclass
class APOWetSensor:
    temp: float
    dosed: bool
    doseFailed: bool

@dataclass
class APODrySensor:
    temp: float
    sp: float

@dataclass
class APODryTopSensor:
    temp: float
    overheated: bool

@dataclass
class APODryBottomSensor:
    temp: float
    overheated: bool

@dataclass
class APOTemperatureSensor:
    mode: str
    wet: APOWetSensor
    dry: APODrySensor
    dryTop: APODryTopSensor
    dryBottom: APODryBottomSensor

@dataclass
class APOTimer:
    mode: str  # TODO: configure as enum, for now 'idle' is the only state I've seen
    initial: int  # not sure what unit this is
    current: int

@dataclass
class APOTemperatureProbe:
    connected: bool
    # probably missing stuff here, what attributes are set when connected?

@dataclass
class APOBoiler:
    descaleRequired: bool
    failed: bool
    overheated: bool
    temp: float
    watts: float
    dosed: bool

@dataclass
class APOEvaporator:
    failed: bool
    overheated: bool
    temp: float
    watts: float

@dataclass
class APOSteamGenerator:
    mode: str
    relativeHumidity: int
    boiler: APOBoiler
    evaporator: APOEvaporator

@dataclass
class APOHeatingElements:
    topElementOn: bool
    topFailed: bool
    topWatts: float
    bottomElementOn: bool
    bottomElementFailed: bool
    bottomElementWatts: float
    rearElementOn: bool
    rearElementFailed: bool
    rearElementWatts: float

@dataclass
class APOState:
    fanSpeed: int
    fanFailed: bool
    waterTankEmpty: bool
    doorClosed: bool
    lampOn: bool
    lampFailed: bool
    lampPreference: str
    uiCommunicationFailed: bool

@dataclass
class APOUpdate:
    cookerId: str
    type: str
    systemInfo: APOSystemInfo
    temperatureBulbs: APOTemperatureSensor
    timer: APOTimer
    probe: APOTemperatureProbe
    steam: APOSteamGenerator
    heating: APOHeatingElements
    state: APOState

def build_wifi_oven_state_body(apo_response: dict[str, Any]) -> APOUpdate:
    apo_system_info = APOSystemInfo(**apo_response['state']['systemInfo'])

    wetData = apo_response['state']['nodes']['temperatureBulbs']['wet']
    dryData = apo_response['state']['nodes']['temperatureBulbs']['dry']
    dryTopData = apo_response['state']['nodes']['temperatureBulbs']['dryTop']
    dryBottomData = apo_response['state']['nodes']['temperatureBulbs']['dryBottom']

    tempSensors = APOTemperatureSensor(
        mode=apo_response['state']['nodes']['temperatureBulbs']['mode'],
        wet=APOWetSensor(
            dosed=wetData['dosed'],
            doseFailed=wetData['doseFailed'],
            temp=wetData['current']['celsius'],
        ),
        dry=APODrySensor(
            temp=dryData['current']['celsius'],
            sp=dryData['setpoint']['celsius'],
        ),
        dryTop=APODryTopSensor(
            temp=dryTopData['current']['celsius'],
            overheated=dryTopData['overheated'],
        ),
        dryBottom=APODryTopSensor(
            temp=dryBottomData['current']['celsius'],
            overheated=dryBottomData['overheated'],
        ),
    )

    timerData = apo_response['state']['nodes']['timer']
    timer = APOTimer(
        current=timerData['current'],
        initial=timerData['initial'],
        mode=timerData['mode'],
    )

    # TODO: run the probe to see where the current value & target are located
    probeData = apo_response['state']['nodes']['temperatureProbe']
    probe = APOTemperatureProbe(
        connected=probeData['connected']
    )

    steamData = apo_response['state']['nodes']['steamGenerators']
    steamGenerator = APOSteamGenerator(
        mode=steamData['mode'],
        relativeHumidity=steamData['relativeHumidity']['current'],
        evaporator=APOEvaporator(
            temp=steamData['evaporator']['celsius'],
            watts=steamData['evaporator']['watts'],
            failed=steamData['evaporator']['failed'],
            overheated=steamData['evaporator']['overheated'],
        ),
        boiler=APOBoiler(
            descaleRequired=steamData['boiler']['descaleRequired'],
            failed=steamData['boiler']['failed'],
            overheated=steamData['boiler']['overheated'],
            temp=steamData['boiler']['celsius'],
            watts=steamData['boiler']['watts'],
            dosed=steamData['boiler']['dosed'],
        ),
    )

    heatingData = apo_response['state']['nodes']['heatingElements']
    heatingElements = APOHeatingElements(
        topElementOn=heatingData['top']['on'],
        topFailed=heatingData['top']['failed'],
        topWatts=heatingData['top']['watts'],
        bottomElementOn=heatingData['bottom']['on'],
        bottomElementFailed=heatingData['bottom']['failed'],
        bottomElementWatts=heatingData['bottom']['watts'],
        rearElementOn=heatingData['rear']['on'],
        rearElementFailed=heatingData['rear']['failed'],
        rearElementWatts=heatingData['rear']['watts'],
    )

    stateData = apo_response['state']['nodes']
    state = APOState(
        fanSpeed=stateData['fan']['speed'],
        fanFailed=stateData['fan']['failed'],
        waterTankEmpty=stateData['waterTank']['empty'],
        doorClosed=stateData['door']['closed'],
        lampOn=stateData['lamp']['on'],
        lampFailed=stateData['lamp']['failed'],
        lampPreference=stateData['lamp']['preference'],
        uiCommunicationFailed=stateData['userInterfaceCircuit']['communicationFailed'],
    )

    # Create APOUpdate object
    apo_update = APOUpdate(
        cookerId=apo_response['cookerId'],
        type=apo_response['type'],
        systemInfo=apo_system_info,
        temperatureBulbs=tempSensors,
        timer=timer,
        probe=probe,
        steam=steamGenerator,
        heating=heatingElements,
        state=state
    )

    return apo_update


@dataclass
class APOWifiDevice:
    cooker_id: str
    type: str
    paired_at: str
    name: str
    update_listener: Callable[[APOUpdate], None] | None = None

    def set_update_listener(self, update_function: Callable[[APOUpdate], None]) -> None:
        self.update_listener = update_function
