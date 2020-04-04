import asyncio
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


def main():
    text = ''
    if len(sys.argv) == 1:
        text = sys.stdin.read()
    elif len(sys.argv) == 2:
        with open(sys.argv[1]) as f:
            text = f.read()

    buf = Buffer()  # Editable buffer.
    buf.document = Document(text=".")
    compact = False
    raw = False

    kb = KeyBindings()

    @kb.add('c-c')
    def _(event):
        event.app.exit()

    @kb.add(Keys.ControlSpace)
    def _(event):
        nonlocal compact
        compact = not compact
        reformat()

    @kb.add(Keys.ControlR)
    def _(event):
        nonlocal raw
        raw = not raw
        reformat()

    old_text = buf.text

    async def tick():
        nonlocal old_text
        unchanged_count = 0
        counting = False
        while True:
            if buf.text != old_text:
                old_text = buf.text
                unchanged_count = 0
                counting = True
            if counting:
                unchanged_count += 1
            if unchanged_count > 2:
                counting = False
                unchanged_count = 0
                try:
                    reformat()
                except Exception as e:
                    print("error:", e)
            await asyncio.sleep(0.3)

    task = asyncio.get_event_loop().create_task(tick())

    root_container = HSplit([
        # One window that holds the BufferControl with the default buffer at
        # the top.
        w1 := Window(height=3, content=BufferControl(buffer=buf)),

        # A vertical line in the middle. We explicitly specify the height, to
        # make sure that the layout engine will not try to divide the whole
        # width by three for all these windows. The window will simply fill its
        # content by repeating this character.
        Window(height=1, char='-'),

        # Display the text 'Hello world' on the bottom.
        w2 := Window(content=FormattedTextControl(text='Hello world')),
        w3 := Window(content=FormattedTextControl())
    ])

    layout = Layout(root_container)
    app = Application(layout=layout, full_screen=True, key_bindings=kb, input=create_input(always_prefer_tty=True))

    def reformat():
        nonlocal w2
        args = []
        if compact:
            args += ["-c"]
        if raw:
            args += ["-r"]
        args += [buf.text]
        out = io.StringIO()
        err = io.StringIO()
        try:
            proc = sh.jq(*args, _in=text, _out=out, _err=err)
            proc.wait()
            out = out.getvalue()
            w2.content.text = ANSI(out)
            w3.content.text = None
            w3.height = 0
            app.invalidate()
        except sh.ErrorReturnCode:
            err = err.getvalue()
            w3.content.text = err
            w3.height = err.count("\n")
            app.invalidate()

    reformat()

    # Run the application, and wait for it to finish.
    app.run()
    task.cancel()

    args = []
    if compact:
        args += ["-c"]
    if raw:
        args += ["-r"]
    args += [buf.text]
    content = sh.jq(*args, _in=text, _tty_out=sys.stdout.isatty()).stdout.decode()
    print(content, end="")


if __name__ == '__main__':
    main()
