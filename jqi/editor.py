"""Mix-ins for the Editor"""
import asyncio
import config_dir
import io
import json
from numbers import Number
from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.input.defaults import create_input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.layout.menus import CompletionsMenu
import re
import sh
import sys
import types
import yaml

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
    elif isinstance(c, (String, str, Number)):
        return json.dumps(c)
    else:
        raise NotImplementedError("{} = {}".format(c, type(c)))


class Editor(Refresh):
    def __init__(self, pattern=None, file=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file = file
        if pattern is None:
            pattern = "."
        self.pattern = pattern
        self.compact = False
        self.raw = False
        self.input = "{}"

        self.kb = self.construct_key_bindings()

        self.app = None
        self.buf = None
        self.status = None
        self.result = None
        self.cache = {Editor.CACHE_ORIGINAL_OBJECT: None}
        self.error = None
        self.vbar = self.completions = None
        self.load()
        self.layout()
        self.mode = Editor.CACHE_JQ_LINES

    CACHE_BYTES = 'BYTES'
    CACHE_OBJECT = 'OBJECT'
    CACHE_ORIGINAL_OBJECT = 'ORIGINAL_OBJECT'
    CACHE_JQ_LINES = 'LINES'
    CACHE_YAML_LINES = 'YAML'

    def construct_key_bindings(self):
        bindings = [
            {"keys": ["c-x"], "args": dict(eager=True), "func": "exit"},
            {"keys": ["c-c"], "args": {}, "func": "quit"},
            {"keys": ["c-@"], "args": {}, "func": "toggle_compact"},
            {"keys": ["c-r"], "args": {}, "func": "toggle_raw"},
            {"keys": ["c-y"], "args": {}, "func": "set_mode_yaml"},
            {"keys": ["c-j"], "args": {}, "func": "set_mode_jq"},
        ]
        cfg = {
            "bindings": bindings,
        }
        cfg = types.SimpleNamespace(**config_dir.load_config(".jqi", default=cfg))

        kb = KeyBindings()
        for binding in cfg.bindings:
            binding = types.SimpleNamespace(**binding)
            kb.add(*binding.keys, **binding.args)(getattr(self, binding.func))

        return kb

    def load(self):
        cfg = dict(pattern=".")
        if self.file is not None:
            cfg = config_dir.load_config(".jqi", sub_dir="query", sub_name=self.file, default=cfg, create=False)
        self.pattern = cfg.get("pattern", self.pattern)
        self.compact = cfg.get("compact", False)
        self.raw = cfg.get("raw", False)

    def save(self, file=None):
        if file is not None:
            self.file = file

        cfg = {
            "pattern": self.buf.text,
            "compact": self.compact,
            "raw": self.raw,
        }

        if self.file is not None:
            config_dir.save_config(".jqi", sub_dir="query", sub_name=self.file, config=cfg)

    def exit(self, event):
        event.app.exit(0)

    def quit(self, event):
        event.app.exit(1)

    def toggle_compact(self, event):
        self.compact = not self.compact
        self.reformat()

    def toggle_raw(self, event):
        self.raw = not self.raw
        self.reformat()

    def set_mode_jq(self, event):
        self.mode = Editor.CACHE_JQ_LINES
        self.update_status_bar()
        self.update_main_window()
        event.app.invalidate()

    def set_mode_yaml(self, event):
        self.mode = Editor.CACHE_YAML_LINES
        self.update_status_bar()
        self.update_main_window()
        event.app.invalidate()

    def update_status_bar(self):
        args = []
        if self.compact:
            args += ["-c"]
        if self.raw:
            args += ["-r"]

        self.status.text = "[{}]-[{}]".format(" ".join(args), self.mode)

    def reformat(self):
        self.update_status_bar()
        self.vbar.width = self.completions.width = 0

        out, err = self.jq(tty=True)
        if out is not None:
            self.cache[Editor.CACHE_BYTES] = out
            self.cache[Editor.CACHE_JQ_LINES] = None
            self.cache[Editor.CACHE_OBJECT] = None
            self.cache[Editor.CACHE_YAML_LINES] = None
            self.update_main_window()
            self.error.content.text = None
            self.error.height = 0
            self.app.invalidate()
        else:
            self.error.content.text = err
            self.error.height = err.count("\n")

        self.app.invalidate()

    def update_main_window(self):
        # On input, some of `self.cache` is already populated.
        # Update the main window according to settings
        lines = []
        if self.mode == Editor.CACHE_JQ_LINES:
            out = self.cache[Editor.CACHE_BYTES]
            if self.cache[Editor.CACHE_JQ_LINES] is None:
                self.cache[Editor.CACHE_JQ_LINES] = out.splitlines()
            lines = self.cache[Editor.CACHE_JQ_LINES]
        elif self.mode == Editor.CACHE_YAML_LINES:
            if self.cache[Editor.CACHE_YAML_LINES] is None:
                try:
                    objects = self._get_cached_objects()
                    out = yaml.safe_dump_all(objects)
                except json.JSONDecodeError:
                    out = "Error parsing stream as Yaml"
                self.cache[Editor.CACHE_YAML_LINES] = out.splitlines()
            lines = self.cache[Editor.CACHE_YAML_LINES]
        else:
            raise NotImplementedError("Unknown mode: {}".format(self.mode))

        # Window positioning goes here.
        maxwidth = max(self.app.output.get_size().columns * 10, 160)
        maxlen = max(self.app.output.get_size().rows * 2, 100)
        self.result.content.text = ANSI("\n".join(line[:maxwidth] for line in lines[:maxlen]))

    _STRIP_ANSI = re.compile(r"""
        (\001[^\002]*\002) | # zero-width sequence
        (\033[^\[]) |        # Other escape
        (\033 \[ [0-9;]* m)  # colour sequence
        """, re.VERBOSE)

    _NOT_WHITESPACE = re.compile(r'[^\s]')

    @staticmethod
    def _parse_json_objects(stream):
        objects = []
        parser = json.JSONDecoder()
        offset = 0

        while True:
            match = Editor._NOT_WHITESPACE.search(stream, offset)
            if not match:
                break
            try:
                obj, offset = parser.raw_decode(stream, match.start())
            except json.JSONDecodeError:
                # do something sensible if there's some error
                raise
            objects.append(obj)

        return objects

    def _get_cached_objects(self):
        if self.cache[Editor.CACHE_OBJECT]:
            return self.cache[Editor.CACHE_OBJECT]

        out = self.cache[Editor.CACHE_BYTES]
        out = Editor._STRIP_ANSI.sub("", out)
        objects = self.cache[Editor.CACHE_OBJECT] = self._parse_json_objects(out)
        return objects

    def _get_cached_original_objects(self):
        if self.cache[Editor.CACHE_ORIGINAL_OBJECT]:
            return self.cache[Editor.CACHE_ORIGINAL_OBJECT]

        objects = self.cache[Editor.CACHE_ORIGINAL_OBJECT] = self._parse_json_objects(self.input)
        return objects

    def layout(self):
        completer = JQCompleter(object_source=self._get_cached_original_objects)
        self.buf = Buffer(document=Document(text=self.pattern), completer=completer)  # Editable buffer.
        self.status = FormattedTextControl(text="")  # Status line

        root_container = HSplit([
            Window(height=3, content=BufferControl(buffer=self.buf)),
            CompletionsMenu(),

            # A vertical line in the middle. We explicitly specify the height, to
            # make sure that the layout engine will not try to divide the whole
            # width by three for all these windows. The window will simply fill its
            # content by repeating this character.
            Window(height=1, char='-', content=self.status),

            # Display the text 'Hello world' on the bottom.
            VSplit([
                w2 := Window(content=FormattedTextControl(text='Hello world')),
                wbar := Window(width=0, char="|"),
                wcomp := Window(width=0, content=FormattedTextControl(text="")),
            ]),
            w3 := Window(content=FormattedTextControl())
        ])

        self.result = w2
        self.error = w3
        self.vbar = wbar
        self.completions = wcomp

        layout = Layout(root_container)
        self.app = Application(layout=layout, full_screen=True, key_bindings=self.kb,
                               input=create_input(always_prefer_tty=True))

    def get_pattern(self):
        return self.buf.text

    def run(self, text):
        self.input = text
        self.create_refresh_task(refresh=self.reformat, get_pattern=self.get_pattern)
        self.reformat()

        # Run the application, and wait for it to finish.
        result = self.app.run()
        self.cancel_refresh_task()

        if result != 0:
            return result

        out, _ = self.jq(tty=sys.stdout.isatty())
        print(out, end="")
        return 0

    def jq(self, text=None, stdio=False, tty=False):
        if text is not None:
            self.input = text
        args = []
        if self.compact:
            args += ["-c"]
        if self.raw:
            args += ["-r"]

        args += [self.buf.text]

        tty_args = {}
        if stdio:
            out = sys.stdout
            err = sys.stderr
        else:
            out = io.StringIO()
            err = io.StringIO()
            tty_args.update({"_tty_out": tty})

        try:
            proc = sh.jq(*args, _in=self.input, _out=out, _err=err, **tty_args)
            proc.wait()
            if not stdio:
                out = out.getvalue()
                err = None
        except sh.ErrorReturnCode:
            if not stdio:
                out = None
                err = err.getvalue()

        return out, err
