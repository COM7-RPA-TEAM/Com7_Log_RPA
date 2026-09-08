@echo off
REM ===========================================================
REM  Deploy Cloud Functions for Com7 RPA Log
REM
REM  Plain ASCII, no ( ) blocks - labels and goto only, so that
REM  cmd.exe cannot mis-parse it under the OEM codepage.
REM
REM  Installs firebase-tools itself if it is not on this machine.
REM
REM  Usage: double-click, or run  deploy-functions.bat
REM  Everything is written to deploy-functions.log next to it.
REM ===========================================================
setlocal EnableExtensions

set "ROOT=%~dp0"
set "NODE_DIR=C:\Program Files\nodejs"
set "PATH=%NODE_DIR%;%APPDATA%\npm;%PATH%"
set "LOG=%ROOT%deploy-functions.log"

echo =========================================================== > "%LOG%"
echo  deploy-functions   %DATE% %TIME% >> "%LOG%"
echo =========================================================== >> "%LOG%"

echo. >> "%LOG%"
echo [1] TOOLING >> "%LOG%"
echo --- node --- >> "%LOG%"
where node >> "%LOG%" 2>&1
node --version >> "%LOG%" 2>&1
echo --- npm --- >> "%LOG%"
call npm --version >> "%LOG%" 2>&1

set "TRIED_INSTALL=0"

:find_firebase
set "FIREBASE="
if exist "%APPDATA%\npm\firebase.cmd" set "FIREBASE=%APPDATA%\npm\firebase.cmd"
if not "%FIREBASE%"=="" goto :got_fb

set "NPM_PREFIX="
for /f "usebackq delims=" %%P in (`npm config get prefix 2^>nul`) do set "NPM_PREFIX=%%P"
if exist "%NPM_PREFIX%\firebase.cmd" set "FIREBASE=%NPM_PREFIX%\firebase.cmd"
if not "%FIREBASE%"=="" goto :got_fb

for /f "usebackq delims=" %%P in (`where firebase.cmd 2^>nul`) do set "FIREBASE=%%P"
if not "%FIREBASE%"=="" goto :got_fb

REM --- not installed on this machine: install it once, then look again ---
if "%TRIED_INSTALL%"=="1" goto :no_firebase
echo --- firebase.cmd not found - installing firebase-tools --- >> "%LOG%"
echo     (npm prefix = %NPM_PREFIX%) >> "%LOG%"
echo Installing firebase-tools, this takes a minute...
call npm install -g firebase-tools --no-fund --no-audit >> "%LOG%" 2>&1
echo npm install exitcode=%ERRORLEVEL% >> "%LOG%"
set "TRIED_INSTALL=1"
goto :find_firebase

:no_firebase
echo --- firebase.cmd STILL NOT FOUND after install --- >> "%LOG%"
echo dir of %APPDATA%\npm: >> "%LOG%"
dir /b "%APPDATA%\npm" >> "%LOG%" 2>&1
echo dir of %NPM_PREFIX%: >> "%LOG%"
dir /b "%NPM_PREFIX%" >> "%LOG%" 2>&1
set "RC=101"
goto :report

:got_fb
echo --- firebase.cmd --- >> "%LOG%"
echo USING: %FIREBASE% >> "%LOG%"
call "%FIREBASE%" --version >> "%LOG%" 2>&1
echo --- logged in as --- >> "%LOG%"
call "%FIREBASE%" login:list >> "%LOG%" 2>&1

echo. >> "%LOG%"
echo [2] FUNCTIONS DEPENDENCIES >> "%LOG%"
if exist "%ROOT%web-rpa\functions\node_modules\firebase-functions" goto :deps_ok
echo node_modules missing - installing >> "%LOG%"
echo Installing functions dependencies...
pushd "%ROOT%web-rpa\functions"
call npm install --no-fund --no-audit >> "%LOG%" 2>&1
echo npm install exitcode=%ERRORLEVEL% >> "%LOG%"
popd
goto :deps_done

:deps_ok
echo OK: functions\node_modules\firebase-functions present >> "%LOG%"

:deps_done
echo. >> "%LOG%"
echo [3] DEPLOY >> "%LOG%"
echo Deploying functions, this takes a few minutes...
pushd "%ROOT%web-rpa"
call "%FIREBASE%" deploy --only functions --project com7-rpa-log >> "%LOG%" 2>&1
set "RC=%ERRORLEVEL%"
popd

:report
echo. >> "%LOG%"
echo EXITCODE=%RC% >> "%LOG%"
if not "%RC%"=="0" goto :failed
echo RESULT=DEPLOY_SUCCESS >> "%LOG%"
goto :show

:failed
echo RESULT=DEPLOY_FAILED >> "%LOG%"

:show
echo.
type "%LOG%"
echo.
echo Log written to: %LOG%
echo.
endlocal
