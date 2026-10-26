"""海岸小屋民宿客服 Agent。

執行方式：python app.py
程式每次啟動時，都會從兩個 CSV 檔重新建立 SQLite 資料庫。
"""

import csv
import json
import os
import re
import socket
import sqlite3
from pathlib import Path

import gradio as gr
from dotenv import load_dotenv
from openai import OpenAI


HERE = Path(__file__).parent
DATABASE_PATH = HERE / "guesthouse.db"
# Gradio 6 的 Chatbot 預設採用 messages 格式；Gradio 5 則必須明確指定。
CHATBOT_KWARGS = {} if int(gr.__version__.split(".")[0]) >= 6 else {"type": "messages"}

# ---------------------------------------------------------------------------
# 1. API 設定
# ---------------------------------------------------------------------------
load_dotenv(HERE / ".env")
client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url=os.getenv("LLM_API_URL"),
    timeout=60.0,
)
CHAT_MODEL = os.getenv("MODEL_NAME")


# ---------------------------------------------------------------------------
# 2. 由 CSV 建立本機資料庫
# ---------------------------------------------------------------------------
connection = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
connection.row_factory = sqlite3.Row
cursor = connection.cursor()


def build_database() -> list[str]:
    """從要繳交的 CSV 資料檔重新建立兩張資料表。"""
    cursor.execute("DROP TABLE IF EXISTS guesthouse_info")
    cursor.execute("DROP TABLE IF EXISTS rooms")
    cursor.execute(
        "CREATE TABLE guesthouse_info (topic TEXT PRIMARY KEY, content TEXT NOT NULL)"
    )
    cursor.execute(
        """CREATE TABLE rooms (
            room_id INTEGER PRIMARY KEY, name TEXT NOT NULL, name_zh TEXT NOT NULL,
            room_type TEXT NOT NULL, capacity INTEGER NOT NULL,
            price_per_night INTEGER NOT NULL, available INTEGER NOT NULL,
            features TEXT NOT NULL
        )"""
    )

    with (HERE / "guesthouse_info.csv").open(newline="", encoding="utf-8") as data_file:
        cursor.executemany(
            "INSERT INTO guesthouse_info (topic, content) VALUES (?, ?)",
            [(row["topic"], row["content"]) for row in csv.DictReader(data_file)],
        )
    with (HERE / "rooms.csv").open(newline="", encoding="utf-8") as data_file:
        cursor.executemany(
            """INSERT INTO rooms
               (room_id, name, name_zh, room_type, capacity, price_per_night, available, features)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    row["room_id"], row["name"], row["name_zh"], row["room_type"],
                    row["capacity"], row["price_per_night"], row["available"], row["features"],
                )
                for row in csv.DictReader(data_file)
            ],
        )
    connection.commit()
    return [row["topic"] for row in cursor.execute("SELECT topic FROM guesthouse_info")]


INFO_TOPICS = build_database()


# ---------------------------------------------------------------------------
# 3. 工具：每個工具只回傳資料，不直接撰寫給客人的句子
# ---------------------------------------------------------------------------
def get_guesthouse_info(topic: str) -> dict:
    """查詢一項民宿常見資訊。"""
    row = cursor.execute(
        "SELECT content FROM guesthouse_info WHERE topic = ?", (topic,)
    ).fetchone()
    if row is None:
        return {"found": False, "available_topics": INFO_TOPICS}
    return {"found": True, "topic": topic, "content": row["content"]}


def search_rooms(keyword: str) -> dict:
    """用中英文房名、房型、特色或容納人數的部分關鍵字搜尋房間。"""
    keyword = keyword.strip()
    if not keyword:
        return {"found": False, "note": "請提供房名、房型、特色或容納人數。"}

    # 模型可能以文字描述人數，例如「四人房」或 "a room for four people"。
    # 由程式做簡單轉換，避免必須在 CSV 中剛好出現相同的完整字串。
    capacity = next((number for word, number in {
        "one": 1, "single": 1, "two": 2, "double": 2, "twin": 2,
        "four": 4, "six": 6, "eight": 8,
        "一": 1, "二": 2, "兩": 2, "双": 2, "雙": 2,
        "四": 4, "六": 6, "八": 8,
    }.items() if word in keyword.lower()), None)
    like = f"%{keyword}%"
    if capacity is not None:
        # 依人數查詢時，不應誤把八人房特色中的「四張床」當作四人房。
        rows = cursor.execute(
            """SELECT name, name_zh, room_type, capacity, price_per_night, available, features
               FROM rooms WHERE capacity = ? ORDER BY price_per_night""",
            (capacity,),
        ).fetchall()
    else:
        rows = cursor.execute(
            """SELECT name, name_zh, room_type, capacity, price_per_night, available, features
               FROM rooms
               WHERE name LIKE ? OR name_zh LIKE ? OR room_type LIKE ? OR features LIKE ?
                  OR CAST(capacity AS TEXT) = ?
               ORDER BY price_per_night""",
            (like, like, like, like, keyword),
        ).fetchall()
    if not rows:
        return {"found": False, "note": f"找不到符合「{keyword}」的房型。"}
    return {
        "found": True,
        "rooms": [
            {
                "name": row["name"],
                "name_zh": row["name_zh"],
                "type": row["room_type"],
                "capacity": row["capacity"],
                "price_per_night": row["price_per_night"],
                "available": bool(row["available"]),
                "features": row["features"],
            }
            for row in rows
        ],
    }


def calculate_stay(room_name: str, nights: int) -> dict:
    """計算每晚房價乘以晚數；只接受名稱精確且目前可用的房型。"""
    if not isinstance(nights, int) or nights < 1 or nights > 30:
        return {"total": None, "note": "住宿晚數必須是 1 到 30 之間的整數。"}
    row = cursor.execute(
        """SELECT name, name_zh, price_per_night, available
           FROM rooms WHERE name = ? OR name_zh = ?""",
        (room_name.strip(), room_name.strip()),
    ).fetchone()
    if row is None:
        return {
            "total": None,
            "note": "房型名稱不夠精確。請先用 search_rooms 查詢，再請客人選定房型。",
        }
    if not row["available"]:
        return {"total": None, "note": f"{row['name']} 目前不可訂。"}
    nightly_rate = row["price_per_night"]
    return {
        "room": row["name"],
        "room_zh": row["name_zh"],
        "nights": nights,
        "nightly_rate": nightly_rate,
        "formula": f"NT${nightly_rate} × {nights} 晚",
        "total": nightly_rate * nights,
    }


def transfer_to_human() -> dict:
    """回傳真人客服聯絡資訊，供客訴、改訂房或資料不足的情況使用。"""
    return {
        "phone": "07-555-0188",
        "service_hours": "每日 08:00–21:00",
        "email": "hello@seasidehaven.example",
        "note": "民宿人員可協助處理客訴、訂房異動、特殊例外與資料未涵蓋的民宿問題。",
    }


TOOL_FUNCTIONS = {
    "get_guesthouse_info": get_guesthouse_info,
    "search_rooms": search_rooms,
    "calculate_stay": calculate_stay,
    "transfer_to_human": transfer_to_human,
}

TOOL_SPECS = [
    {"type": "function", "function": {
        "name": "get_guesthouse_info",
        "description": "查詢民宿的一項固定資訊，例如入住、退房、地址、電話、停車、早餐、付款、寵物、寄放行李、取消政策或 Wi-Fi。",
        "parameters": {"type": "object", "properties": {
            "topic": {"type": "string", "enum": INFO_TOPICS}
        }, "required": ["topic"]},
    }},
    {"type": "function", "function": {
        "name": "search_rooms",
        "description": "搜尋房型，回傳每晚房價、容納人數、特色與可用狀態。適用於房型、價格、景觀、寵物、無障礙或容納人數等問題。請使用簡短關鍵字，例如「double」、「family」、「sea view」、「港灣」或「4」。",
        "parameters": {"type": "object", "properties": {
            "keyword": {"type": "string"}
        }, "required": ["keyword"]},
    }},
    {"type": "function", "function": {
        "name": "calculate_stay",
        "description": "計算一個名稱精確且可用房型的住宿費。只要問題需要總價，一律使用此工具，絕不可自行乘算或加總房價；房名不清楚時先搜尋。",
        "parameters": {"type": "object", "properties": {
            "room_name": {"type": "string", "description": "由 search_rooms 得到的精確中英文房名。"},
            "nights": {"type": "integer", "description": "住宿晚數，範圍為 1 到 30。"},
        }, "required": ["room_name", "nights"]},
    }},
    {"type": "function", "function": {
        "name": "transfer_to_human",
        "description": "用於客訴、要求真人服務、訂房異動、特殊例外，或其他工具無法回答的民宿問題。不可用於與民宿無關的話題。",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
]


SYSTEM_PROMPT = """
你是「海岸小屋民宿」的線上客服 Agent；這是一間虛構的高雄民宿。
所有價格均為新臺幣，格式必須寫成 NT$。

規則
1. 只能根據工具回傳的結果回答。不可憑記憶回答，也不可虛構事實、房型、價格或政策。
2. 工具找不到答案時，要明確說明；若真人客服可以協助，使用 transfer_to_human。
3. 只討論這間民宿。天氣、作業、程式或一般知識等無關要求，要禮貌婉拒。
4. 答覆應有幫助且精簡，不超過三句；依程式指定的語言回答。
5. 入住、早餐、停車、付款、寵物、取消或 Wi-Fi 等民宿固定資訊 → get_guesthouse_info。
6. 房型、特色、容納人數、可用狀態或每晚價格 → search_rooms。
7. 任何住宿總價 → calculate_stay。絕不可自行計算金額；房名不清楚時先搜尋。
8. 客訴、訂房異動、特殊需求、要求真人服務，或資料未涵蓋的民宿問題 → transfer_to_human。
""".strip()

MAX_STEPS = 6
CJK = re.compile(r"[一-鿿]")


def execute_tool(tool_name: str, arguments: dict) -> dict:
    """只執行白名單中的本機函式，並安全處理錯誤的工具呼叫。"""
    function = TOOL_FUNCTIONS.get(tool_name)
    if function is None:
        return {"error": f"工具「{tool_name}」不存在。"}
    try:
        return function(**arguments)
    except (TypeError, ValueError) as error:
        return {"error": f"工具 {tool_name} 的參數不正確：{error}"}


def run_agent(chat_history: list[dict]) -> tuple[str, list[dict]]:
    """回答最新一則使用者訊息，並回傳本回合的工具軌跡。"""
    question = chat_history[-1]["content"]
    language = "Traditional Chinese" if CJK.search(question) else "English"
    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + chat_history[:-1]
        + [{"role": "system", "content": f"請使用 {language} 回答。"}]
        + chat_history[-1:]
    )
    trace = []

    for step in range(MAX_STEPS):
        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            tools=TOOL_SPECS,
            temperature=0.2,
        )
        message = response.choices[0].message
        if not message.tool_calls:
            return (message.content or "抱歉，目前無法產生回覆。" ).strip(), trace

        messages.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {"id": call.id, "type": "function", "function": {
                    "name": call.function.name, "arguments": call.function.arguments,
                }}
                for call in message.tool_calls
            ],
        })
        for call in message.tool_calls:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
                result = {"error": "模型傳送的 JSON 參數格式錯誤。"}
            else:
                result = execute_tool(call.function.name, arguments)
            trace.append({
                "step": step + 1,
                "tool": call.function.name,
                "arguments": arguments,
                "result": result,
            })
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

    return "抱歉，這項請求目前無法完成，請聯絡民宿櫃檯。", trace


# ---------------------------------------------------------------------------
# 4. Gradio 聊天介面與可見的工具軌跡
# ---------------------------------------------------------------------------
GREETING = (
    "歡迎來到海岸小屋民宿。您可以詢問房型、價格、入住或民宿服務。\n\n"
    "Welcome to Seaside Haven Guesthouse. Ask me about rooms, prices, check-in, "
    "or guesthouse services."
)
EMPTY_TRACE = "### 使用的工具\n\n（尚未呼叫工具）"

SAMPLE_QUESTIONS_EN = [
    "What time can I check in?",
    "Do you have a pet-friendly room?",
    "How much is the Seaside Suite for three nights?",
    "I need to change my reservation.",
]
SAMPLE_QUESTIONS_ZH = [
    "請問入住時間是幾點？",
    "有可以帶寵物的房間嗎？",
    "海景套房住三晚多少錢？",
    "我想更改訂房。",
]


def format_trace(trace: list[dict]) -> str:
    if not trace:
        return "### 使用的工具\n\n（此回覆不需要工具）"
    lines = ["### 使用的工具", ""]
    for entry in trace:
        lines.extend([
            f"**{entry['step']}. {entry['tool']}**", "",
            f"參數：`{json.dumps(entry['arguments'], ensure_ascii=False)[:180]}`", "",
            f"結果：`{json.dumps(entry['result'], ensure_ascii=False)[:300]}`", "",
        ])
    return "\n".join(lines)


def start_chat() -> list[dict]:
    return [{"role": "assistant", "content": GREETING}]


def add_user_message(user_text: str, chat_history: list[dict]) -> tuple[str, list[dict]]:
    user_text = user_text.strip()
    if not user_text:
        return "", chat_history
    return "", chat_history + [{"role": "user", "content": user_text}]


def api_history(chat_history: list[dict]) -> list[dict]:
    """只保留 OpenAI API 需要的 role 與純文字 content。

    Gradio 6 可能在聊天訊息加入介面專用欄位；這些欄位不應送到模型 API。
    """
    cleaned = []
    for message in chat_history:
        role = message.get("role")
        content = message.get("content")
        if isinstance(content, list):
            # Gradio 6 會把純文字包成 [{"type": "text", "text": "..."}]。
            content = "".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            )
        if role not in {"user", "assistant"} or not isinstance(content, str) or not content:
            continue
        cleaned.append({"role": role, "content": content})
    return cleaned


def answer_question(chat_history: list[dict]) -> tuple[list[dict], str]:
    if not chat_history or chat_history[-1]["role"] != "user":
        return chat_history, EMPTY_TRACE
    try:
        clean_history = api_history(chat_history)
        if not clean_history or clean_history[-1]["role"] != "user":
            raise ValueError("聊天訊息格式不正確。")
        answer, trace = run_agent(clean_history)
        panel = format_trace(trace)
    except Exception as error:
        print(f"Agent 呼叫失敗：{error!r}")
        answer = "抱歉，服務暫時無法使用。請檢查 API 設定後再試一次。"
        panel = f"### 使用的工具\n\n（呼叫失敗：{type(error).__name__}）"
    return chat_history + [{"role": "assistant", "content": answer}], panel


def find_available_port() -> int:
    """讓 Gradio 使用作業系統指派的可用本機埠，避免與既有服務衝突。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


with gr.Blocks(title="海岸小屋民宿客服 Agent") as demo:
    gr.Markdown(
        "## 海岸小屋民宿 — 客服 Agent\n"
        "房型與民宿資訊都來自本機資料庫；右側會顯示工具呼叫軌跡。"
    )
    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(value=start_chat(), height=440, label="民宿客服", **CHATBOT_KWARGS)
            with gr.Row():
                user_box = gr.Textbox(
                    placeholder="請詢問房型、價格、入住或民宿服務……",
                    show_label=False,
                    scale=8,
                )
                send_button = gr.Button("送出", variant="primary", scale=1)
                clear_button = gr.Button("清除", scale=1)
            with gr.Tabs():
                with gr.Tab("英文範例"):
                    gr.Examples(SAMPLE_QUESTIONS_EN, inputs=user_box)
                with gr.Tab("中文範例"):
                    gr.Examples(SAMPLE_QUESTIONS_ZH, inputs=user_box)
        with gr.Column(scale=2):
            trace_panel = gr.Markdown(EMPTY_TRACE)

    send_button.click(add_user_message, [user_box, chatbot], [user_box, chatbot]).then(
        answer_question, chatbot, [chatbot, trace_panel]
    )
    user_box.submit(add_user_message, [user_box, chatbot], [user_box, chatbot]).then(
        answer_question, chatbot, [chatbot, trace_panel]
    )
    clear_button.click(start_chat, outputs=chatbot).then(
        lambda: ("", EMPTY_TRACE), outputs=[user_box, trace_panel]
    )


if __name__ == "__main__":
    demo.launch(server_port=find_available_port())
