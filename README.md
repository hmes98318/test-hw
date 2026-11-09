# 海岸小屋民宿：AI 客服 Agent

這是一個服務虛構高雄民宿的 AI 文字客服 Agent。它透過工具讀取本機 SQLite 資料庫來回答房型與民宿服務問題。模型不憑記憶回答：它先選擇工具，Python 程式查詢資料或計算住宿費，再由模型根據工具結果撰寫回覆。

## 功能

- 查詢民宿資訊與房型價格
- 計算住宿總費用
- 搜尋寵物與取消退款規定（RAG）
- 資料不存在時不自行編造答案

## 工具

| 工具 | 用途 |
|---|---|
| `get_guesthouse_info` | 查詢入住、早餐、地址、停車等民宿資訊。 |
| `search_rooms` | 查詢房型、房價、人數與房間特色。 |
| `calculate_stay` | 計算每晚房價乘以住宿晚數。 |
| `search_guesthouse_rules` | 從 `guesthouse_rules.txt` 搜尋寵物與取消退款規定。 |
| `transfer_to_human` | 提供真人客服聯絡方式，處理特殊情況。 |

## 啟動

```bash
pip install -r requirements.txt
cp .env.example .env
python app.py
```

在 `.env` 填入自己的 API 設定後，開啟終端機顯示的本機網址。

## 測試問題

- `海景套房住三晚多少錢？`
- `花園雙床房多少錢？可以帶寵物嗎？`
- `你們有游泳池嗎？`

請勿提交 `.env` 或 API 金鑰。
