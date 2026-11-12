# Lab: Xây dựng Status Investigation Agent

> **Hình thức: Bài cá nhân.** Mỗi cá nhân tự làm, tự tạo repo riêng và tự nộp link lên LMS.
>
> **Tên repo nộp:** `K5-L3A-DAY04-[HoVaTen]-[MSSV]-ReactLoopAgent` hoặc `K5-L3B-DAY04-[HoVaTen]-[MSSV]-ReactLoopAgent` (thay `[HoVaTen]` và `[MSSV]`, bỏ cả dấu ngoặc vuông) · **Nơi nộp:** [aithucchien.vinuni.edu.vn](https://aithucchien.vinuni.edu.vn)
>
> **Deadline (GMT+7):** ca 9:00–13:00 và 14:00–18:00 trước 23:59 cùng ngày, ca 16:30–20:00 trước 12:00 trưa hôm sau. Nộp muộn bị trừ điểm.

Tài liệu đi kèm: [GUIDE.md](GUIDE.md) · [SUBMISSION.md](SUBMISSION.md) · [RUBRIC.md](RUBRIC.md) · [CHECKPOINTS.md](CHECKPOINTS.md) · [RULES.md](RULES.md)

Bạn sẽ tự viết một agent loop bằng Python. Agent dùng dữ liệu thật từ GitHub Status và Cloudflare Status để hỗ trợ điều tra sự cố, sau đó bạn dùng trace và eval để kiểm tra cách agent hoạt động.

**Mục tiêu:** gọi LLM → thực thi tool → đưa kết quả trở lại LLM → lặp đến khi trả lời hoặc hết giới hạn. Thời lượng dự kiến: **4 giờ**, gồm nghỉ 10 phút. Lịch theo từng ca ở [CHECKPOINTS.md](CHECKPOINTS.md). Toàn bộ các bước trong [GUIDE.md](GUIDE.md) là nội dung của lab. Đọc thêm [RUBRIC.md](RUBRIC.md) để biết tiêu chí đánh giá.

## Agent hoạt động như thế nào?

Sơ đồ dưới đây mô tả bài chính với hai tools; phần bonus dùng bộ tools riêng. Agent nhận câu hỏi cùng system prompt và lịch sử hội thoại. LLM đề xuất tool call; Python thực thi tool, đưa kết quả về context rồi gọi LLM tiếp. Quá trình dừng khi có câu trả lời, gặp lỗi hoặc hết giới hạn bước.

<img src="assets/agent-architecture.svg" alt="Sơ đồ agent: user, conversation context, LLM, Python agent loop và hai tools truy cập GitHub Status hoặc Cloudflare Status" width="1200">

## Một vòng thực hành

Sau khi xây agent, bạn chạy eval, phân tích kết quả, cải tiến rồi chạy lại cùng bộ eval để so sánh.

<img src="assets/lab-workflow.svg" alt="Vòng lặp: xây agent, chạy eval, phân tích lỗi, cải tiến và quay lại chạy eval" width="1200">

## Lộ trình học

1. Khám phá status tools và tự code agent loop.
2. Thêm xử lý lỗi, giới hạn bước và trace.
3. Chạy bộ eval 22 case và nhận điểm 0–100 cùng giải thích từng case.
4. Phân tích lỗi trong trace; chọn một thay đổi và cải tiến agent.
5. Chạy lại cùng bộ eval một lần, so sánh điểm, lỗi và chi phí.

Các bước trên là một lab thống nhất. Timeline, yêu cầu và tiêu chí hoàn thành được mô tả trong [GUIDE.md](GUIDE.md).

## Thử thách tùy chọn: +15 điểm

Sau bài chính, bạn có thể mở rộng agent để điều tra **GitHub, Cloudflare, Vercel, npm và DigitalOcean** qua 5 status tools và một tool đọc incident theo trang. Bộ bonus có 10 case riêng về dữ liệu dài, nhiều nhà cung cấp, pagination, lỗi định dạng, rate limit và prompt injection. Xem [GUIDE.md](GUIDE.md#thử-thách-bonus-tùy-chọn--15-điểm) để thực hiện.

Điểm bài chính tối đa 85; bonus tối đa 15, tổng tối đa 100. Không cần làm bonus để hoàn thành bài chính.

## 1. Chuẩn bị

- Python **3.10+**, có Internet và API key của **một** trong năm provider.
- Chọn model có hỗ trợ **tool calling**. API provider/model có thể phát sinh chi phí.
- Không cần cài package: project dùng Python standard library.

Fork repo đề về tài khoản của bạn, đổi tên theo mẫu (chi tiết ở [SUBMISSION.md](SUBMISSION.md)), clone về máy rồi mở terminal tại thư mục đó:

```bash
python3 --version
export PROVIDER=openai
export MODEL='<tên-model-có-tool-calling>'
export OPENAI_API_KEY='<api-key>'
```

Chọn cấu hình khác nếu cần:

| `PROVIDER` | Biến chứa key | `MODEL` |
|---|---|---|
| `openai` | `OPENAI_API_KEY` | Tên model OpenAI bạn được cấp quyền dùng. |
| `gemini` | `GEMINI_API_KEY` | Tên model Gemini hỗ trợ function calling. |
| `anthropic` | `ANTHROPIC_API_KEY` | Tên model Claude hỗ trợ tool use. |
| `openrouter` | `OPENROUTER_API_KEY` | Model ID đầy đủ trên OpenRouter, thường có dạng `provider/model`. |
| `opencode-go` | `OPENCODE_GO_API_KEY` | Ví dụ: `deepseek-v4.1-flash`; cần key và quyền truy cập OpenCode Go. |

Ví dụ chuyển sang Gemini: `export PROVIDER=gemini`, đặt `GEMINI_API_KEY` và `MODEL` phù hợp. Chọn một provider; không cần tất cả key. File `.env.example` chỉ là mẫu: chương trình **không tự đọc `.env`**. Có thể chạy `cp .env.example .env`, điền key rồi chạy `source .env` trong mỗi terminal mới. Trên Windows, dùng Git Bash để chạy đúng các lệnh này, hoặc thay `python3` bằng `python` và đặt biến bằng `$env:TEN_BIEN='gia_tri'` trong PowerShell. Không commit key hay trace chứa dữ liệu nhạy cảm.

Ví dụ dùng OpenCode Go (đặt key trong terminal hoặc cách quản lý secret của bạn):

```bash
export PROVIDER=opencode-go
export MODEL=deepseek-v4.1-flash
export OPENCODE_GO_API_KEY='<key-OpenCode-Go>'
```

Adapter gửi User-Agent riêng và giữ cùng session ID cho các lượt trong một run theo [hướng dẫn OpenCode Go](https://opencode.ai/docs/console/go/#where-can-i-use-it). Key phải còn hiệu lực và workspace cần có quyền dùng model. Nếu dùng judge provider khác, xem `--judge-provider` và `--judge-model` trong GUIDE.

Adapter dùng Chat Completions cho OpenAI, Gemini compatibility, OpenRouter và OpenCode Go; Anthropic dùng Messages API. Nó phục vụ **tool calling cơ bản**, không bao phủ mọi tính năng đặc thù model như extended thinking. Khi provider từ chối model hoặc hết quota, kiểm tra quyền truy cập, model ID và key. Xem tài liệu: [OpenAI](https://developers.openai.com/api/docs/guides/function-calling), [Gemini](https://ai.google.dev/gemini-api/docs/openai), [Anthropic](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works), [OpenRouter](https://openrouter.ai/docs/guides/features/tool-calling), [OpenCode Go](https://opencode.ai/docs/console/go/).

## 2. Chạy thử

Sau khi hoàn thiện `agent.py`:

```bash
python3 run.py 'GitHub Actions hiện có sự cố không? Hãy kiểm tra incident gần đây.'
python3 run.py --mode live 'Cloudflare có incident liên quan cache purge không?'
python3 -m unittest discover -s tests -v
python3 evals/run_evals.py --case E2 --output eval_results_e2.json
python3 evals/run_evals.py --output eval_before.json
# Sau khi phân tích và cải tiến agent:
python3 evals/run_evals.py --output eval_after.json
```

- Mặc định là `snapshot`: đọc dữ liệu được lưu sẵn; vẫn cần LLM API key.
- `live`: gọi status API thật, dữ liệu thay đổi và cần Internet. Cloudflare khuyến nghị User-Agent có thông tin liên hệ; giảng viên có thể đặt `export STATUS_USER_AGENT="StatusAgentLab/1.0 (contact: email-lop@example.edu)"` bằng thông tin liên hệ thực của lớp.
- Unit tests dùng fake provider, không cần key. **Ban đầu một số tests thất bại** vì `agent.py` chưa được implement.
- Eval gọi LLM cho agent và LLM judge, tiêu tốn token. Mỗi case có điểm 0–100; điểm tổng là trung bình các case. Nếu có case chưa chấm được, điểm tổng là `null`. Đọc giải thích và trace; điểm judge là ước lượng, cần kiểm tra lại.
- Có thể override bằng `--provider`, `--model`, `--max-steps`. `--max-steps` là số lần gọi model, mặc định 6 với `run.py`, 8 với `evals/run_evals.py` và 16 khi chạy eval bonus.

Snapshot bài chính được lưu ngày 09/11/2026; snapshot của ba API bổ sung được lưu ngày 10/11/2026. Không dùng nó để trả lời tình trạng hiện tại trong thực tế. Khi chạy live, API có thể rate limit, timeout hoặc thay đổi dữ liệu.

## Tài liệu tham khảo: làm việc với coding agent

Các tài liệu dưới đây giúp bạn tham khảo cách tổ chức việc viết code với AI; **không phải task của lab và không cần cài đặt để hoàn thành bài**.

Trong bài lab, *agent loop* là vòng LLM → tool → kết quả. Khi dùng coding agent, một vòng làm việc khác có thể là: mô tả yêu cầu và tiêu chí hoàn thành → agent sửa code → chạy tests/kiểm tra → đọc kết quả và điều chỉnh. “Loop engineering” trong ngữ cảnh này là thiết kế cách cung cấp nhiệm vụ, phản hồi và điều kiện dừng cho quá trình đó.

| Chủ đề | Tài liệu | Bạn sẽ tìm thấy gì? |
|---|---|---|
| Instructions | [Codex: AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md) · [Claude Code: project instructions](https://code.claude.com/docs/en/memory) | Cách cung cấp quy ước dự án và lệnh kiểm tra cho coding agent. |
| Skills | [OpenAI: Build skills](https://learn.chatgpt.com/docs/build-skills) · [Claude Code: Skills](https://code.claude.com/docs/en/skills) | Cách đóng gói một workflow có thể dùng lại, ví dụ review code hoặc debug. |
| Hooks | [Codex: Hooks](https://learn.chatgpt.com/docs/hooks) · [Claude Code: Hooks](https://code.claude.com/docs/en/hooks) | Cách chạy kiểm tra tại các sự kiện như trước/sau tool call hoặc khi agent kết thúc. |
| Workflow | [GitHub Spec Kit](https://github.github.com/spec-kit/quickstart) · [Superpowers](https://github.com/obra/superpowers) | Hai ví dụ workflow: đi từ yêu cầu đến kế hoạch, implementation và kiểm chứng. Superpowers là dự án cộng đồng. |
| Vòng lặp tự động | [Ralph: bài viết gốc](https://ghuntley.com/ralph/) · [Claude Code Ralph Loop plugin](https://github.com/anthropics/claude-plugins-official/blob/main/plugins/ralph-loop/README.md) | Ví dụ cho agent tiếp tục lặp trên một nhiệm vụ; plugin dùng Stop hook và là một implementation riêng của ý tưởng này. |
| Thiết kế môi trường | [OpenAI: Harness engineering](https://openai.com/index/harness-engineering/) | Vai trò của tests, feedback và môi trường khi giao công việc cho coding agent. |

Nếu thử workflow tự động, hãy đặt giới hạn lượt chạy hoặc chi phí, có điều kiện dừng và tự kiểm tra kết quả. Tests pass là bằng chứng hữu ích, nhưng vẫn cần xem code và đối chiếu yêu cầu. Đọc kỹ quyền và hướng dẫn của từng công cụ trước khi cài hoặc chạy plugin/hook.
