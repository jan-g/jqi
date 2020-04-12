"""Mix-ins for the Editor"""
import asyncio
import json
from prompt_toolkit.completion import Completer, CompleteEvent, Completion
from .completion import completer
from .parser import Token, Field, String


class Refresh:
    def __init__(self, *args, **kwargs):
        self._counting = False
        self._old_pattern = None
        self._get_pattern = None
        self._refresh = None
        self._task = None

    def create_refresh_task(self, refresh=None, get_pattern=None):
        self._refresh = refresh
        self._get_pattern = get_pattern
        self._task = asyncio.get_event_loop().create_task(self._tick())
        return self._task

    def cancel_refresh_task(self):
        self._task.cancel()

    def disable_refresh(self):
        # Turn off the display update
        self._counting = False
        self._old_pattern = self._get_pattern()

    async def _tick(self):
        unchanged_count = 0
        self._counting = False
        self._old_pattern = self._get_pattern()
        while True:
            pattern = self._get_pattern()
            if pattern != self._old_pattern:
                self._old_pattern = pattern
                unchanged_count = 0
                self._counting = True
            if self._counting:
                unchanged_count += 1
            if unchanged_count > 2:
                self._counting = False
                unchanged_count = 0
                try:
                    self._refresh()
                except Exception as e:
                    print("error:", e)
            await asyncio.sleep(0.3)


class JQCompleter(Completer):
    def __init__(self, object_source=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._object_source = object_source

    def get_completions(self, doc, event):
        expr = doc.text
        pos = doc.cursor_position
        try:
            comp = completer(expr, pos)
            completions, (start, end) = comp(self._object_source())
            return (Completion(text=_expand_completion(c), start_position=start - pos)
                    for c in completions)
        except Exception as e:
            print(e)
            raise


def _expand_completion(c):
    if isinstance(c, (Token, Field)):
        return c
    elif isinstance(c, String):
        return json.dumps(c)
    else:
        raise NotImplementedError("{} = {}".format(c, type(c)))
