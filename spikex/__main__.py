def main():
    import sys

    import typer
    from wasabi import msg

    from . import cli

    commands = {
        "create-wikigraph": cli.create_wikigraph,
        "download-wikigraph": cli.download_wikigraph,
        "package-wikigraph": cli.package_wikigraph,
        "profile-matcher": cli.profile_matcher,
        "profile-wikigraph-load": cli.profile_wikigraph_load,
        "profile-wikigraph-exec": cli.profile_wikigraph_exec,
    }

    if len(sys.argv) == 1:
        msg.info("Available commands", ", ".join(commands), exits=1)
    command = sys.argv.pop(1)
    sys.argv[0] = "spikex %s" % command
    if command in commands:
        typer.run(commands[command])
    else:
        available = "Available: {}".format(", ".join(commands))
        msg.fail("Unknown command: {}".format(command), available, exits=1)


if __name__ == "__main__":
    main()
