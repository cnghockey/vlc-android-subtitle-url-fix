# VLC for Android: subtitle web addresses in `subtitles_location`

VLC for Android ignores a subtitle that an app gives it as a web address (`http://…`, `https://…`).
This repository has a 7-line fix, the proof, and the steps to build and install it.

> **Not affiliated with VideoLAN.** "VLC" is a trademark of VideoLAN.
> This repository holds a patch, not a release. No APK is published ([why](#why-no-apk)).
> The patch has not been submitted to VideoLAN. Anyone may submit it: see
> [`docs/upstream-merge-request.md`](docs/upstream-merge-request.md).

## Who this affects

Any app that starts VLC with the `subtitles_location` intent extra set to a URL.
Example: **Jellyfin for Android TV** with VLC as the external player. The video plays.
VLC shows no subtitle, and it shows no error.

VLC issue [#1904](https://code.videolan.org/videolan/vlc-android/-/issues/1904) reports this
since 2017. It is still open.

## The cause

1. The app sends `subtitles_location = "http://server/…/Stream.srt"`.
2. `VideoPlayerActivity` reads it as a `String` and calls `service.addSubtitleTrack(path, true)`
   (in `loadMedia`, and again on `MediaPlayer.Event.Opening`).
3. That reaches `MediaPlayer.addSlave(int type, String path, boolean select)` in libvlcjni.
   Its documentation says `@param path a local path`. The code is
   `addSlave(type, Uri.fromFile(new File(path)), select)`.
4. An `http://` string becomes a local path that does not exist.
   libvlc cannot open it. VLC drops the subtitle.

Checked in VLC for Android `3.7.2` and `master` (October 2026), and in libvlcjni `master`.

## The fix

[`patches/0001-player-accept-uri-in-subtitles_location.patch`](patches/0001-player-accept-uri-in-subtitles_location.patch)
changes one function, `PlayerController.addSubtitleTrack(path: String, select: Boolean)`.
If the path contains `://`, it goes to libvlc as a `Uri`. A normal local path takes the old route.

```kotlin
fun addSubtitleTrack(path: String, select: Boolean): Boolean =
    if (path.contains("://")) mediaplayer.addSlave(IMedia.Slave.Type.Subtitle, path.toUri(), select)
    else mediaplayer.addSlave(IMedia.Slave.Type.Subtitle, path, select)
```

## Proof

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

## Build and install

[`docs/BUILD-WINDOWS.md`](docs/BUILD-WINDOWS.md) lists the steps that produced the APK on Windows 11.
The build takes about 15 minutes. It needs no native compile: the release build uses the prebuilt
libvlc from Maven.

**Warning before you install.** Your build has a different signature from the Play Store VLC.
Android will not install it over the top. You must uninstall the Play Store VLC first. That resets
VLC's own settings. After that, the Play Store no longer updates VLC for you.

## What was and was not tested

- Tested: VLC `3.7.2` built on Windows 11 (Gradle 9.3.1, JDK 21, Android SDK 36). One device
  (NVIDIA SHIELD, Android 11, arm64). One app (Jellyfin for Android TV 0.19.10). One subtitle URL
  (an `http://` address on a local network, no login needed).
- Not tested: `https://`, `smb://`, `ftp://`, a subtitle that needs a login, other devices, other apps,
  VLC 4 / `master`.
- Known quirk: VLC adds the extra twice (in `loadMedia` and on `Opening`). That already happens for
  local paths. The subtitle menu may list the track twice. Not checked.
- The intent extra carries one subtitle only. That is VLC's design.
- A build without your own OpenSubtitles API key has a broken "download subtitles" search
  ([details](docs/BUILD-WINDOWS.md#6-build)). Official VLC builds carry VideoLAN's key. Yours does not.
- Installing a build with a different signature resets VLC's settings, including "Preferred subtitle
  language". Set it again, or no subtitle track is chosen for you.

## Why no APK

A binary signed with one person's key, named "VLC", is a modified VLC under VideoLAN's name. Build
your own from the patch. Do not trust an APK from anyone, including this repository's author.

## Author

[cnghockey](https://github.com/cnghockey)

## License

GPL-2.0-or-later, the same as VLC for Android (see [`LICENSE`](LICENSE), copied from the VLC for
Android repository).

Copyright (C) 2026 cnghockey, for the test script, the build guide and this README.
The patch changes a VLC for Android source file. VLC's copyright stays with the VLC authors.

Developed with Claude Code (Anthropic) under the author's direction, and tested on the author's own device.
