# FIT HUIT Telegram Notifier

Bot này chạy bằng GitHub Actions, không cần VPS. Mỗi 30 phút workflow sẽ vào `https://fit.huit.edu.vn/thong-bao`, kiểm tra bài mới, rồi gửi vào Telegram channel.

## Cách dùng

1. Tạo một GitHub repository mới.
2. Upload toàn bộ file trong thư mục này lên repository đó.
3. Vào `Settings -> Secrets and variables -> Actions -> New repository secret` và tạo 2 secret:

```text
TELEGRAM_BOT_TOKEN=<token từ BotFather>
TELEGRAM_CHAT_ID=@ten_channel_cua_ban
```

4. Vào `Actions -> Check FIT HUIT notices -> Run workflow` để chạy thử lần đầu.

Lần chạy đầu chỉ tạo `seen.json` và không gửi Telegram, để tránh spam các thông báo cũ. Từ lần chạy sau, nếu có thông báo mới thì bot mới gửi.

## Lưu ý

- Channel public có thể dùng `TELEGRAM_CHAT_ID=@ten_channel`.
- Channel private cần dùng numeric chat id.
- Bot phải được thêm vào channel và có quyền post message.
- Nếu repo private, nhớ kiểm tra quota Actions của tài khoản.
