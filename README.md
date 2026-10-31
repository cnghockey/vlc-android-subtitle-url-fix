# VLC for Android as an external player: subtitle addresses and the subtitle search name

Three problems appear with VLC for Android on an NVIDIA SHIELD TV, started by an app such as **Jellyfin for Android TV**:

1. VLC **ignores a subtitle** that the app gives it as a web address (`http://…`, `https://…`).
2. VLC's **subtitle search** opens with the wrong name, and the Season and Episode boxes are empty.
3. VLC's **Match Display Frame Rate** setting does nothing: a 24 fps film plays at 59.94 Hz.

This repository has a small patch for each, the proof, and the steps to build and install them.

> **Not affiliated with VideoLAN.** "VLC" is a trademark of VideoLAN.
> This repository holds patches, not a release. No APK is published ([why](#why-no-apk)).
> The patches have not been submitted to VideoLAN. Anyone may submit them: see
> [`docs/upstream-merge-request.md`](docs/upstream-merge-request.md).

| Patch | What it changes | Status |
|---|---|---|
| [`0001`](patches/0001-player-accept-uri-in-subtitles_location.patch) | A subtitle given as a web address is loaded | Tested on a device |
| [`0002`](patches/0002-subtitle-search-reads-show-season-episode-from-filename.patch) | The subtitle search reads show, season and episode from the file name | Tested on a device: Name, Season and Episode were filled correctly |

| [`0003`](patches/0003-opensubtitles-send-the-build-time-api-key-as-given.patch) | A self-built VLC sends your own OpenSubtitles API key as it is. **Needed** for the subtitle search to work in your own build ([why](docs/BUILD-WINDOWS.md#6-build)) | Tested on a device: the subtitle search returns results |

| [`0004`](patches/0004-frame-rate-match-on-android-11-uses-the-display-mode.patch) | On Android 11, "Match Display Frame Rate" also asks for a display mode, and applies it | Tested on a device: the screen went to 24.000 Hz for a 24 fps film |

Apply them in this order. They apply cleanly to VLC for Android `3.7.2`, and the result is the code that was built.

## What Jellyfin for Android TV sends VLC

Read from the app's source (version 0.19.10, `ExternalPlayerActivity.kt`) and from Jellyfin's own database:

| Intent extra | What it holds |
|---|---|
| `title` | The episode name plus `S3E2`. **No show name.** |
| `filename` | The file name from the server's path (see the note below). VLC ignores it. |
| `subtitles_location` | The web address of the **first** separate subtitle file. One subtitle only. |

- **Which subtitle is first:** Jellyfin numbers separate subtitle files in file-name order. So `….eng.srt` comes
  before `….fra.srt`, and a video with both an English and a French file gets the English one. In Jellyfin's
  database, all six videos that had two separate files follow file-name order. Four of them were an English
  and a French pair.
- **The file name:** the app takes it with `File(path).name`. When the server runs Windows, the path has
  backslashes, and on Android that call keeps the whole path. This comes from reading the code. It was not
  observed on a device. Patch 0002 keeps only the last part, so it works either way.

## Problem 1: the subtitle web address is ignored

VLC issue [#1904](https://code.videolan.org/videolan/vlc-android/-/issues/1904) reports this since 2017.
It is still open.

**The cause**

1. The app sends `subtitles_location = "http://server/…/Stream.srt"`.
2. `VideoPlayerActivity` reads it as a `String` and calls `service.addSubtitleTrack(path, true)`
   (in `loadMedia`, and again on `MediaPlayer.Event.Opening`).
3. That reaches `MediaPlayer.addSlave(int type, String path, boolean select)` in libvlcjni.
   Its documentation says `@param path a local path`. The code is
   `addSlave(type, Uri.fromFile(new File(path)), select)`.
4. An `http://` string becomes a local path that does not exist.
   libvlc cannot open it. VLC drops the subtitle.

Checked in VLC for Android `3.7.2` and `master` (October 2026), and in libvlcjni `master`.

**Patch 0001** changes one function, `PlayerController.addSubtitleTrack(path: String, select: Boolean)`.
If the path contains `://`, it goes to libvlc as a `Uri`. A normal local path takes the old route.

```kotlin
fun addSubtitleTrack(path: String, select: Boolean): Boolean =
    if (path.contains("://")) mediaplayer.addSlave(IMedia.Slave.Type.Subtitle, path.toUri(), select)
    else mediaplayer.addSlave(IMedia.Slave.Type.Subtitle, path, select)
```

### Proof for patch 0001

**1. libvlc test (desktop VLC 3.0.24).** Same engine and same `add_slave` call as Android VLC.
Run it yourself: [`test/libvlc_add_slave_test.py`](test/libvlc_add_slave_test.py).
The video has 3 embedded subtitle tracks (the list shows 4 entries: "Disable" and the 3 tracks).
The subtitle comes from a web server.

| What is given to `add_slave` | Subtitle tracks | New track? | Selected track |
|---|---|---|---|
| `PATH` — `file:///http:/host/x.srt` (what the String overload builds) | 4 → 4 | no | an embedded track |
| `URI` — `http://host/x.srt` (what the patch does) | 4 → 5 | yes | the new track |
| `FILE` — a real local copy (control) | 4 → 5 | yes | the new track |

**2. Live test on a device.** Patched VLC 3.7.2 on an NVIDIA SHIELD (Android TV 11), started by
Jellyfin for Android TV 0.19.10. The subtitle appeared by itself. The device log (server address and
ids replaced):

```
ExternalPlayerActivity: Starting item <id> from 0s with 1 external subtitles: http://<server>:8096/Videos/<id>/stream?...
libvlc input: loading spu-es slave: http://<server>:8096/Videos/<id>/<id>/Subtitles/0/Stream.srt?...
GET /Videos/<id>/<id>/Subtitles/0/Stream.srt?copyTimestamps=false&addVttTimeMap=false&startPositionTicks=0 HTTP/1.1
libvlc decoder: using spu decoder module "subsdec"
```

No "before" log of the unpatched app was recorded on the device. The "before" evidence is test 1
and the code above.

## Problem 2: the subtitle search opens with the wrong name

VLC's search window fills **Name** from the `title` extra: `Episode Title S3E2`, with no show name.
VLC never fills **Season** or **Episode**: only text you type sets them. A streamed video is not a local
file, so VLC cannot compute a file hash for it. It searches by that one name alone, and the results
are poor. The app also sends the real file name in `filename`. VLC reads the code path for `title` only.

**Patch 0002** does three things:

- The player keeps the `filename` extra.
- A new helper, `EpisodeGuess`, reads show, season and episode from a name such as
  `Show Name S03E02 Episode Title (1080p).mkv`, `Show.Name.2021.S03E02.mkv` or `Show Name 3x02`.
  Only the last part of a path is used. A film, or a name with no season and episode, gives nothing,
  and VLC behaves as before.
- The search window opens with Name = `Show Name`, Season = `3`, Episode = `2`, and the first search
  uses them.

**Test status for patch 0002**

- It compiled into the same VLC 3.7.2 release build as patch 0001.
- The name rules were tried on 15 file names, including a full Windows path, in a Python copy of the same
  regular expressions. All gave the expected result.
- A Kotlin unit test was written but has **not been run**, so it is not in the patch.
- It was checked on a device (NVIDIA SHIELD, Jellyfin for Android TV 0.19.10): the search window opened
  with the right Name, Season and Episode. One device, one app.

## Problem 3: "Match Display Frame Rate" does nothing

VLC has a setting, **Settings > Video > Match Display Frame Rate**. It is off by default. It should switch the
TV to the frame rate of the film: 24 Hz for a 24 fps film. Without it, the SHIELD keeps 59.94 Hz and a 24 fps
film shows an uneven frame rhythm.

**The cause**

1. On Android 11, VLC asks for the frame rate with one call only: `Surface.setFrameRate()`
   (`FrameRateManager.setFrameRateR`).
2. The SHIELD TV firmware (Android 11) switches that call off. `getprop ro.vendor.surface_flinger.use_frame_rate_api`
   answers `false`. The call does nothing.
3. VLC has an older route for Android 6 to 10: it asks for a display mode (`preferredDisplayModeId`). It is not used on
   Android 11. It also changes the window settings in place (`window.attributes.preferredDisplayModeId = …`) and never
   tells Android, so the change may never reach the display.

**Patch 0004** does two things: on Android 11 it also uses the older route, and it applies the mode with
`window.attributes = window.attributes.apply { preferredDisplayModeId = … }`.

### Proof for patch 0004

NVIDIA SHIELD TV, Android 11, VLC `3.7.2`, one HEVC film at 24 fps, measured with `adb shell dumpsys` while the film played.
The setting was on in both cases.

| | Before the patch | With the patch |
|---|---|---|
| Screen mode while the film plays | 3840x2160 at 59.94 Hz, for the whole 133-second recording | 3840x2160 at 24.000 Hz (mode 52) |
| Display mode asked for by the app | none | mode 52 |
| Time the screen has spent at 24 Hz since boot | 1.8 s | 22.9 s at the check, and growing |

- VLC ignores videos shorter than 5 minutes (its own rule in `setFrameRateM`).
- The TV may go black for 1 to 2 seconds when the mode changes. VLC resumes by itself.
- The modes come from the TV. The tested TV offered no 25 Hz or 50 Hz mode, so 25 fps video is not matched.
- Tested on one device, one TV and one file. On another Android 11 device, the patch makes VLC use both routes.
  Both ask for the same rate.

## Build and install

[`docs/BUILD-WINDOWS.md`](docs/BUILD-WINDOWS.md) lists the steps that produced the APK on Windows 11.
The build takes about 15 minutes. It needs no native compile: the release build uses the prebuilt
libvlc from Maven. Apply the patches in step 4. Patch 0003 is not optional if you want the subtitle search.

**Warning before you install.** Your build has a different signature from the Play Store VLC.
Android will not install it over the top. You must uninstall the Play Store VLC first. That resets
VLC's own settings. After that, the Play Store no longer updates VLC for you. Later builds signed with
the same key do update in place and keep your settings.

## What was and was not tested

- Tested: VLC `3.7.2` built on Windows 11 (Gradle 9.3.1, JDK 21, Android SDK 36). One device
  (NVIDIA SHIELD, Android 11, arm64). One app (Jellyfin for Android TV 0.19.10). One subtitle URL
  (an `http://` address on a local network, no login needed). This covers patch 0001. On the same
  device and app, patch 0002 filled Name, Season and Episode correctly, and with patch 0003 and a
  key of its own the subtitle search returned results. Patch 0004 switched the screen to 24.000 Hz for a
  24 fps film.
- Not tested: `https://`, `smb://`, `ftp://`, a subtitle that needs a login, other devices, other apps,
  and VLC 4 / `master`.
- Known quirk: VLC adds the extra twice (in `loadMedia` and on `Opening`). That already happens for
  local paths. The subtitle menu may list the track twice. Not checked.
- The intent extra carries one subtitle only. That is VLC's design.
- A build without your own OpenSubtitles API key has a broken "download subtitles" search, and so does a
  build with a key but without patch 0003 ([details](docs/BUILD-WINDOWS.md#6-build)). Official VLC builds
  carry VideoLAN's key. Yours does not.
- Installing a build with a different signature resets VLC's settings, including "Preferred subtitle
  language". Set it again, or no subtitle track is chosen for you.

## Why no APK

A binary signed with one person's key, named "VLC", is a modified VLC under VideoLAN's name. Build
your own from the patches. Do not trust an APK from anyone, including this repository's author.

## Author

[cnghockey](https://github.com/cnghockey)

## License

GPL-2.0-or-later, the same as VLC for Android (see [`LICENSE`](LICENSE), copied from the VLC for
Android repository).

Copyright (C) 2026 cnghockey, for the test script, the build guide and this README.
The patches change VLC for Android source files, and patch 0002 adds a new file under the same license.
VLC's copyright stays with the VLC authors.

Developed with Claude Code (Anthropic) under the author's direction, and tested on the author's own device.
