"""即時測試工具選擇；會呼叫聊天及 embedding API 並消耗額度。"""
import time
from app import run_agent

# 每題列出必須使用及不應使用的工具；可額外使用其他合理工具。
TEST_CASES = [
    ("What time can I check in?", {"get_guesthouse_info"}, {"search_guesthouse_rules"}),
    ("Where is the guesthouse?", {"get_guesthouse_info"}, set()),
    ("Can I bring my dog?", {"search_guesthouse_rules"}, {"get_guesthouse_info"}),
    ("取消訂房可以退款嗎？", {"search_guesthouse_rules"}, {"get_guesthouse_info"}),
    ("Do you have a room for four people?", {"search_rooms"}, set()),
    ("海景套房住三晚多少錢？", {"calculate_stay"}, set()),
    ("花園雙床房多少錢？可以帶寵物嗎？", {"search_rooms", "search_guesthouse_rules"}, set()),
    ("I need to change my reservation.", {"transfer_to_human"}, set()),
    ("What will the weather be tomorrow?", set(), set()),
]


def main():
    hits = 0
    for question, required, forbidden in TEST_CASES:
        answer, trace = run_agent([{"role": "user", "content": question}])
        used = {entry["tool"] for entry in trace}
        passed = required <= used and not (forbidden & used)
        if not required and not forbidden:
            passed = not used
        hits += passed
        print(f"{'通過' if passed else '未通過'}：{question}\n  工具：{sorted(used)}\n  回答：{answer}\n")
        time.sleep(2)
    print(f"工具選擇：{hits}/{len(TEST_CASES)}。請另行人工檢查答案是否忠於資料。")


if __name__ == "__main__":
    main()
