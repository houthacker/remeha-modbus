# Remeha Modbus Gateway integration for Home Assistant

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./custom_components/remeha_modbus/brand/dark_logo.png">
  <img alt="Remeha logo" src="./custom_components/remeha_modbus/brand/logo.png">
</picture>

[![Hassfest](https://github.com/houthacker/remeha-modbus/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/houthacker/remeha-modbus/actions/workflows/hassfest.yaml)
[![Validate HACS](https://github.com/houthacker/remeha-modbus/actions/workflows/hacs.yaml/badge.svg)](https://github.com/houthacker/remeha-modbus/actions/workflows/hacs.yaml)
[![pytest](https://github.com/houthacker/remeha-modbus/actions/workflows/pytest.yaml/badge.svg)](https://github.com/houthacker/remeha-modbus/actions/workflows/pytest.yaml)
[![badge](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/houthacker/ff0da84bf72a3d20fb68db8cb9d3e38e/raw/coverage_badge.json)](https://github.com/houthacker/remeha-modbus/actions/workflows/coverage.yaml)
[![GitHub tag (latest by date)](https://img.shields.io/github/v/tag/houthacker/remeha-modbus)](https://github.com/houthacker/remeha-modbus/releases/latest)

This integration allows you to manage your Remeha heating/cooling appliance locally from Home Assistant.

## Supported appliances

According to Remeha, the following appliances can be extended with a GTW-08 (modbus interface), or have one pre-installed:

| Appliance type     | Supported by GTW-08 | Tested  |
| ------------------ | :-----------------: | :-----: |
| Elga Ace           |       &check;       | &cross; |
| Elga Ace MB        |       &check;       | &cross; |
| Mercuria           |       &check;       | &cross; |
| Eria Tower         |       &check;       | &cross; |
| Eria Tower Ace (S) |       &check;       | &cross; |
| Mercuria Ace       |       &check;       | &check; |
| Mercuria Ace MB    |       &check;       | &check; |
| Gas 220 Ace        |       &check;       | &cross; |
| Quinta Ace 65      |       &check;       | &check; |
| Quinta Ace 160     |       &check;       | &cross; |
| Gas 320/620 Ace    |       &check;       | &cross; |
| miTerra            |       &check;       | &cross; |
| miTerra plus       |       &check;       | &cross; |

This integration is known to be working with the tested devices, but since the modbus interface is the same for all others, it is very likely that it will work for those too. This list is also available on the Remeha site (Dutch &#x1f1f3;&#x1f1f1;): [Remeha modbus support](https://kennisbank.remeha.nl/welke-remeha-toestellen-hebben-een-modbus-interface/).

## Supported modbus proxies

The following proxies are known to be working with this integration. Other gateways or proxies probably work as well, but haven't been tested.

| Device type                              | URL                                                                     |
| ---------------------------------------- | ----------------------------------------------------------------------- |
| Waveshare RS232/485 to WiFi and Ethernet | https://www.waveshare.com/product/rs232-485-to-wifi-eth-b.htm?sku=25222 |

## Current features

Planned features and features under discussion are available in the [issues](https://github.com/houthacker/remeha-modbus/issues). If you're missing a feature that has not been mentioned yet in the issues, please submit an issue or a PR.

- Connections:
  - Directly through a serial port
  - Indirectly through a proxy over WiFi or ethernet.
- Supported climate zones are exposed as [climate](https://www.home-assistant.io/integrations/climate/) entities
  - DHW (domestic hot water)
  - CH (central heating)
  - Automatically discovered once the integration has been set up.
  - Linked to a device, showing the type of board in the Remeha appliance, including its soft- and hardware versions.
  - Climate features are enabled depending on the climate zone type (for instance, a DHW zone is only able to heat, not cool).
- DHW auto scheduling:
  - This integration exposes a service called `dhw_auto_schedule` that can be used in automations or scripts. A detailed explanation follows below.
- Time schedule editing:
  If you install the [scheduler](https://github.com/nielsfaber/scheduler-card) integration, you can edit your DHW schedules from Home Assistant after [enabling it](#schedule-synchronization).

## Entities

Notworthy entities are described here.

### Heatpump managed schedules

The entity named `switch.heatpump_managed_schedules` is switched on by default, and is unavailable
if the `scheduler-component` integration is not installed. If it's available though, switching this switch
to 'off' causes the `scheduler-component` to execute the actions listed in synchronized zone schedules
directly, instead of letting the Remeha appliance handle schedule execution.

This might be undesirable, because:

- It might lead to conflicts: if your climate zone is still in scheduling mode, both the Remeha appliance
  _and_ the `scheduler-component` will attempt to control the heat pump state.
  To prevent that, the affected climate zone is put in eco mode once this entity is switched off.
- It prevents the heat pump from heating/cooling efficiently because it doesn't know what preset
  changes are coming up. This might lead to more energy usage.

To ensure that you have been warned about this, a persistent notification is triggered as well.

### Schedule synchronization

The entity named `switch.enable_schedule_sync` is switched off by default, and is unavailable if the
`scheduler-component` integration is not installed. If it's available though, switching this switch
to 'on' causes the DHW time zone schedules from your Remeha appliance to be synchronized with the `scheduler-component`
integration, allowing you to edit them in Home Assistant as well.

## Services

### dhw_auto_schedule

- Fields: no
- Return value: no
- Raised errors: `RemehaIncorrectServiceCall` if called when either:
  - There is no DHW climate
  - The configured weather forecast does not supply a `solar_irradiance` field

A description of this service is available in [DHW auto scheduling](#dhw-auto-scheduling)

### read_registers

Read arbitrary modbus registers from the Remeha modbus interface.
| Field | Type | Required | Description |
|-------|------|:---------:|-------------|
| `start_register` | `int` | &check; | The address of the first register to read. |
| `register_count` | `int` | &check; | The amount of registers to read (max 10). Defaults to 1 |
| `struct_format` | `str` | &check; | The struct format of the returned registers. Defaults to `=H` |

### bootstrap_blenders

- Fields: no
- Return value: no
- Raised errors: `RemehaIncorrectServiceCall` if called when any required integrations are missing but
  the related `switch` entities have been enabled by the user.

Bootstraps integrations with other components.
This service is called automatically once Home Assistant has started.
Calling it multiple times has no additional effect, except possibly when the blenders didn't bootstrap somehow.

## Installation

To install this integration, you need to have [HACS](https://hacs.xyz/docs/use) installed in your Home Assistant.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=houthacker&repository=remeha-modbus&category=integration)

## DHW auto scheduling

DHW auto scheduling is a feature allowing efficient heating of your DHW boiler by using as much solar power as possible while keeping the
interference to a minimum with other devices also using (direct) solar power.

### How to use

To start using the auto scheduling feature, execute the following steps:

#### Install KNMI weather integration

- Request an API key at [weerlive.nl](https://weerlive.nl/api/toegang/index.php)
- Install the KNMI weather integration using the button below and enter the obtained API key during installation.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=golles&repository=ha-knmi&category=integration)

#### Reconfigure this integration

- Reconfigure this integration and provide the required information about your PV system and DHW boiler. Select the KNMI weather
  entity to retrieve the weather forecast.

#### Example configuration:

![Example configuration](/.github/assets/remeha-dhw-scheduling-config.png)

#### Create an automation

- Then just create a new automation with the following properties:
  - Trigger at any time between 22:00 and 23:59
  - Call the Remeha Modbus service `dhw_auto_schedule`
  - Optionally set the DHW boiler climate to preset `schedule_1`.

#### Set the correct DHW preset mode

After creating the automation, a new schedule for the next day will automatically be created. If the preset is not set in the
automation, manually change the preset mode of your DHW boiler climate to `Schedule 1`, otherwise the schedule will of course be inactive.

### Screenshots

#### Remeha Appliance Info

![Remeha Appliance Info](/.github/assets/remeha-device.png)

#### Central Heating and Domestic Hot Water (DHW) climates

![Central Heating and Domesting Hot Water climates](/.github/assets/remeha-ch-dhw.png)

#### DHW History View

Showing current temperature, target temperature and heating status.

![DHW History View](/.github/assets/remeha-dhw-history.png)
