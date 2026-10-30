# Build the patched VLC for Android on Windows

These are the steps that produced a working APK on Windows 11 on 2026-10-29 (cold build: 15 minutes).
They are **not wrapped in a script**: nobody has run them as one script. Read each step.
Commands are for Git Bash. Replace `C:/work` with a folder of your own. Do not use a folder
inside OneDrive.

## 1. Tools

```bash
W=C:/work/vlc-build
mkdir -p $W/tools $W/dl
# JDK 21 (Eclipse Temurin), portable zip
curl -L -o $W/dl/jdk21.zip "https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse"
python -m zipfile -e $W/dl/jdk21.zip $W/tools/
# Android command-line tools
curl -L -o $W/dl/cmdtools.zip "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"
mkdir -p $W/android-sdk/cmdline-tools
python -m zipfile -e $W/dl/cmdtools.zip $W/android-sdk/cmdline-tools/
mv $W/android-sdk/cmdline-tools/cmdline-tools $W/android-sdk/cmdline-tools/latest
```

## 2. Android SDK parts

`sdkmanager --licenses` shows Google's license. **Read it and accept it yourself.**

```bash
export JAVA_HOME=$W/tools/jdk-21.0.12.1+1   # the folder the zip created. Your version number may differ.
SDKM=$W/android-sdk/cmdline-tools/latest/bin/sdkmanager.bat
$SDKM --sdk_root=$W/android-sdk --licenses
$SDKM --sdk_root=$W/android-sdk "platforms;android-36" "build-tools;36.0.0" "platform-tools"
```

## 3. Gradle 9.3.1 (the version VLC pins)

```bash
curl -L -o $W/dl/gradle-9.3.1-bin.zip https://services.gradle.org/distributions/gradle-9.3.1-bin.zip
sha256sum $W/dl/gradle-9.3.1-bin.zip   # must be b266d5ff6b90eada6dc3b20cb090e3731302e553a27c5d3e4df1f0d76beaff06
python -m zipfile -e $W/dl/gradle-9.3.1-bin.zip $W/tools/
```

The checksum is the one in VLC's `buildsystem/compile.sh`.

## 4. Source and patch

```bash
git -c core.autocrlf=false clone --depth 1 --branch 3.7.2 https://code.videolan.org/videolan/vlc-android.git $W/src
cd $W/src
git apply /path/to/patches/0001-player-accept-uri-in-subtitles_location.patch
```

Windows Git turns files into CRLF by default. The patch uses LF, and `git apply` then fails with
"patch does not apply". `core.autocrlf=false` avoids that.

Two more setup lines:

```bash
mkdir -p libvlcjni/libvlc     # settings.gradle includes it; release builds use Maven, so it stays empty
printf 'sdk.dir=C:/work/vlc-build/android-sdk\n' > local.properties
```

**Use forward slashes in `local.properties`.** Java reads a single backslash there as an escape and
the build stops with "The filename, directory name, or volume label syntax is incorrect".

## 5. Signing key (yours, keep it private)

```bash
mkdir -p $W/keys
$JAVA_HOME/bin/keytool -genkeypair -keystore $W/keys/mine.jks -storetype PKCS12 -alias mine \
  -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=My VLC build"
```

Use the same key for every later build. Android installs an update only if the signature matches.
Never publish the `.jks` file or its password.

## 6. Build

```bash
export ANDROID_HOME=$W/android-sdk ANDROID_SDK_ROOT=$W/android-sdk
export PASSWORD_KEYSTORE="the password you chose"
export VLC_OPEN_SUBTITLES_API_KEY="your own OpenSubtitles API key"   # see the warning below
$W/tools/gradle-9.3.1/bin/gradle.bat --console=plain \
  -PkeyStoreFile=$W/keys/mine.jks -Pstorealias=mine \
  :application:app:assembleSignedRelease
```

**Warning: the OpenSubtitles key.** VLC's "download subtitles" search needs an OpenSubtitles API key
that is fixed into the app at build time (`application/resources/build.gradle` reads the environment
variable `VLC_OPEN_SUBTITLES_API_KEY`, or the Gradle property `vlc_open_subtitles_api_key`). Official
VLC builds contain VideoLAN's key. **Your build does not.** Without a key the build still succeeds, but
VLC shows "OpenSubtitles is currently unavailable" when you search. The API answers HTTP 403
("You cannot consume this service") to a blank key. Make your own free key in your OpenSubtitles account
(API consumers). Do not copy VideoLAN's key out of an official APK: it is not yours to use.
The first build in this project had no key, and the search broke.

Output: `application/app/build/outputs/apk/signedRelease/VLC-Android-3.7.2-all.apk`
(a universal APK, about 120 MB). `apksigner verify --print-certs` shows your key.
The package name is `org.videolan.vlc`.

## 7. Install on an Android TV

Turn on Developer options and USB / Network debugging on the device.

```bash
adb connect <device-ip>:5555         # approve the box on the TV
adb uninstall org.videolan.vlc       # needed: different signature. Resets VLC's settings.
adb install VLC-Android-3.7.2-all.apk
```

To go back: `adb uninstall org.videolan.vlc`, then install VLC from the Play Store again.

## Another VLC version

The patch fits the `3.7.2` tag and `master` of October 2026. For another tag, apply it by hand: the
change is one function in
`application/vlc-android/src/org/videolan/vlc/media/PlayerController.kt`.

Copyright (C) 2026 cnghockey. GPL-2.0-or-later (see the repository's `LICENSE`).
