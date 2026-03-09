# Copyright (c) 2025 Ming Yu (yuming@oppo.com), Liangliang Han (hanliangliang@oppo.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import json
import logging
import time

# 获取日志实例
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger()


def compare_results(calculated, ground_truth):
    """比较计算结果和ground truth"""
    if len(calculated) != len(ground_truth):
        return False

    if calculated != ground_truth:
        return False

    return True


def benchmark(extractor, input_file, show_all_cases=True, writer=print, language=None):
    total_cases = 0
    success_cases = 0
    error_cases = 0

    with open(input_file, encoding="utf-8") as fin:
        for line_num, line in enumerate(fin, 1):
            total_cases += 1
            data = json.loads(line.strip())
            query = data["query"]
            base_time = data.get("metadata", "2025-01-21T08:00:00Z")
            # 从datetime_result中提取所有dict的value值形成新数组
            gt = data["datetime_result"]
            # 提取中文翻译（仅英文测试时使用）
            chinese_translation = data.get("chinese_translation", "")
            if line:
                # 逐例耗时统计：总耗时与子阶段耗时（通过extractor的累加计数求增量）
                _wall_start = time.time()
                _norm_before = getattr(extractor, "normalizer_time", 0.0)
                _parse_before = getattr(extractor, "time_parser_time", 0.0)

                datetime_results, query_tag = extractor.extract(query, base_time)

                _wall_cost = time.time() - _wall_start
                _norm_cost = getattr(extractor, "normalizer_time", 0.0) - _norm_before
                _parse_cost = getattr(extractor, "time_parser_time", 0.0) - _parse_before
                # 比较结果
                match = compare_results(datetime_results, gt)
                if match:
                    success_cases += 1
                    # 根据控制变量决定是否显示成功case信息
                    if show_all_cases:
                        writer(
                            f"Line {line_num}: ✓ Success | total={_wall_cost:.6f}s, normalizer={_norm_cost:.6f}s, parser={_parse_cost:.6f}s"
                        )
                        writer(f"  Query: {query}")
                        # 如果是英文测试且有中文翻译，则显示中文翻译
                        if language == "english" and chinese_translation:
                            writer(f"  中文: {chinese_translation}")
                        writer(f"  Query Tag: {query_tag}")
                        writer(f"  Result: {datetime_results}")
                        writer(f"  Ground Truth: {gt}")
                else:
                    error_cases += 1
                    # 错误case总是显示
                    writer(
                        f"Line {line_num}: ✗ Mismatch | total={_wall_cost:.6f}s, normalizer={_norm_cost:.6f}s, parser={_parse_cost:.6f}s"
                    )
                    writer(f"  Query: {query}")
                    # 如果是英文测试且有中文翻译，则显示中文翻译
                    if language == "english" and chinese_translation:
                        writer(f"  中文: {chinese_translation}")
                    writer(f"  Query Tag: {query_tag}")
                    writer(f"  Calculated: {datetime_results}")
                    writer(f"  Ground Truth: {gt}")
                    pass

    # 输出统计信息：即使 only_errors 也保留统计数据
    writer("\n" + "=" * 80)
    writer("BENCHMARK SUMMARY")
    writer("=" * 80)
    writer(f"Total test cases: {total_cases}")
    writer(f"Success cases: {success_cases} ({success_cases/total_cases*100:.2f}%)")
    writer(f"Error cases: {error_cases} ({error_cases/total_cases*100:.2f}%)")


def print_usage_examples():
    """打印使用示例"""
    examples = """
使用示例：

1. 解析单条中文文本：
   python main.py --text "明天上午9点" --language chinese

2. 解析单条英文文本：
   python main.py --text "3 PM tomorrow" --language english

3. 指定基准时间：
   python main.py --text "明天上午9点" --base_time "2025-01-21T08:00:00Z"

4. 批量处理文件（中文）：
   python main.py --file src/chinese/test/groundtruth_utc.jsonl --language chinese

5. 批量处理文件（英文）：
   python main.py --file src/english/test/groundtruth_utc_700english.jsonl --language english

6. 批量处理并保存结果：
   python main.py --file input.jsonl --output result.txt --language chinese

7. 强制重建缓存：
   python main.py --text "明天" --overwrite_cache

更多信息请查看 README.md
"""
    print(examples)


def main():  # noqa: C901
    """Main function for time extraction from text input.

    Parses command-line arguments and processes either single text input
    or batch processing from a file using FstTimeExtractor.
    """
    parser = argparse.ArgumentParser(
        description="FST-based Time Extraction Tool - 基于有限状态转换器的时间表达式提取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例：
  # 解析单条中文文本
  python main.py --text "明天上午9点" --language chinese

  # 解析单条英文文本
  python main.py --text "3 PM tomorrow" --language english

  # 批量处理文件
  python main.py --file src/chinese/test/groundtruth_utc.jsonl --language chinese

  # 批量处理并保存结果
  python main.py --file input.jsonl --output result.txt --language chinese

更多信息请查看 README.md
        """,
    )
    parser.add_argument("--text", help="Input text string for time extraction")
    parser.add_argument("--file", help="Path to input file for batch processing")
    parser.add_argument("--output", help="Path to output file for saving --file results")
    parser.add_argument(
        "--overwrite_cache",
        action="store_true",
        help="Force rebuild and overwrite existing FST cache files",
    )
    # 添加基准时间参数
    parser.add_argument(
        "--base_time",
        type=str,
        default="2025-01-21T08:00:00Z",
        help="Base time for relative time calculations (ISO 8601 format)",
    )
    # 添加语言选择参数
    parser.add_argument(
        "--language",
        type=str,
        choices=["chinese", "english"],
        default="chinese",
        help="Language selection for time extraction (chinese/english)",
    )

    # 添加是否显示所有case的参数
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Show all test cases (including successful ones) in batch processing mode",
    )

    args = parser.parse_args()

    # 参数验证：必须提供 --text 或 --file 之一
    if not args.text and not args.file:
        print("错误：必须提供 --text 或 --file 参数之一\n")
        parser.print_help()
        print_usage_examples()
        return 1

    # 参数验证：--text 和 --file 不能同时使用
    if args.text and args.file:
        print("错误：--text 和 --file 参数不能同时使用\n")
        parser.print_help()
        print_usage_examples()
        return 1

    # 参数验证：--output 只能与 --file 一起使用
    if args.output and not args.file:
        print("错误：--output 参数只能与 --file 参数一起使用\n")
        parser.print_help()
        print_usage_examples()
        return 1

    # 参数验证：检查文件是否存在
    if args.file:
        import os

        if not os.path.exists(args.file):
            print(f"错误：文件不存在: {args.file}\n")
            return 1

    # 根据语言选择初始化对应的时间提取器（延迟导入避免初始化不必要的符号表）
    if args.language == "chinese":
        from src.chinese.fst_time_extractor import (
            FstTimeExtractor as ChineseFstTimeExtractor,
        )

        extractor = ChineseFstTimeExtractor(overwrite_cache=args.overwrite_cache)
    elif args.language == "english":
        from src.english.fst_time_extractor import (
            FstTimeExtractor as EnglishFstTimeExtractor,
        )

        extractor = EnglishFstTimeExtractor(overwrite_cache=args.overwrite_cache)
    else:
        raise ValueError(f"Unsupported language: {args.language}")

    start_time = time.time()
    if args.text:
        # 处理单条文本输入
        datetime_results, query_tag = extractor.extract(args.text, args.base_time)

        print(f"Language: {args.language}")
        print(f"Query: {args.text}")
        print(f"BaseTime: {args.base_time}")
        print(f"Query Tag: {query_tag}")
        print(f"Result: {datetime_results}")
    elif args.file:
        # 处理文件批量输入
        if args.output:
            # 如果指定了输出文件，同时输出到控制台和文件
            with open(args.output, "w", encoding="utf-8") as f:

                def writer(msg):
                    try:
                        print(msg)
                    except BrokenPipeError:
                        # 忽略管道中断错误（如使用 head 命令时）
                        pass
                    f.write(msg + "\n")

                benchmark(
                    extractor,
                    args.file,
                    show_all_cases=args.show_all,
                    writer=writer,
                    language=args.language,
                )
        else:
            # 只输出到控制台
            benchmark(
                extractor,
                args.file,
                show_all_cases=args.show_all,
                language=args.language,
            )

    # 输出性能统计信息
    print(f"Language: {args.language}")
    # 检查extractor是否有normalizer属性及其方法
    if (
        hasattr(extractor, "normalizer")
        and hasattr(extractor.normalizer, "tagger")
        and hasattr(extractor.normalizer.tagger, "num_states")
    ):
        print(f"FST状态数: {extractor.normalizer.tagger.num_states()}")
    else:
        print(f"FST状态数: N/A (not available for {args.language})")
    print(f"Total time: {time.time() - start_time}")
    print(f"Normalizer time: {extractor.normalizer_time}")
    print(f"Time parser time: {extractor.time_parser_time}")


if __name__ == "__main__":
    main()
