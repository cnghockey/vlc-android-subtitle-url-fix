# Merge request text for code.videolan.org/videolan/vlc-android

**Title:** Player: let the `subtitles_location` intent extra take http(s):// and other URIs

Fixes #1904.

## Problem

The `subtitles_location` intent extra is documented as "location of a subtitles file to load".
Media-server apps send a URL in it. Jellyfin for Android TV does this
(`VlcExternalPlayerApi`: `intent.putExtra("subtitles_location", url)`).
VLC then drops the subtitle and shows no error.

Cause: `VideoPlayerActivity` calls `service.addSubtitleTrack(path: String, true)`.
That reaches `MediaPlayer.addSlave(int type, String path, boolean select)` in libvlcjni,
which is documented "@param path a local path" and does `Uri.fromFile(new File(path))`.
An `http://host/x.srt` string becomes the local path `/http:/host/x.srt`. libvlc cannot open it.

## Change

`PlayerController.addSubtitleTrack(path: String, select)`: when `path` contains `://`,
pass it to the `Uri` overload of `addSlave()`. A plain local path takes the old route.
One function, no new dependency. `Uri` and `toUri()` are already imported in the file.

## Test

I ran libvlc 3.0.24 (desktop) with `--no-sub-autodetect-file`, on an MKV that has
3 embedded subtitle tracks, and called `libvlc_media_player_add_slave` with the
same subtitle served over HTTP:

| Argument to add_slave | Subtitle tracks | New track | Selected track |
|---|---|---|---|
| `file:///http:/host/x.srt` (what the String overload builds) | 4 -> 4 | no | the embedded default track |
| `http://host/x.srt` (the URI route this MR uses) | 4 -> 5 | yes | the new track |
| `file:///C:/x.srt` (control, a real local copy) | 4 -> 5 | yes | the new track |

## Not tested

I did not build or run the Android app. The Android-only part is `VLCUtil.encodeVLCUri(uri)`
inside `addSlave(int, Uri, boolean)`, which already serves the existing `Uri` overload.
`VideoPlayerActivity` still adds the extra twice (in `loadMedia` and on `Opening`), as it
does for local paths today. This MR does not change that.
