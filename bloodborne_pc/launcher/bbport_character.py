"""Parse Bloodborne character data from save files for launcher display."""

from datetime import datetime
import json
import re
from pathlib import Path

_TROPHY_METADATA = None

GRADE_NAMES = {'P': 'Platinum', 'G': 'Gold', 'S': 'Silver', 'B': 'Bronze'}


def _get_trophy_metadata(save_folder=None):
    global _TROPHY_METADATA
    if _TROPHY_METADATA is not None:
        return _TROPHY_METADATA

    candidates = [
        Path(__file__).resolve().parent / 'assets' / 'trophies' / 'trophies.json',
        Path(save_folder) / 'trophy_cache' / 'metadata.json' if save_folder else None,
    ]
    for p in candidates:
        if p and p.is_file():
            try:
                data = json.loads(p.read_text(encoding='utf-8', errors='ignore'))
                entries = data.get('entries', [])
                if entries:
                    _TROPHY_METADATA = entries
                    return _TROPHY_METADATA
            except Exception:
                pass
    return []


def _categorize_trophy(entry):
    desc = entry.get('description', '')
    name = entry.get('name', '')
    if 'Defeat' in desc:
        return 'Boss'
    if 'Chalice' in name or 'Labyrinth' in desc or 'Queen' in name:
        return 'Chalice'
    if any(k in desc for k in ['Acquire', 'weapon', 'Rune', 'gem', 'tools']):
        return 'Equipment'
    return 'Story'


def _load_trophy_data(save_folder):
    """Load trophy unlocks and detailed trophy metadata."""
    folder = Path(save_folder)
    unlocked_map = {}

    candidates = [
        folder / 'trophies.txt',
        folder / 'savedata' / 'trophies.txt',
        folder.parent / 'trophies.txt',
    ]
    for trophy_file in candidates:
        try:
            if trophy_file.is_file():
                for line in trophy_file.read_text(encoding='utf-8', errors='ignore').splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                        trophy_id = int(parts[0])
                        ts = int(parts[1])
                        if 0 <= trophy_id < 128:
                            try:
                                dt = datetime.fromtimestamp(ts)
                                unlocked_map[trophy_id] = dt.strftime('%b %d, %Y')
                            except Exception:
                                unlocked_map[trophy_id] = "Unlocked"
                if unlocked_map:
                    break
        except Exception:
            pass

    entries = _get_trophy_metadata(save_folder)
    all_trophies = []
    earned_trophies = []
    locked_trophies = []

    for e in entries:
        tid = e.get('id', 0)
        grade = e.get('grade', 'B')
        name = e.get('name', f'Trophy {tid}')
        desc = e.get('description', '').replace('\n', ' ').strip()
        icon_name = f'TROP{tid:03d}.PNG'
        is_unlocked = tid in unlocked_map
        unlocked_at = unlocked_map.get(tid, '')
        category = _categorize_trophy(e)

        item = {
            'id': tid,
            'name': name,
            'description': desc,
            'grade': grade,
            'grade_name': GRADE_NAMES.get(grade, 'Bronze'),
            'category': category,
            'icon': icon_name,
            'unlocked': is_unlocked,
            'unlocked_at': unlocked_at
        }
        all_trophies.append(item)
        if is_unlocked:
            earned_trophies.append(item)
        else:
            locked_trophies.append(item)

    total_count = len(entries) if entries else 40
    return len(unlocked_map), total_count, all_trophies, earned_trophies, locked_trophies


class CharacterData:
    """Extract character stats from Bloodborne userdata file."""

    def __init__(self):
        self.name = "Unknown"
        self.level = 0
        self.vitality = 0
        self.endurance = 0
        self.strength = 0
        self.skill = 0
        self.bloodtinge = 0
        self.arcane = 0
        self.blood_echoes = 0
        self.insight = 0
        self.deaths = 0
        self.play_time = 0
        self.bosses_defeated = 0
        self.trophies_earned = 0
        self.trophies_total = 40
        self.trophies = []
        self.earned_trophies = []
        self.locked_trophies = []
        self.valid = False

    @staticmethod
    def from_save_file(save_path):
        """Parse character data from a Bloodborne save file (userdata0000 - userdata0009)."""
        char = CharacterData()

        try:
            save_path = Path(save_path)
            if not save_path.exists():
                return char

            data = save_path.read_bytes()
            # Valid character slot files are ~1.25 MB (0x140000); userdata0010 is system save (0x40000)
            if len(data) < 0x20000:
                return char

            # Locate inventory start marker: 0x40, 0xf0, 0xff, 0xff
            inv_marker = data.find(bytes([0x40, 0xf0, 0xff, 0xff]))
            if inv_marker != -1 and inv_marker >= 469:
                base = inv_marker - 469
            else:
                # Fallback: search for FACE appearance marker
                face_pos = data.find(b'FACE', 0xF000)
                if face_pos != -1 and face_pos >= 34028 + 469:
                    base = face_pos - 34028 - 469
                else:
                    return char

            if base < 150 or base + 33 > len(data):
                return char

            # Character name is stored as UTF-16LE at base + 1 (2-byte aligned)
            try:
                name_bytes = data[base + 1 : base + 33]
                decoded_name = name_bytes.decode('utf-16le', errors='ignore').split('\x00')[0].strip()
                char.name = decoded_name if decoded_name else "Hunter"
            except Exception:
                char.name = "Hunter"

            # Level and stats relative to base
            try:
                char.level = int.from_bytes(data[base - 23 : base - 19], 'little')
                char.blood_echoes = int.from_bytes(data[base - 19 : base - 15], 'little')
                char.play_time = int.from_bytes(data[base - 15 : base - 11], 'little')
                char.insight = int.from_bytes(data[base - 35 : base - 31], 'little')

                # Attributes (1 byte each)
                char.vitality = data[base - 103]
                char.endurance = data[base - 95]
                char.strength = data[base - 79]
                char.skill = data[base - 71]
                char.bloodtinge = data[base - 63]
                char.arcane = data[base - 55]
            except Exception:
                pass

            # Death count: AOB marker b'\x03\x00\x00\x00\x05\x00\x01\x00' + 360
            try:
                aob = data.find(bytes([0x03, 0x00, 0x00, 0x00, 0x05, 0x00, 0x01, 0x00]))
                if aob != -1 and aob + 364 <= len(data):
                    char.deaths = int.from_bytes(data[aob + 360 : aob + 364], 'little')
            except Exception:
                pass

            # Validation: level must be reasonable (1-594) and vitality between 1 and 99
            if 0 < char.level <= 594 and 0 < char.vitality <= 99:
                char.valid = True

            return char

        except Exception as e:
            print(f"Error parsing character data: {e}")
            return char

    def play_time_formatted(self):
        """Format play time as human-readable string."""
        hours = self.play_time // 3600
        minutes = (self.play_time % 3600) // 60
        return f"{hours}h {minutes}m"

    def to_dict(self):
        """Convert to dictionary for QML display."""
        total_p = sum(1 for t in self.trophies if t.get('grade') == 'P')
        earned_p = sum(1 for t in self.earned_trophies if t.get('grade') == 'P')
        total_g = sum(1 for t in self.trophies if t.get('grade') == 'G')
        earned_g = sum(1 for t in self.earned_trophies if t.get('grade') == 'G')
        total_s = sum(1 for t in self.trophies if t.get('grade') == 'S')
        earned_s = sum(1 for t in self.earned_trophies if t.get('grade') == 'S')
        total_b = sum(1 for t in self.trophies if t.get('grade') == 'B')
        earned_b = sum(1 for t in self.earned_trophies if t.get('grade') == 'B')

        total_boss = sum(1 for t in self.trophies if t.get('category') == 'Boss')
        earned_boss = sum(1 for t in self.earned_trophies if t.get('category') == 'Boss')
        total_story = sum(1 for t in self.trophies if t.get('category') == 'Story')
        earned_story = sum(1 for t in self.earned_trophies if t.get('category') == 'Story')
        total_equip = sum(1 for t in self.trophies if t.get('category') == 'Equipment')
        earned_equip = sum(1 for t in self.earned_trophies if t.get('category') == 'Equipment')
        total_chalice = sum(1 for t in self.trophies if t.get('category') == 'Chalice')
        earned_chalice = sum(1 for t in self.earned_trophies if t.get('category') == 'Chalice')

        total = max(1, len(self.trophies))
        pct = round((len(self.earned_trophies) / total) * 100, 1)

        return {
            'name': self.name,
            'level': self.level,
            'vitality': self.vitality,
            'endurance': self.endurance,
            'strength': self.strength,
            'skill': self.skill,
            'bloodtinge': self.bloodtinge,
            'arcane': self.arcane,
            'blood_echoes': self.blood_echoes,
            'insight': self.insight,
            'deaths': self.deaths,
            'play_time': self.play_time_formatted(),
            'bosses_defeated': self.bosses_defeated if self.bosses_defeated else earned_boss,
            'trophies_earned': self.trophies_earned,
            'trophies_total': self.trophies_total,
            'completion_pct': pct,
            'platinum_str': f"{earned_p}/{total_p}",
            'gold_str': f"{earned_g}/{total_g}",
            'silver_str': f"{earned_s}/{total_s}",
            'bronze_str': f"{earned_b}/{total_b}",
            'boss_count_str': f"{earned_boss}/{total_boss}",
            'story_count_str': f"{earned_story}/{total_story}",
            'equip_count_str': f"{earned_equip}/{total_equip}",
            'chalice_count_str': f"{earned_chalice}/{total_chalice}",
            'locked_total_count': len(self.locked_trophies),
            'locked_boss_count': total_boss - earned_boss,
            'locked_story_count': total_story - earned_story,
            'locked_equip_count': total_equip - earned_equip,
            'locked_chalice_count': total_chalice - earned_chalice,
            'trophies': self.trophies,
            'earned_trophies': self.earned_trophies,
            'locked_trophies': self.locked_trophies,
            'valid': self.valid
        }


def get_characters(save_folder, title_id=None):
    """Find and parse all characters in the save folder, including trophy unlocks."""
    characters = []
    folder = Path(save_folder)
    earned_count, total_count, all_trophies, earned_list, locked_list = _load_trophy_data(folder)

    # Search candidates for save directory
    candidates = []
    if (folder / 'savedata').is_dir():
        candidates.append(folder / 'savedata')
    if folder.is_dir():
        candidates.append(folder)

    # All known Bloodborne title IDs
    title_ids = [title_id] if title_id else [
        'CUSA00207', 'CUSA03173', 'CUSA00208', 'CUSA00299',
        'CUSA00900', 'CUSA01363', 'CUSA03014', 'CUSA03023',
        'CUSA01988', 'CUSA03179'
    ]

    # Only match character save slots userdata0000 - userdata0009 (exclude userdata0010 system settings)
    slot_pattern = re.compile(r'^userdata000[0-9]$')

    all_saves = []
    for save_root in candidates:
        for tid in title_ids:
            for pattern in (f'*/{tid}/SPRJ*/userdata*', f'{tid}/SPRJ*/userdata*', f'*/{tid}/*/userdata*'):
                for userdata in save_root.glob(pattern):
                    if userdata.is_file() and slot_pattern.match(userdata.name):
                        all_saves.append(userdata)
        for userdata in save_root.glob('SPRJ*/userdata*'):
            if userdata.is_file() and slot_pattern.match(userdata.name):
                all_saves.append(userdata)

    seen_paths = set()
    unique_saves = []
    for s in all_saves:
        try:
            rp = s.resolve()
            if rp not in seen_paths:
                seen_paths.add(rp)
                unique_saves.append(s)
        except Exception:
            if s not in seen_paths:
                seen_paths.add(s)
                unique_saves.append(s)

    # Sort by modification time, most recent first
    unique_saves.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)

    for userdata in unique_saves:
        char = CharacterData.from_save_file(userdata)
        if char.valid:
            char.trophies_earned = earned_count
            char.trophies_total = total_count
            char.trophies = all_trophies
            char.earned_trophies = earned_list
            char.locked_trophies = locked_list
            characters.append(char.to_dict())

    return characters
