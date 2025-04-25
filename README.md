# Remeha Modbus Gateway integration for Home Assistant
![Remeha logo](logos/remeha-small.png)

[![Hassfest](https://github.com/houthacker/remeha-modbus/actions/workflows/hassfest.yaml/badge.svg)](https://github.com/houthacker/remeha-modbus/actions/workflows/hassfest.yaml)
[![Validate HACS](https://github.com/houthacker/remeha-modbus/actions/workflows/hacs.yaml/badge.svg)](https://github.com/houthacker/remeha-modbus/actions/workflows/hacs.yaml)
[![pytest](https://github.com/houthacker/remeha-modbus/actions/workflows/pytest.yaml/badge.svg)](https://github.com/houthacker/remeha-modbus/actions/workflows/pytest.yaml)
[![badge](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/houthacker/ff0da84bf72a3d20fb68db8cb9d3e38e/raw/coverage_badge.json)](https://github.com/houthacker/remeha-modbus/actions/workflows/coverage.yaml)
[![GitHub tag (latest by date)](https://img.shields.io/github/v/tag/houthacker/remeha-modbus)](https://github.com/houthacker/remeha-modbus/releases/latest)


This integration allows you to manage your Remeha heating/cooling appliance locally from Home Assistant.

### Supported appliances
According to Remeha, the following appliances can be extended with a GTW-08 (modbus interface), or have one pre-installed:

| Appliance type    | Supported by GTW-08           | Tested    |
|-------------------|:-----------------------------:|:---------:|
| Elga Ace          | &check;                       | &cross;   |
| Elga Ace MB       | &check;                       | &cross;   |
| Mercuria          | &check;                       | &cross;   |
| Eria Tower        | &check;                       | &cross;   |
| Eria Tower Ace (S)| &check;                       | &cross;   |
| Mercuria Ace      | &check;                       | &cross;   |
| Mercuria Ace MB   | &check;                       | &check;   |
| Gas 220 Ace       | &check;                       | &cross;   |
| Quinta Ace 160    | &check;                       | &cross;   |
| Gas 320/620 Ace   | &check;                       | &cross;   |
| miTerra           | &check;                       | &cross;   |
| miTerra plus      | &check;                       | &cross;   |

This integration is known to be working with the tested devices, but since the modbus interface is the same for all others, it is very likely that it will work for those too. This list is also available on the Remeha site (Dutch &#x1f1f3;&#x1f1f1;): [Remeha modbus support](https://kennisbank.remeha.nl/welke-remeha-toestellen-hebben-een-modbus-interface/).

### Supported modbus proxies
The following proxies are known to be working with this integration. Other gateways or proxies probably work as well, but haven't been tested.

| Device type | URL |
|-------------|-----|
| Waveshare RS232/485 to WiFi and Ethernet | https://www.waveshare.com/product/rs232-485-to-wifi-eth-b.htm?sku=25222 |

### Current features
Planned features and features under discussion are available in the [issues](https://github.com/houthacker/remeha_modbus/issues). If you're missing a feature that has not been mentioned yet in the issues, please submit an issue or a PR.
- Connections:
    - Directly through a serial port
    - Indirectly through a proxy over WiFi or ethernet.
- Supported climate zones are exposed as [climate](https://www.home-assistant.io/integrations/climate/) entities
    - DHW (domestic hot water)
    - CH (central heating)
    - Automatically discovered once the integration has been set up.
    - Linked to a device, showing the type of board in the Remeha appliance, including its soft- and hardware versions.
    - Climate features are enabled depending on the climate zone type (for instance, a DHW zone is only able to heat, not cool).

### Installation
To install this integration, you need to have [HACS](https://hacs.xyz/docs/use) installed in your Home Assistant.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=houthacker&repository=remeha-modbus&category=integration)

