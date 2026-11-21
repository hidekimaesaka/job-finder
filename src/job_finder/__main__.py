import argparse

from job_finder.config import Settings
from job_finder.log import configure_logging
from job_finder.runner import run


def main() -> int:
    parser = argparse.ArgumentParser(description="Coleta vagas compatíveis com o perfil do Kali.")
    parser.add_argument(
        "--trigger",
        choices=("scheduled", "manual"),
        default="scheduled",
        help="Origem da execução.",
    )
    args = parser.parse_args()
    settings = Settings()
    configure_logging(settings.log_level)
    return run(settings, trigger=args.trigger)


if __name__ == "__main__":
    raise SystemExit(main())
