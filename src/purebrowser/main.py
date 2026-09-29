"""Entry point. Order matters: flags() MUST run before any Qt import."""


def main() -> int:
    from .privacy import flags
    flags.apply()

    from .app import run
    return run()


if __name__ == "__main__":
    raise SystemExit(main())