# An interactive wrapper for jq

This can be used as part of a pipeline, or take a file as input.

Use control-space to toggle compact mode; use control-R to toggle
raw output.

Use:

    somthing-that-produces-json | jqi

or

    jqi /tmp/foo.json file

Use control-C to exit.
