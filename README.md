# Hackebein's Object Tracking
Track your real objects and track them in VRChat. All SteamVR/OpenVR tracker are supported. [Demo](https://x.com/Hackebein/status/1817729114142343460)

Available on:
* [Steam](https://store.steampowered.com/app/3140770) (soon)
* [Github](https://github.com/Hackebein/Object-Tracking-App/releases)

This application is used with [Unitypackage](https://github.com/Hackebein/Object-Tracking-Unitypackage)
This application has no UI.

## Support:
* [Hackebein's Research Lab](https://discord.gg/AqCwGqqQmW) at discord.gg

### Project Overview
[Task Overview](https://github.com/users/Hackebein/projects/4/views/1)

## Features
### AV3Emulator support
[AV3Emulator](https://github.com/lyuma/Av3Emulator) support is limited to send only.
Set launch parameter `--av3e-ip` (optional) and `--av3e-port` to send a copy of all messages to AV3Emulator. Needs to match UDP Port in "Avatars 3.0 Emulator Control".

## Config
Config: `%appdata%\ObjectTracking\config.json`

### IP and Port
Default: 127.0.0.1 / 9000<br>
IP and port of your VRChat.

### Server_Port
Default: 0 - Auto<br>
UDP - OSCquery Server

### HTTP_Port
Default: 0 - Auto<br>
TCP - Webserver to announce OSCquery Server

### UpdateRate
Update rate of tracking data. Should not be higher than your HMDs refresh rate.  (Planned to be removed)

## Debug
Log: `%appdata%\ObjectTracking\object_tracking.log`

### Launch Parameter
`--debug`: set Log Level to Debug
`--av3e-ip`: IP of AV3Emulator instance
`--av3e-port`: Port of AV3Emulator instance

## Troubleshoot
* Ensure only one ObjectTracking.exe is running (Task Manager)
* Restart VRChat if ObjectTracking was started afterward
* Reset OSC config (AM > Options > OSC > Reset Config)
* Switch avatar
* Close all VRChat UIs
* Nudge your thumbstick