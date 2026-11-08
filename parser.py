"""Read timestamped episodes without extracting ZIP members to disk."""
import logging
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

LOG = logging.getLogger(__name__)
FILE = re.compile(r"episode-(\d+).*\.txt$", re.I)
HEADER = re.compile(r"^\s*\*\*(.+?):\*\*\s*$", re.M)
SCENE = re.compile(r"^\s*SCENE\s+(\d+)\s*$", re.M | re.I)
TIME = r"(\d+:[0-5]\d(?:\.\d{1,2})?)"
SPAN = re.compile(r"^\s*Start:\s*\(" + TIME + r"\)\s*\|\s*End:\s*\(" + TIME + r"\)[ \t]*\r?$", re.M | re.I)


def ticks(value):
    minute, second = value.split(":")
    whole, _, fraction = second.partition(".")
    return int(minute) * 6000 + int(whole) * 100 + int(fraction.ljust(2, "0"))


def stamp(value):
    minute, rest = divmod(value, 6000)
    second, fraction = divmod(rest, 100)
    return f"{minute:02}:{second:02}.{fraction:02}"


@dataclass(frozen=True)
class Event:
    episode: int
    scene: int
    type: str
    speaker: str
    emotion: str
    start: int
    end: int
    text: str

    @property
    def start_sec(self):
        return self.start / 100

    @property
    def end_sec(self):
        return self.end / 100


@dataclass
class Episode:
    number: int
    logline: str
    continuity: str
    events: list[Event]
    end: int


def parse_episode(raw, number):
    preamble, marker, script = raw.partition("--- SCRIPT START ---")
    if not marker:
        LOG.warning("Episode %d has no script start marker", number)
        script = raw
    script = script.split("--- SCRIPT END ---", 1)[0]

    def metadata(name):
        match = re.search(r"^" + name + r":\s*([^\r\n]+)", preamble, re.M)
        return match[1].strip() if match else ""

    scenes = list(SCENE.finditer(script))
    events = []
    scene_end = 0
    for index, scene in enumerate(scenes):
        end = scenes[index + 1].start() if index + 1 < len(scenes) else len(script)
        body = script[scene.end():end]
        declared = re.search(r"^Scene end:\s*" + TIME, body, re.M | re.I)
        if declared:
            scene_end = max(scene_end, ticks(declared[1]))
        blocks = list(HEADER.finditer(body))
        for offset, block in enumerate(blocks):
            stop = blocks[offset + 1].start() if offset + 1 < len(blocks) else len(body)
            payload = body[block.end():stop]
            span = SPAN.match(payload)
            label = block[1].strip()
            if label.upper() in {"CAMERA", "ACTION", "SOUND FX"}:
                kind, speaker, emotion = label.upper(), "", ""
            else:
                character = re.fullmatch(r"(.+?)\s*\(([^()]*)\)", label)
                speaker, emotion = character.groups() if character else (label, "")
                kind = "DIALOGUE"
            content = payload[span.end():].strip() if span else ""
            if not span or not content or ticks(span[1]) >= ticks(span[2]):
                LOG.warning("Episode %d scene %s skipped malformed %s block", number, scene[1], label)
                continue
            events.append(Event(number, int(scene[1]), kind, speaker, emotion,
                                ticks(span[1]), ticks(span[2]), " ".join(content.split())))
    if not events:
        raise ValueError(f"Episode {number} has no valid timed events")
    events.sort(key=lambda event: (event.start, event.end))
    return Episode(number, metadata("EPISODE LOGLINE"), metadata("CONTINUITY NOTES"),
                   events, max(scene_end, max(event.end for event in events)))


def load_shows(source):
    source = Path(source)
    groups = defaultdict(dict)

    def add(relative, payload):
        match = FILE.fullmatch(relative.name)
        if not match or "__MACOSX" in relative.parts:
            return
        episodes = groups[str(relative.parent)]
        number = int(match[1])
        if number in episodes:
            raise ValueError(f"Duplicate episode {number} in {relative.parent}")
        try:
            episodes[number] = parse_episode(payload.decode("utf-8-sig"), number)
        except ValueError as error:
            LOG.warning("Skipped %s (%s)", relative, error)

    if source.is_dir():
        for path in sorted(source.rglob("*.txt")):
            if FILE.fullmatch(path.name):
                add(path.relative_to(source), path.read_bytes())
    elif source.is_file() and zipfile.is_zipfile(source):
        with zipfile.ZipFile(source) as archive:
            members = [item for item in archive.infolist()
                       if FILE.fullmatch(PurePosixPath(item.filename).name)]
            if sum(item.file_size for item in members) > 50_000_000:
                raise ValueError("Archive exceeds the 50 MB episode text limit")
            for item in members:
                add(PurePosixPath(item.filename), archive.read(item))
    else:
        raise ValueError("Input must be an episode folder or ZIP archive")
    shows = {name if name != "." else source.stem: dict(sorted(episodes.items()))
             for name, episodes in groups.items() if episodes}
    if not shows:
        raise ValueError("No valid episode-NNN*.txt files found")
    return shows
