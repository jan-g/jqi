import argparse_helper as argparse
import config_dir
import sys

from .editor import Editor


def main(*args):
    if len(args) > 0:
        args = [args]
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", dest="cfg_file", help="query save name")
    parser.add_argument("-x", default=False, action="store_true", dest="run", help="run immediately")
    parser.add_argument("-l", default=False, action="count", dest="list", help="list saved queries")
    parser.add_argument("-p", default=False, action="store_true", dest="previous", help="use previous query")
    parser.add_argument("pattern", nargs="?", help="override saved pattern")
    parser.add_argument("file", nargs="?", help="file to operate on")
    args = parser.parse_args(*args)

    if args.cfg_file is None and args.previous:
        args.cfg_file = "previous"

    if args.cfg_file is not None and args.file is None:
        args.file = args.pattern
        args.pattern = None

    editor = Editor(file=args.cfg_file, pattern=args.pattern)

    if args.list > 0:
        if args.cfg_file is not None:
            cfg = config_dir.load_config(name=".jqi", sub_dir="query", sub_name=args.cfg_file, create=False)
            print(cfg["pattern"])
        else:
            list_stored(args.list > 1)
        return

    if args.file is None:
        text = sys.stdin.read()
    else:
        with open(args.file) as f:
            text = f.read()

    if args.run:
        editor.jq(text, stdio=True)
    else:
        result = editor.run(text)
        if result == 0:
            editor.save()
            editor.save("previous")
        else:
            sys.exit(result)


def list_stored(long=False):
    d = config_dir.config_dir(name=".jqi", sub_dir="query")
    for f in d.iterdir():
        name = f.name
        cfg = config_dir.load_config(name=".jqi", sub_dir="query", sub_name=name, create=False)
        if long:
            print(name)
            for line in cfg["pattern"].splitlines():
                print("\t{}".format(line))
        else:
            print("{}\t{}".format(name, cfg["pattern"].splitlines()[0]))


if __name__ == '__main__':
    main("-f", "foo", "/tmp/x")
