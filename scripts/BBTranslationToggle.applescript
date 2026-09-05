set scriptPath to "/Users/hieutt/Vibe Code/Baking-tools/BB-Translation/scripts/pipeline_toggle.sh"

try
	set toggleResult to do shell script quoted form of scriptPath
on error errMsg
	display notification errMsg with title "BB-Translation" subtitle "Lỗi"
	return
end try

if toggleResult contains "STARTED" then
	display notification "Đã mở trình duyệt tại localhost:8000" with title "BB-Translation" subtitle "Đã khởi động"
else if toggleResult contains "STOPPED" then
	display notification "MinerU và app đã dừng" with title "BB-Translation" subtitle "Đã đóng"
else if toggleResult contains "FAILED_MINERU" then
	display notification "MinerU không khởi động được (xem /tmp/bb-mineru.log)" with title "BB-Translation" subtitle "Lỗi"
else if toggleResult contains "FAILED_APP" then
	display notification "App không khởi động được (xem /tmp/bb-app.log)" with title "BB-Translation" subtitle "Lỗi"
else
	display notification toggleResult with title "BB-Translation" subtitle "Kết quả"
end if
