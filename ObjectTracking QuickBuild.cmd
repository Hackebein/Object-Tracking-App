@ECHO OFF
pipreqs --mode compat --ignore dist,build --force

pyinstaller ObjectTracking-win64.spec
