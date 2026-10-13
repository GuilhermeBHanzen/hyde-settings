"""`hyde-settings` opens the app; `hyde-settings --revert-after N BACKUP TARGET` is the revert watchdog."""
import sys


def main(argv=None):
    argv = sys.argv if argv is None else argv
    if len(argv) >= 5 and argv[1] == "--revert-after":
        from hyde_settings import apply
        from hyde_settings.hypr import Hypr

        return apply.revert_after(int(argv[2]), argv[3], argv[4], Hypr())
    from hyde_settings.app import HydeSettings

    return HydeSettings().run(argv[:1])


if __name__ == "__main__":
    sys.exit(main())
