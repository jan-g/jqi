import asyncio
import argparse_helper as argparse
import config_dir
import io
from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.input.defaults import create_input
from prompt_toolkit.keys import Keys
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.layout import Layout
import sh
import sys


def main(*args):
    if len(args) > 0:
        args = [args]
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", dest="cfg_file")
    parser.add_argument("file", nargs="?")
    args = parser.parse_args(*args)

    editor = Editor(file=args.cfg_file)

    if args.file is None:
        text = sys.stdin.read()
    else:
        with open(args.file) as f:
            text = f.read()

    result = editor.run(text)
    if result == 0:
        editor.save()
    else:
        sys.exit(result)


class Editor:
    def __init__(self, file=None):
        self.file = file
        self.pattern = "."
        self.compact = False
        self.raw = False
        self.input = "{}"

        kb = self.kb = KeyBindings()
        kb.add(Keys.ControlX, eager=True)(self.exit)
        kb.add('c-c')(self.quit)
        kb.add(Keys.ControlSpace)(self.toggle_compact)
        kb.add(Keys.ControlR)(self.toggle_raw)

        self.app = None
        self.buf = None
        self.status = None
        self.result = None
        self.error = None
        self.load()

    def load(self):
        cfg = dict(pattern=".")
        if self.file is not None:
            cfg = config_dir.load_config(".jqi", sub_name=self.file, default=cfg, create=False)
        self.pattern = cfg.get("pattern", self.pattern)
        self.compact = cfg.get("compact", False)
        self.raw = cfg.get("raw", False)

    def save(self):
        cfg = {
            "pattern": self.buf.text,
            "compact": self.compact,
            "raw": self.raw,
        }
        if self.file is not None:
            config_dir.save_config(".jqi", sub_name=self.file, config=cfg)

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

    async def tick(self):
        unchanged_count = 0
        counting = False
        old_pattern = self.buf.text
        while True:
            if self.buf.text != old_pattern:
                old_pattern = self.buf.text
                unchanged_count = 0
                counting = True
            if counting:
                unchanged_count += 1
            if unchanged_count > 2:
                counting = False
                unchanged_count = 0
                try:
                    self.reformat()
                except Exception as e:
                    print("error:", e)
            await asyncio.sleep(0.3)

    def reformat(self):
        args = []
        if self.compact:
            args += ["-c"]
        if self.raw:
            args += ["-r"]

        self.status.text = "[" + " ".join(args) + "]"

        args += [self.buf.text]
        out = io.StringIO()
        err = io.StringIO()
        try:
            proc = sh.jq(*args, _in=self.input, _out=out, _err=err)
            proc.wait()
            out = out.getvalue().splitlines()
            maxlen = max(self.app.output.get_size().rows * 2, 100)
            self.result.content.text = ANSI("\n".join(out[:maxlen]))
            self.error.content.text = None
            self.error.height = 0
            self.app.invalidate()
        except sh.ErrorReturnCode:
            err = err.getvalue()
            self.error.content.text = err
            self.error.height = err.count("\n")

        self.app.invalidate()

    def run(self, text):
        self.input = text
        self.buf = Buffer(document=Document(text=self.pattern))  # Editable buffer.
        self.status = FormattedTextControl(text="")  # Status line

        root_container = HSplit([
            Window(height=3, content=BufferControl(buffer=self.buf)),

            # A vertical line in the middle. We explicitly specify the height, to
            # make sure that the layout engine will not try to divide the whole
            # width by three for all these windows. The window will simply fill its
            # content by repeating this character.
            Window(height=1, char='-', content=self.status),

            # Display the text 'Hello world' on the bottom.
            w2 := Window(content=FormattedTextControl(text='Hello world')),
            w3 := Window(content=FormattedTextControl())
        ])

        self.result = w2
        self.error = w3

        layout = Layout(root_container)
        self.app = Application(layout=layout, full_screen=True, key_bindings=self.kb,
                               input=create_input(always_prefer_tty=True))
        task = asyncio.get_event_loop().create_task(self.tick())

        self.reformat()

        # Run the application, and wait for it to finish.
        result = self.app.run()
        task.cancel()

        if result != 0:
            return result

        args = []
        if self.compact:
            args += ["-c"]
        if self.raw:
            args += ["-r"]
        args += [self.buf.text]
        content = sh.jq(*args, _in=text, _tty_out=sys.stdout.isatty()).stdout.decode()
        print(content, end="")
        return 0


if __name__ == '__main__':
    main("-f", "foo", "/tmp/x")
