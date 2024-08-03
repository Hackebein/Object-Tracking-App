# Hackebein's Object Tracking
Track your real objects and track them in VRChat. All SteamVR/OpenVR tracker are supported.

Available on:
* [Steam](https://store.steampowered.com/app/3140770) (soon)
* [Github](https://github.com/Hackebein/Object-Tracking-App/releases)

This application is used with [Unitypackage](https://github.com/Hackebein/Object-Tracking-Unitypackage)
This application has no UI. 

## Config
Config: `%appdata%\ObjectTracking\config.json`

### IP and Port
Default: 127.0.0.1 / 9000<br>
IP and port of your VRChat. (Planned to be removed)

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

### Debug Mode
`ObjectTrackingDebug.exe`<br>
Debug mode lowers log level and shows log output in console