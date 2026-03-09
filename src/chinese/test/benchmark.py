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
import importlib
import json
import os
import sys
import time

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
FstTimeExtractor = importlib.import_module("chinese.fst_time_extractor").FstTimeExtractor


def compare_results(calculated, ground_truth):
    """比较计算结果和ground truth"""
    if len(calculated) != len(ground_truth):
        return False

    if calculated != ground_truth:
        return False

    return True


def write_to_success(data, mode="a"):
    file_path = os.path.dirname(__file__) + "/groundtruth_utc_success.jsonl"
    try:
        with open(file_path, mode, encoding="utf-8") as file:
            # 将字典转换为JSON字符串并写入
            json.dump(data, file, ensure_ascii=False)
            file.write("\n")  # 每行一个JSON对象
        # print(f"成功写入JSONL文件: {file_path}")
    except Exception as e:
        print(f"写入JSONL文件时出错: {e}")


def write_to_fail(data, mode="a"):
    file_path = os.path.dirname(__file__) + "/groundtruth_utc_fail.jsonl"
    try:
        with open(file_path, mode, encoding="utf-8") as file:
            # 将字典转换为JSON字符串并写入
            json.dump(data, file, ensure_ascii=False)
            file.write("\n")  # 每行一个JSON对象
        # print(f"成功写入JSONL文件: {file_path}")
    except Exception as e:
        print(f"写入JSONL文件时出错: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", help="input string")
    parser.add_argument("--overwrite_cache", action="store_true", help="rebuild *.fst")
    args = parser.parse_args()

    # test_case = os.path.dirname(__file__) + "/tag_classifications/type_time_lunar.jsonl"
    test_case = os.path.dirname(__file__) + "/groundtruth_utc.jsonl"
    fst_file = os.path.dirname(__file__) + "/fst"

    extractor = FstTimeExtractor(cache_dir=fst_file, overwrite_cache=args.overwrite_cache)

    # 统计信息
    total_cases = 0
    success_cases = 0
    error_cases = 0
    error_details = []

    start_time = time.perf_counter()
    # 读取utc_time.jsonl文件
    with open(test_case, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            # if line_num > 100:
            #     continue
            total_cases += 1
            try:
                data = json.loads(line.strip())
                query = data["query"]
                base_time = data.get("metadata", "2025-01-21T08:00:00Z")
                # 从datetime_result中提取所有dict的value值形成新数组
                gt = data["datetime_result"]

                # 使用FstTimeExtractor提取时间
                try:
                    datetime_results = extractor.extract(query, base_time)

                    # 比较结果
                    match = compare_results(datetime_results, gt)
                    if match:
                        success_cases += 1
                        print(f"Line {line_num}: ✓ Success")
                        # write_to_success(data) #分出正确的例子
                    else:
                        error_cases += 1
                        print(f"Line {line_num}: ✗ Mismatch")
                        # write_to_fail(data) #分出错误的例子

                    print(f"  Query: {query}")
                    print(f"  Calculated: {datetime_results}")
                    print(f"  Ground Truth: {gt}")

                except Exception as e:
                    error_cases += 1
                    datetime_results = []
                    error_details.append({"line": line_num, "query": query, "error": str(e)})
                    print(f"Line {line_num}: ✗ Error calculating datetime")
                    print(f"  Query: {query}")
                    print(f"  Error: {e}")

                print("-" * 80)

            except json.JSONDecodeError as e:
                print(f"Error parsing JSON at line {line_num}: {e}")
                error_cases += 1
            except Exception as e:
                print(f"Unexpected error at line {line_num}: {e}")
                error_cases += 1

        end_time = time.perf_counter()

    print(f"总执行时间: {end_time - start_time:.4f}秒")

    # 输出统计信息
    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY")
    print("=" * 80)
    print(f"Total test cases: {total_cases}")
    print(f"Success cases: {success_cases} ({success_cases/total_cases*100:.2f}%)")
    print(f"Error cases: {error_cases} ({error_cases/total_cases*100:.2f}%)")

    if error_details:
        print("\nDetailed errors (showing first 10):")
        for err in error_details[:10]:
            print(f"  Line {err['line']}: {err['query']}")
            print(f"    Error: {err['error']}")


if __name__ == "__main__":
    main()
