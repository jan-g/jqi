# An interactive wrapper for jq

This can be used as part of a pipeline, or take a file as input.

Use control-space to toggle compact mode; use control-R to toggle
raw output.

Use:

    somthing-that-produces-json | jqi

or

    jqi /tmp/foo.json file

Use control-C to exit.

## Keys

- `^X`: exit (dumping the result to stdout)
- `^C`: quit
- `^ space`: toggle compact mode
- `^r`: toggle raw mode
- `^y`: set yaml mode
- `^j`: set JSON mode

- `^ LEFT`: word left
- `^ RIGHT`: work right

- `alt-arrow`, `alt-page up/down`, `alt-home/end`: scroll the output window
