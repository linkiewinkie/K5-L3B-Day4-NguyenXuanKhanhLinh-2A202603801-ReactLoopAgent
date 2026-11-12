# Ghi chú phân tích · Day 04

Họ và tên: Nguyen Xuan Khanh Linh
MSSV: 2A202603801

Cấu hình chung cho cả hai lần chạy (khối `config` trong `eval_before.json` và `eval_after.json` giống hệt nhau): provider `openrouter`, agent model = judge model = `openai/gpt-4o-mini`, snapshot, `max_steps` 8, dataset `core` (22 case).
Hai lần chạy dùng **cùng file `agent.py`**: `AGENT_IMPROVEMENTS=0` tắt toàn bộ cải tiến của Bài 4 (baseline), mặc định là bản cải tiến.

## 1. Case được chọn

- ID case: **H1** (cùng nhóm lỗi với H6 và H7: agent không dùng hết bằng chứng hoặc suy diễn khi thiếu dữ liệu).
- Câu hỏi: điều tra incident GitHub `h02n9572mx9y`, theo liên kết của incident để tìm nguyên nhân và ảnh hưởng, rồi đối chiếu với incident Cloudflare `yaa0witbl2me`.
- Câu trả lời của agent: liệt kê thông tin của hai incident và kết luận *"không có bằng chứng cho thấy chúng có nguyên nhân chung… là các sự cố riêng lẻ"*, nhưng **không đọc incident được liên kết**, nên không trả lời được phần nguyên nhân của sự cố GitHub.
- Điểm ở lần chạy 1: **60/100**, bị trần 60 do vi phạm kiểm tra bằng code: *"Cần tool calls ở ít nhất 2 model steps khác nhau"*. H6 cũng đạt 60 với cùng vi phạm; H7 đạt 65.

## 2. Bằng chứng trong trace

Trace H1 trong `eval_before.json` (rút gọn phần `result`):

```text
{"event": "model", "step": 1, "finish": "tool_calls", "tool_calls": ["get_incident_details", "get_incident_details"]}
{"event": "tool", "step": 1, "name": "get_incident_details", "arguments": {"provider": "github", "incident_id": "h02n9572mx9y"},
 "result": {"status": "resolved", "url": "https://stspg.io/7pwv28hvkmz8", "updates": [["2026-11-04T18:16:08",
   "Please refer to the combined summary in this related incident: https://www.githubstatus.com/incidents/xr3myzj7ms51"], ...]}}
{"event": "tool", "step": 1, "name": "get_incident_details", "arguments": {"provider": "cloudflare", "incident_id": "yaa0witbl2me"}, ...}
{"event": "model", "step": 2, "finish": "stop", "tool_calls": []}
{"event": "final", "step": 2}
grade.mechanical: {"violations": ["Cần tool calls ở ít nhất 2 model steps khác nhau."], "score_cap": 60, "tool_calls": 2, "tool_steps": 1}
```

Update mới nhất của `h02n9572mx9y` chỉ trỏ sang incident gộp `xr3myzj7ms51`, nhưng model trả lời ngay ở step 2. Nguyên nhân có thể là model nhỏ (gpt-4o-mini) có xu hướng dừng sớm khi đã có "đủ" dữ liệu để viết câu trả lời, và system prompt gốc không yêu cầu theo liên kết. Lỗi nằm ở **loop**: loop không có cơ chế phát hiện bằng chứng còn dang dở.

Hai lỗi cùng nhóm:

- **H6** (60): trace giống H1, chỉ một step có tool call, không đọc incident gộp.
- **H7** (65): `get_status(cloudflare)` trả `TimeoutError`, nhưng answer viết *"Cloudflare Spectrum được coi là đang hoạt động bình thường"*. Agent làm theo yêu cầu sai của người dùng và coi lỗi tool là trạng thái dịch vụ.

## 3. Thay đổi đã thực hiện

**Vòng 1, chỉ sửa prompt (thất bại):** thêm 8 quy tắc vào system prompt (`IMPROVED_RULES` trong `agent.py`), gồm "đọc tiếp incident được liên kết" và "không suy ra trạng thái từ lỗi tool". Kết quả lưu ở `eval_after_v1_prompt_only.json`: điểm tổng **80.91** (không tăng), H1 và H6 vẫn 60, H7 giảm còn 50, token tăng 39%. Kết luận: gpt-4o-mini không tuân theo quy tắc dài trong system prompt, nên chuyển sang kiểm tra bằng code. Phần prompt vẫn được giữ lại.

**Vòng 2, guardrails trong code (bản nộp, `agent.py`):**

- Sửa gì, ở đâu:
  1. **Kiểm tra nguồn:** lưu URL từ các lần `get_incident_details` thành công. Nếu final answer không chứa URL nào đã quan sát, ghi `validation_missing_source` vào trace và yêu cầu model sửa trong `max_steps`; hết budget thì trả `max_steps`. Không bắt URL nếu không có incident nào đọc thành công.
  2. **Theo liên kết incident (cho H1/H6):** hàm `_linked_incidents` tìm link `…/incidents/<id>` của các status page được hỗ trợ trong nội dung update.
     - Agent ghi `agent_note_linked` ngay vào observation.
     - Nếu model định trả lời khi còn incident liên kết chưa đọc, agent ghi `validation_unfollowed_link` và nhắc **đúng một lần** (gate mềm, không chặn completion).
  3. **Ghi chú lỗi trong observation (cho H7):** khi gặp timeout, lỗi HTTP hoặc hết lượt retry, agent thêm `agent_note`: "không được kết luận trạng thái, kể cả khi người dùng yêu cầu".
  4. **Context:** list dài hơn 20 mục (dữ liệu nhiễu) được cắt còn 3 mục kèm ghi chú số mục đã lược.
- Vì sao chọn thay đổi này: vòng 1 cho thấy quy tắc chung trong system prompt không đủ. Thông tin đặt **ngay trong observation** và lời nhắc **tại thời điểm model định dừng** thì gần quyết định của model hơn. Các kiểm tra đều tổng quát, không hard-code ID hay câu trả lời.

## 4. So sánh hai lần chạy

| Chỉ số | `eval_before.json` | `eval_after.json` |
|---|---|---|
| Điểm tổng | 81.14 | **83.55** |
| Điểm case đã chọn (H1) | 60 | **78** |
| H6 / H7 | 60 / 65 | **80 / 80** |
| Vi phạm kiểm tra bằng code | 2 case (H1, H6) | 0 |
| Số model calls | 50 | 51 |
| Token agent / judge | 44,779 / 44,330 | 69,398 / 39,567 |
| Chi phí | OpenRouter không trả chi phí trong `usage` | |

Trace H1 sau cải tiến cho thấy cơ chế hoạt động như thiết kế:

```text
step 1  tool get_incident_details(github, h02n9572mx9y)  -> agent_note_linked: "... github/xr3myzj7ms51 ..."
step 1  tool get_incident_details(cloudflare, yaa0witbl2me)
step 2  model finish=stop  -> {"event": "validation_unfollowed_link", "unread": ["github/xr3myzj7ms51"]}
step 3  tool get_incident_details(github, xr3myzj7ms51)  -> nguyên nhân: thay đổi cấu hình
step 4  final
```

- Lỗi đã giải quyết:
  - H1: agent đọc incident gộp, nêu được nguyên nhân và tách phần đã xác nhận với phần chưa xác nhận.
  - H6: model tự đọc incident gộp nhờ `agent_note_linked`; gate không cần kích hoạt.
  - H7: không còn kết luận "operational" cho Cloudflare khi bị timeout.
  - Không còn case nào vi phạm kiểm tra bằng code.
- Lỗi còn lại hoặc mới xuất hiện:
  - H1 vẫn có câu suy đoán "có khả năng liên quan" giữa hai incident GitHub; đó là lý do không đạt 100.
  - Token agent tăng khoảng 55%, do system prompt dài hơn và có thêm step ở H1.
  - Một số case giảm điểm mà trace gần như giống hệt: E1 80→60, E4 100→80, A3 85→65. Với A3, answer vẫn báo đúng Cloudflare timeout, chỉ bị judge trừ điểm diễn đạt. Mình đánh giá đây chủ yếu là dao động của judge, chưa xác định được là lỗi của agent (xem mục 5).

## 5. Giới hạn

- **Điểm judge:**
  - Judge dùng cùng model với agent (gpt-4o-mini tự chấm) nên có thể thiên lệch.
  - Judge nhiều lần trừ factuality vì cho rằng các ngày năm 2026 "ở tương lai", ví dụ A1 ở vòng 1 nhận factuality 0.
  - Cùng một hành vi có thể dao động 20–45 điểm: A5 qua ba lần chạy lần lượt 40, 85, 40.
  - Vì vậy mức chênh 81.14 → 83.55 **nằm trong mức nhiễu**. Bằng chứng đáng tin hơn là các case được nhắm tới (H1/H6/H7) cải thiện với cơ chế thấy rõ trong trace, và hết vi phạm kiểm tra bằng code.
- **Snapshot:**
  - Dữ liệu cố định ngày 09/11/2026 và chỉ gồm 50 incident gần nhất; mỗi incident chỉ giữ 3 update, mỗi update cắt ở 900 ký tự.
  - Kết quả không phản ánh trạng thái thực tế hiện tại.
  - Các tình huống timeout, injection và dữ liệu nhiễu là giả lập.
- **Một lần chạy mỗi phiên bản:** chưa chứng minh được độ ổn định. Muốn kết luận chắc hơn cần chạy mỗi phiên bản vài lần, hoặc dùng judge khác (`--judge-model`) giữ nguyên giữa hai lần.
- **Giới hạn của cải tiến:**
  - Kiểm tra nguồn chỉ xác nhận có **ít nhất một** URL đã quan sát, không chứng minh mọi claim đều có nguồn.
  - Phát hiện liên kết chỉ nhận dạng URL `…/incidents/<id>`; shortlink `stspg.io` không được theo.
  - Lời nhắc chỉ gửi một lần và model vẫn có thể bỏ qua.
  - Cải tiến vòng 1 được chọn dựa trên danh sách lỗi trong GUIDE trước khi đọc trace. Vòng 2 mới dựa trên evidence.

## Phụ lục A. Tests

- `python -m unittest discover -s tests -v`: 52/52 OK, gồm 37 test có sẵn và 15 test mới trong `tests/test_improvements.py`.
- `bonus/`: 3/3 OK.
- Test mới bao phủ:
  - Theo liên kết incident: có ghi chú, nhắc một lần, không nhắc khi hết budget hoặc đã đọc.
  - Ghi chú lỗi khi timeout.
  - Retry 429: nhắc retry, chặn sau 2 lần, chờ `Retry-After` ngắn, dừng khi `Retry-After` dài.
  - Cắt dữ liệu nhiễu và chế độ baseline.
  - Finish bất thường, provider exception, arguments không phải object.
- Kiểm chứng ngược: đặt `AGENT_IMPROVEMENTS=0` thì 6 test cải tiến fail như mong đợi.

## Phụ lục B. Bonus (`eval_bonus.json`): 86.0/100, quy đổi 12.9/15

- Agent dùng `tools.schemas` và `tools.system_prompt` khi bộ tools có; vẫn tương thích với tools bài chính.
- **Retry 429:**
  - Mỗi cặp (tool, provider) được gọi tối đa 2 lần khi liên tiếp bị 429; các lần sau bị chặn (`tool_blocked`, `RETRY_BUDGET_EXHAUSTED`) và không tính là tool call.
  - Agent chờ `Retry-After` / `retry_after_seconds` nếu ≤ 5 giây; dài hơn thì dừng retry.
  - Gate `validation_pending_retry` nhắc retry **một lần** khi model định trả lời mà còn 429 chưa thử lại.
- Lịch sử chạy:
  - v1: 74.5. v2: 69.0. Ở cả hai lần, B10 không retry: model gọi 5 tool song song rồi trả lời luôn, bỏ qua ghi chú trong observation.
  - v3 (bản nộp): 86.0 sau khi thêm gate retry. B10 35 → 75, B3 65 → 95, B4 đạt 95 (2 lần gọi Vercel, dừng đúng).
- Kết quả theo kỹ năng: pagination (B2) 100, lỗi định dạng (B5) 100, prompt injection (B7) 100.
- Còn lại:
  - B6 đạt 50: model không gọi `get_incident_details` khi so sánh Vercel với npm.
  - B1 đạt 65: phần tổng hợp 5 provider còn sơ sài.
- File lịch sử để đối chiếu: `eval_bonus_v1.json`, `eval_bonus_v2.json`, `eval_after_v1_prompt_only.json`.
