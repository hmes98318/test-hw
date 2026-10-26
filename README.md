# 海岸小屋民宿：AI 客服 Agent

這是一個服務虛構高雄民宿的 AI 文字客服 Agent。它透過工具讀取本機 SQLite 資料庫來回答房型與民宿服務問題。模型不憑記憶回答：它先選擇工具，Python 程式查詢資料或計算住宿費，再由模型根據工具結果撰寫回覆。

> 課程作業：G 單元──我的 AI 客服 Agent（資料庫與工具）  
> 學生：**[請填入學號與姓名]**

> 請在完成測試後，將主畫面與工具軌跡截圖加到本 README，並在報告中附上四類問題的畫面。

## 服務對象與使用情境

本客服服務海岸小屋民宿的潛在住客與既有住客，處理房型、每晚房價、入住、停車、早餐、寵物與 Wi-Fi 等常見問題。使用者可用英文或繁體中文提問。

客訴、訂房異動、特殊例外與資料庫沒有的民宿問題，會轉交真人人員，而不是由模型猜測答案。

## 工具

| 工具 | 功能 | 客人可能的問法 |
|---|---|---|
| `get_guesthouse_info(topic)` | 查詢常見民宿資訊 |「請問幾點可以入住？」|
| `search_rooms(keyword)` | 查詢房型、房價、人數、特色與可用狀態 |「有適合四個人的房間嗎？」|
| `calculate_stay(room_name, nights)` | 由 Python 計算「每晚房價 × 晚數」 |「海景套房住三晚多少錢？」|
| `transfer_to_human()` | 提供真人客服聯絡資訊 |「我想更改訂房。」|

## 資料與資料庫

程式啟動時會重建 `guesthouse.db`。資料庫檔不會上傳，而是由下列 CSV 檔自動產生。

| SQLite 資料表 | CSV 檔 | 內容 |
|---|---|---|
| `guesthouse_info` | `guesthouse_info.csv` | 11 個主題：入住、停車、早餐、付款、寵物、取消政策等 |
| `rooms` | `rooms.csv` | 15 筆房型資料：房價、人數、可用狀態與特色 |

## 安裝與執行

1. 請使用 Python 3.10 以上版本，安裝套件：

   ```bash
   pip install -r requirements.txt
   ```

2. 將 `.env.example` 複製為 `.env`，並填入 `API_KEY`。端點與模型必須支援 OpenAI-compatible tool calling。

   ```bash
   cp .env.example .env        # macOS / Linux
   copy .env.example .env      # Windows
   ```

3. 啟動程式：

   ```bash
   python app.py
   ```

4. 開啟終端機顯示的本機網址，通常為 `http://127.0.0.1:7860`。

## 工具選擇測試

設定好 `.env` 後，執行以下 12 題測試，並把分數與修正過程寫入作業報告：

```bash
python tool_choice_test.py
```

測試題之間會稍微暫停，避免超過 API 的速率限制。若某題選錯工具，優先修改該工具的 `description` 或 `SYSTEM_PROMPT` 裡的分派規則，再重新測試。

## 安全注意事項

- `.env` 含有 API 金鑰，絕不可提交至 GitHub。
- `guesthouse.db` 由 CSV 自動產生，絕不可提交至 GitHub。
- 本專案中的民宿名稱、電話、價格與政策皆為虛構練習資料。
