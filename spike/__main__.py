if __name__ == "__main__":
    import typer
    import sys
    from wasabi import msg
    from . import cli

    commands = {
        "profile": cli.profile,
        "create-wiki-xnergraph": cli.create_wiki_xnergraph,
    }

    if len(sys.argv) == 1:
        msg.info("Available commands", ", ".join(commands), exits=1)
    command = sys.argv.pop(1)
    sys.argv[0] = "spike %s" % command
    if command in commands:
        typer.run(commands[command])
    else:
        available = "Available: {}".format(", ".join(commands))
        msg.fail("Unknown command: {}".format(command), available, exits=1)
