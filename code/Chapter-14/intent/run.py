#!/usr/bin/env python3

__author__ = "xi"

from libentry import ArgumentParser
from libentry.mcp.service import RunServiceConfig, run_service

from intent.service import IntentService, IntentServiceConfig


def main():
    parser = ArgumentParser()
    parser.add_schema("run", RunServiceConfig)
    parser.add_schema("config", IntentServiceConfig)
    args = parser.parse_args()

    run_service(IntentService, args.config, args.run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
