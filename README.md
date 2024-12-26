# Hackebein's Object Tracking
Track your real objects and track them in VRChat. All SteamVR/OpenVR supported trackers are supported. [Demo](https://x.com/Hackebein/status/1817729114142343460)

Available on:
* [Steam](https://store.steampowered.com/app/3140770) (soon<sup>1</sup>)
* [Github](https://github.com/Hackebein/Object-Tracking-App/releases)

<sup>1</sup> beta keys can be requested via support

This application is used with [Unitypackage](https://github.com/Hackebein/Object-Tracking-Unitypackage).

## Support
* [Hackebein's Research Lab](https://discord.gg/AqCwGqqQmW) at discord.gg

### Project Overview
[Task Overview](https://github.com/users/Hackebein/projects/4)

## Versions
Everything before version 1.0 is to be seen as pre-release.

### Pre-release
Pre-releases are essentially test versions that have undergone less rigorous testing and may contain bugs. These versions have limited compatibility and are typically designed to work only with the latest provided Unitypackage version.

### Steam
Steam version receives auto updates.

Available branches:
* **Default**: 0.1.12
* **Beta**: 0.1.13

### Github
* [0.1.13](https://github.com/Hackebein/Object-Tracking-App/releases/download/0.1.13/HackebeinObjectTracking-0.1.13-win64.zip)

## Features
### AV3Emulator support
[AV3Emulator](https://github.com/lyuma/Av3Emulator) support is limited to send only.
Set launch parameter `--av3e-port` to send a copy of all messages to AV3Emulator. Needs to match UDP Port in "Avatars 3.0 Emulator Control". Optionally set `--av3e-ip` if Unity runs on a different PC.

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
`--debug`: set Log Level to Debug<br>
`--av3e-ip`: IP of AV3Emulator instance<br>
`--av3e-port`: Port of AV3Emulator instance<br>

## Troubleshoot
* Ensure only one ObjectTracking.exe is running (Task Manager)
* Restart VRChat if ObjectTracking was started afterward
* Reset OSC config (AM > Options > OSC > Reset Config)
* Switch avatar
* Close all VRChat UIs
* Nudge your thumbstick to move a bit forward
