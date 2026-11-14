"""Verified offline copies of the nine original WeChat game-result sprites."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from wx4.game_emojis import result
from .paths import is_link

ASSETS=Path(__file__).resolve().parents[1]/'ui'


@lru_cache(maxsize=1)
def checksums():
    try:
        values=json.loads((ASSETS/'wechat-game-emojis.json').read_text('utf-8'))
        return values if isinstance(values,dict) else {}
    except (OSError,ValueError):return {}


def game_image(game):
    if not isinstance(game,dict):return None
    canonical=result(game.get('type'),game.get('value'))
    if canonical is None:return None
    digest=canonical['md5'];path=ASSETS/'wechat-game-emojis'/(digest+'.png')
    try:
        if is_link(path) or path.stat().st_size>128*1024:return None
        blob=path.read_bytes()
    except OSError:return None
    if hashlib.sha256(blob).hexdigest()!=checksums().get(digest):return None
    return blob
