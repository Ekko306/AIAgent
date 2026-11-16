#!/usr/bin/env python3
import os.path
import sys

# 支持直接运行本文件（如 IDE 右上角点击运行）：将项目根目录加入 sys.path，
# 使 `examples` 包可被导入；等价于在 Chapter-14 目录下执行 `python3 -m examples.run`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


__author__ = "xi"

from libentry import ArgumentParser
from libentry.mcp.service import run_service

from examples.common import ExampleConfig
from examples.service import ExampleService


def main():
    # 如果使用libentry中的ArgumentParser，则可以将配置的class作为参数，这样可以通过命令行设置其属性
    # 例如下面这种写法，在运行run.py的时候，就可以通过 --config.name "XX Name" 的形式设置ExampleConfig的name属性值
    parser = ArgumentParser()
    parser.add_schema("config", ExampleConfig)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--num_workers", type=int, default=1)
    parser.add_argument("--num_threads", type=int, default=50)
    args = parser.parse_args()

    run_service(
        service_type=ExampleService,
        service_config=args.config,
        host=args.host,
        port=args.port,
        num_workers=args.num_workers,
        num_threads=args.num_threads
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
