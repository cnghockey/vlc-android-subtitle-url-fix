#!/usr/bin/env python3
# Copyright (C) 2026 cnghockey. GPL-2.0-or-later. See LICENSE in the repository root.
"""Show why VLC for Android drops a subtitle given as a web address, and why the fix works.

VLC for Android adds the `subtitles_location` subtitle with libvlc's add_slave().
The String overload of that call treats its argument as a LOCAL PATH
(`Uri.fromFile(new File(path))`). This script gives libvlc the same subtitle three ways:

  PATH  the string an http URL turns into on Android: file:///http:/host/x.srt
  URI   the http URL itself (what the patch does)
  FILE  a real local copy of the subtitle (control: shows the test can see a working subtitle)

Each case runs in its own process, with a fresh libvlc, and prints:
  subtitle tracks before / after, and which track is selected.

Needs: desktop VLC (it brings libvlc) and `pip install python-vlc`.
Desktop libvlc is the same engine and the same add_slave call that Android VLC uses.

  python libvlc_add_slave_test.py VIDEO_FILE http://server/path/subtitle.srt
"""
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

WINDOWS_VLC = r"C:\Program Files\VideoLAN\VLC"


def child(label, slave_uri, media):
    if os.name == "nt" and os.path.isdir(WINDOWS_VLC):
        os.add_dll_directory(WINDOWS_VLC)
        os.environ.setdefault("PYTHON_VLC_LIB_PATH", os.path.join(WINDOWS_VLC, "libvlc.dll"))
        os.environ.setdefault("PYTHON_VLC_MODULE_PATH", os.path.join(WINDOWS_VLC, "plugins"))
    import vlc

    # --no-sub-autodetect-file: desktop VLC would otherwise find a .srt that sits beside
    # the video. Android VLC does not do that for web streams, and it would hide the result.
    inst = vlc.Instance("--vout=dummy", "--aout=dummy", "--quiet", "--no-video-title-show",
                        "--no-osd", "--no-sub-autodetect-file")
    player = inst.media_player_new()
    player.set_media(inst.media_new(media))
    player.play()
    for _ in range(60):  # wait until the demuxer has listed its tracks
        time.sleep(0.2)
        if player.video_get_spu_count() > 0 or player.get_state() == vlc.State.Error:
            break

    def tracks():
        return [(i, n.decode(errors="replace")) for i, n in (player.video_get_spu_description() or [])]

    before = tracks()
    player.add_slave(vlc.MediaSlaveType.subtitle, slave_uri, True)  # select=True, as VLC does
    time.sleep(4)  # let libvlc fetch and parse the slave
    after = tracks()
    new = [t for t in after if t not in before]
    print(f"{label:<5} tracks {len(before)} -> {len(after)}   new track: {'yes ' + str(new[0]) if new else 'NO'}   "
          f"selected id: {player.video_get_spu()}")
    player.stop()


def main():
    if len(sys.argv) >= 5 and sys.argv[1] == "--child":
        child(sys.argv[2], sys.argv[3], sys.argv[4])
        return
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    media, url = sys.argv[1], sys.argv[2]
    scheme_end = url.index("://") + 3
    as_path = "file:///" + url[:scheme_end - 2].rstrip("/") + "/" + url[scheme_end:]  # file:///http:/host/...
    with tempfile.TemporaryDirectory() as tmp:
        local = os.path.join(tmp, "subtitle.srt")
        urllib.request.urlretrieve(url, local)
        cases = [("PATH", as_path), ("URI", url), ("FILE", "file:///" + local.replace("\\", "/"))]
        for label, uri in cases:
            subprocess.run([sys.executable, __file__, "--child", label, uri, media], check=False)


if __name__ == "__main__":
    main()
