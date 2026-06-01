# Group Report: Lab 3 - Production-Grade Agentic System

- **Team Name**: soloteam
- **Team Members**: Nguyễn Trần Mạnh Thắng 
- **Deployment Date**:1/6/2026

---

## 1. Executive Summary

*Brief overview of the agent's goal and success rate compared to the baseline chatbot.*

- **Success Rate**: thời gian khá ổn nhưng còn những giá tiền thì còn hơi giả
- **Key Outcome**: [e.g., "Our agent solved 40% more multi-step queries than the chatbot baseline by correctly utilizing the Search tool."]

---

## 2. System Architecture & Tooling

### 2.1 ReAct Loop Implementation

*Diagram or description of the Thought-Action-Observation loop.*

### 2.2 Tool Definitions (Inventory)


| Tool Name                | Input Format   | Use Case                                           |
| ------------------------ | -------------- | -------------------------------------------------- |
| `calc_tax`               | `json`         | Calculate VAT based on country code.               |
| `search_api`             | `string`       | Retrieve real-time information from Google Search. |
| fetch_weather_forecast   | lat/lon + ngày | Lấy dữ liệu thời tiết                              |
| resolve/geocode location | string         | Chuẩn hóa hoặc xác định địa điểm                   |


### 2.3 LLM Providers Used

- **Primary**: GPT-4o-mini
- **Secondary (Backup)**: Gemini 1.5 Flash

---

## 3. Telemetry & Performance Dashboard

*Analyze the industry metrics collected during the final test run.*

- **Average Latency (P50)**: [e.g., 1200ms]
- **Max Latency (P99)**: [e.g., 4500ms]
- **Average Tokens per Task**: [e.g., 350 tokens]
- **Total Cost of Test Suite**: [e.g., $0.05]
- chưa lưu log

---

## 4. Root Cause Analysis (RCA) - Failure Traces

*Deep dive into why the agent failed.*

### Case Study:Agent lặp action hoặc parse sai địa điểm

- **Input**: "Lập kế hoạch đi lại trong ngày từ nhà đến Quận 1, sau đó đi Bình Dương"
- **Observation**: Agent hoặc demo parser có thể parse sai địa điểm nhiều từ như:
  - “Quận 1” thành `Quận`
  - “Bình Dương” thành `Bình`
- **Root Cause**: parser input ở demo chưa đủ mạnh với địa điểm nhiều từ
- prompt chưa đủ chặt để ép mô hình kết thúc bằng `Final Answer`

---

## 5. Ablation Studies & Experiments

### Experiment 1: Prompt v1 vs Prompt v2

- **Diff**: Thêm hướng dẫn rõ hơn về:
  - cách gọi `plan_day_schedule`
  - định dạng `Thought / Action / Final Answer`
  - yêu cầu không lặp action
  - ví dụ few-shot cụ thể
- **Result**:Prompt mới giúp giảm lỗi:
  - gọi tool sai định dạng
  - lặp action
  - thiếu `Final Answer`

### Experiment 2 (Bonus): Chatbot vs Agent


| Case       | Chatbot Result | Agent Result | Winner    |
| ---------- | -------------- | ------------ | --------- |
| Simple Q   | Correct        | Correct      | Same      |
| Multi-step | Hallucinated   | Correct      | **Agent** |


---

## 6. Production Readiness Review

*Considerations for taking this system to a real-world environment.*

- **Security**: 
  - Cần kiểm tra và làm sạch input trước khi đưa vào tool
  - Không hard-code API key trong code
  - Dùng `.env` hoặc secret manager
- **Guardrails**: 
  - Giới hạn tối đa số vòng lặp (`max_steps`)
  - Dừng nếu action lặp lại
  - Validate tool arguments trước khi gọi
- **Scaling**:
  - cơ chế chọn tool thông minh
  - queue bất đồng bộ cho tool call
  - cache cho geocoding / weather / route

---

> [!NOTE]
> Submit this report by renaming it to `GROUP_REPORT_[TEAM_NAME].md` and placing it in this folder.

