"""執行 12 題即時工具選擇測試，供作業報告使用。

此程式會呼叫 API 並消耗額度。先完成 .env 設定，再執行：
    python tool_choice_test.py
"""

import time

from app import run_agent


TEST_CASES = [
    ("What time can I check in?", [{"get_guesthouse_info"}]),
    ("Where is the guesthouse?", [{"get_guesthouse_info"}]),
    ("Is breakfast included?", [{"get_guesthouse_info"}]),
    ("Can I bring my dog?", [{"get_guesthouse_info"}]),
    ("Do you have a room for four people?", [{"search_rooms"}]),
    ("Which rooms have a sea view?", [{"search_rooms"}]),
    ("What is the price of a double room?", [{"search_rooms"}]),
    # 模型若先查房型名稱再計算，同樣視為正確。
    ("How much is the Seaside Suite for two nights?", [{"calculate_stay"}, {"search_rooms", "calculate_stay"}]),
    ("花園雙人房住三晚多少錢？", [{"calculate_stay"}, {"search_rooms", "calculate_stay"}]),
    ("I want to complain about my room.", [{"transfer_to_human"}]),
    ("I need to change my reservation.", [{"transfer_to_human"}]),
    ("What will the weather be tomorrow?", [set()]),
]


def main() -> None:
    hits = 0
    print("工具選擇測試\n")
    for number, (question, accepted) in enumerate(TEST_CASES, start=1):
        _, trace = run_agent([{"role": "user", "content": question}])
        actual = {entry["tool"] for entry in trace}
        passed = actual in accepted
        hits += passed
        print(f"{number:02d}. {'通過' if passed else '未通過'}")
        print(f"    問題：{question}")
        print(f"    可接受工具：{[sorted(tools) or ['不需工具'] for tools in accepted]}")
        print(f"    實際工具：  {sorted(actual) or ['不需工具']}")
        time.sleep(4)  # 工具呼叫經常需要兩次以上 API 呼叫，避免觸發免費額度的速率限制。
    print(f"\n分數：{hits}/{len(TEST_CASES)} = {hits / len(TEST_CASES):.0%}")


if __name__ == "__main__":
    main()
