# -*- coding: utf-8 -*-
"""
ffmpeg probe
"""
import subprocess
from typing import NamedTuple


class FFProbeResult(NamedTuple):
    """ffmpeg probe result"""

    return_code: int
    json: str
    error: str


def ffprobe(file_path) -> FFProbeResult:
    """return ffprobe in json format"""
    command_array = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        file_path,
    ]
    try:
        result = subprocess.run(
            command_array,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf8",
            check=True,
        )
    except (UnicodeDecodeError, subprocess.CalledProcessError) as _e:
        return FFProbeResult(return_code=1212, json="", error=str(_e))
    return FFProbeResult(
        return_code=result.returncode, json=result.stdout, error=result.stderr
    )


def smart_probe(ffmpeg_json):
    """add smart infos to original ffmpeg probe"""
    streams = ffmpeg_json.get("streams", [])
    dstreams = {"video": [], "audio": [], "subtitle": []}
    screen_size = ""
    for stream in streams:
        language = (
            f'({stream.get("tags").get("language")})'
            if (stream.get("tags") and stream.get("tags").get("language"))
            else ""
        )
        codec_type = stream.get("codec_type", "unknown")
        if codec_type in ["video", "audio", "subtitle"]:
            dstreams[codec_type].append(f'{stream.get("codec_name")} {language}')
        if codec_type == "video":
            screen_size = f'{stream.get("width", "?")}x{stream.get("height", "?")}'
    codecs = []
    for codec_type in ["video", "audio", "subtitle"]:
        if dstreams[codec_type]:
            codecs.append(codec_type)
    streams = [
        f"{codec_type}: {', '.join(dstreams[codec_type])}" for codec_type in codecs
    ]
    streams = " | ".join(streams)
    ffmpeg_json["smart_streams"] = streams
    ffmpeg_json["format"]["screen_size"] = screen_size
    # fields can be missing (damaged video file ?): force it
    ffmpeg_json["format"]["bit_rate"] = ffmpeg_json["format"].get("bit_rate", 0)
    ffmpeg_json["format"]["duration"] = ffmpeg_json["format"].get("duration", 0)
    # duplicate title in format field
    ffmpeg_json["title"] = (
        ffmpeg_json["format"]["tags"]["title"]
        if ffmpeg_json["format"].get("tags")
        and ffmpeg_json["format"]["tags"].get("title")
        else ""
    )
    return ffmpeg_json
