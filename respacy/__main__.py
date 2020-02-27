if __name__ == "__main__":
    import typer
    import sys
    from wasabi import msg
    from .cli import profile

    commands = {"profile": profile}

    if len(sys.argv) == 1:
        msg.info("Available commands", ", ".join(commands), exits=1)
    command = sys.argv.pop(1)
    sys.argv[0] = "respacy %s" % command
    if command in commands:
        typer.run(commands[command])
    else:
        available = "Available: {}".format(", ".join(commands))
        msg.fail("Unknown command: {}".format(command), available, exits=1)
