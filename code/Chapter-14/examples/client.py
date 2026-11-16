#!/usr/bin/env python3
import os.path
import sys

# 支持直接运行本文件（如 IDE 右上角点击运行）：将项目根目录加入 sys.path，
# 使 `examples` 包可被导入；等价于在 Chapter-14 目录下执行 `python3 -m examples.run`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


__author__ = "xi"

from types import GeneratorType

from libentry import ArgumentParser
from libentry.mcp.client import APIClient

from examples.common import ExampleRequest, ExampleResponse


def main():
    # 这个是个测试程序，实际上并不需要为service写一个额外的client程序
    # 因为组成一个client的三要素都已经具备：
    # （1）具体收发请求逻辑：由libentry.mcp.client.APIClient对象实现的
    # （2）输入输出：由XXRequest对象和XXResponse对象确定
    # （3）远程请求路径：由XXRequest对象给出（之前是约定好一个名称，现在可以直接通过request对象获取）
    parser = ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    client = APIClient(f"http://localhost:{args.port}")

    request = ExampleRequest(speed=5, stream=True)
    response = client.post(request)

    if (isinstance(response, GeneratorType)):
        for resp in response:
            resp = ExampleResponse.model_validate(resp)
            print(resp.content, end="", flush=True)
    else:
        print(response)

    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
