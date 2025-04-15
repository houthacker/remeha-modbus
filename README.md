# Remeha Modbus Gateway integration for Home Assistant
![Remeha logo](logos/remeha-small.png)

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

This integration is known to be working with the checked devices, but since the modbus interface is the same for all others, it is very likely that it will work for those too. This list is also available on the Remeha site (Dutch &#x1f1f3;&#x1f1f1;): [Remeha modbus support](https://kennisbank.remeha.nl/welke-remeha-toestellen-hebben-een-modbus-interface/).

### Supported modbus proxies
The following proxies are known to be working with this integration. If you use another device that works too, please submit a PR.

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