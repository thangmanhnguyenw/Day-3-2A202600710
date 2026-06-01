# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: Nguyễn Trần Mạnh Thắng 
- **Student ID**: 2A202600710
- **Date**: 1/6/2026

---

## I. Technical Contribution (15 Points)

*Describe your specific contribution to the codebase (e.g., implemented a specific tool, fixed the parser, etc.).*

- **Modules Implementated**:  **hoàn thiện ReAct Agent** và **cải thiện planner lịch trình di chuyển**
- **Code Highlights**: Full
- **Documentation**: 
- sinh ra `Thought`
- gọi tool bằng `Action`
- nhận `Observation`
- tiếp tục suy luận đến khi có `Final Answer`

---

## II. Debugging Case Study (10 Points)

*Analyze a specific failure event you encountered during the lab using the logging system.*

- **Problem Description**: nhập địa chỉ nếu không có | sẽ dễ bị lỗi sai cú pháp
- **Log Source**: [Link or snippet from `logs/YYYY-MM-DD.log`]
- **Diagnosis**: vì cấu trúc nhập là time| locate | do
- **Solution**: thêm phần mẫu để người dùng nhập cho đúng 

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

*Reflect on the reasoning capability difference.*

1. **Reasoning**: `Thought` giúp agent thể hiện được **quá trình suy luận từng bước** trước khi hành động, nếu chỉ dùng chatbot thuần túy, mô hình có thể trả lời “nên đi xe máy” hoặc “nên đi sớm hơn” nhưng đó chỉ là phỏng đoán ngôn ngữ.  
Ngược lại, với ReAct:
  - agent suy nghĩ rằng cần lấy lịch trình
  - gọi tool để tính commute + weather
  - sau đó mới đưa ra quyết định dựa trên observation
2. **Reliability**: **Khi prompt chưa rõ**
  - Mô hình dễ trả format sai
  - dễ lặp action
  - dễ không tạo được `Final Answer`

1. **Observation**: Phần `Observation` là điểm khác biệt quan trọng nhất giữa chatbot và agent.
  Với chatbot bình thường:
  - mô hình thường chỉ dựa trên prompt gốc
  - không có cơ chế nhận phản hồi từ môi trường thực thi
  Với agent:
  - observation đóng vai trò như “feedback loop”
  - sau mỗi action, mô hình có thêm dữ liệu mới để cập nhật suy luận

---

## IV. Future Improvements (5 Points)

*How would you scale this for a production-level AI agent system?*

- **Scalability**: có thể mở rộng thêm cho một lịch trình hằng ngày, job, phương tiện hiện có ..... 
- **Safety**: Tôi sẽ thêm một lớp “supervisor” hoặc “guardrail” trước khi agent thực thi action, nhằm:
  - kiểm tra tool name có hợp lệ không
  - kiểm tra tham số JSON có đủ và an toàn không
  - phát hiện hành vi lặp bất thường
  - chặn các action không mong muốn trước khi thực thi
- **Performance**: Trong tương lai, nếu số lượng tool tăng lên, tôi sẽ:
  - xây dựng cơ chế tool retrieval hoặc tool ranking
  - dùng vector DB / embedding để chọn tool phù hợp thay vì đưa toàn bộ tool vào prompt
  - cache lại các geocoding / weather / route thường gặp để giảm số lần gọi API

---

> [!NOTE]
> Submit this report by renaming it to `REPORT_[YOUR_NAME].md` and placing it in this folder.

