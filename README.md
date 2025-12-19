# Plex Custom Control

A HACS custom integration for Home Assistant that allows you to control Plex devices.
For more information, visit [https://github.com/haumlab/plex-hacs](https://github.com/haumlab/plex-hacs).

## Features
- Export Plex clients as Media Player entities.
- Play, Pause, Stop, Next, Previous.
- Volume control.
- Use in Home Assistant automations.

## Installation
1. Open **HACS** in your Home Assistant.
2. Click the **three dots** in the top right corner.
3. Select **Custom repositories**.
4. Paste `https://github.com/haumlab/plex-hacs` into the Repository field.
5. Select **Integration** as the category and click **Add**.
6. Find **Plex Custom Control** in HACS and click **Download**.
7. Restart Home Assistant.
8. Go to **Settings** -> **Devices & Services** -> **Add Integration** and search for "Plex Custom Control".

## Authentication
This integration supports the Plex.tv PIN flow. You will be given a 4-digit code to enter at [https://plex.tv/link](https://plex.tv/link). This is the easiest and most secure way to connect.

Alternatively, you can still use a manual token if you prefer.
