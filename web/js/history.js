// Alpine.js app for web/history.html (US-12).

function historyApp() {
  return {
    jobs: [],
    total: 0,
    limit: 20,
    offset: 0,
    statusFilter: "",
    // US-15 S15-7/BR-PARSE-04: mac dinh chi hien job dich, khong tron voi
    // job parse_only vao "translation history".
    jobTypeFilter: "translate",

    statusBadgeClass(status) {
      const map = {
        completed: "bg-green-100 text-green-700",
        failed: "bg-red-100 text-red-700",
        cancelled: "bg-gray-200 text-gray-700",
        // Architecture.md 6.11.4 Lop 3 — a system-initiated budget stop,
        // distinct from both an error (failed) and a user action (cancelled).
        cost_capped: "bg-purple-100 text-purple-700",
        translating: "bg-amber-100 text-amber-700",
        // US-15: MinerU dang chay cho job_type=parse_only.
        parsing: "bg-amber-100 text-amber-700",
        queued: "bg-blue-100 text-blue-700",
      };
      return map[status] || "bg-gray-100 text-gray-600";
    },

    // b. US moi (2026-09-06): hien chi phi THAT (actual_cost) khi job da
    // hoan tat; hien uoc tinh (estimated_cost) khi chua; "-" khi khong co
    // du lieu nao (job vua tao, chua uoc tinh lan nao).
    formatCost(job) {
      if (job.actual_cost != null) {
        return `$${job.actual_cost.toFixed(2)} (${job.cost_source})`;
      }
      if (job.estimated_cost != null) {
        return `ước tính: $${job.estimated_cost.toFixed(2)}`;
      }
      return "-";
    },

    // US-19 (Architecture.md 6.17.3, BR-HIST-02): "total_pages" la NULL cho
    // EPUB (khong ap dung o dot nay) va cho job cu truoc migration nay.
    formatTotalPages(job) {
      return job.total_pages != null ? String(job.total_pages) : "-";
    },

    // US-19 (Architecture.md 6.17.3, EC-19.2): API luon tra so giay float —
    // format "X phut Y giay" o day, KHONG dua backend format san.
    // BR-HIST-02: job dang chay (duration_seconds == null) hien "-", khong
    // dem tien (tranh phai refresh dinh ky).
    formatDuration(job) {
      if (job.duration_seconds == null) return "-";
      const totalSeconds = Math.round(job.duration_seconds);
      const minutes = Math.floor(totalSeconds / 60);
      const seconds = totalSeconds % 60;
      if (minutes === 0) return `${seconds} giây`;
      return `${minutes} phút ${seconds} giây`;
    },

    async load() {
      const params = new URLSearchParams({ limit: String(this.limit), offset: String(this.offset) });
      if (this.statusFilter) params.set("status", this.statusFilter);
      if (this.jobTypeFilter) params.set("job_type", this.jobTypeFilter);
      const res = await fetch(`/api/jobs?${params}`);
      const body = await res.json();
      this.jobs = body.jobs;
      this.total = body.total;
    },

    // US moi (2026-09-06): xoá 1 job khỏi lịch sử — chỉ xoá DB row + file kết
    // quả (backend từ chối job đang chạy, 400: phải Dừng trước). Không đụng
    // tới file gốc trong data/uploads (xem docstring DELETE /api/jobs/{id}).
    async deleteJob(job) {
      if (!confirm(`Xoá job "${job.filename}" khỏi lịch sử? Không thể hoàn tác.`)) return;
      const res = await fetch(`/api/jobs/${job.id}`, { method: "DELETE" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        alert(body.detail || "Không xoá được job.");
        return;
      }
      await this.load();
    },
  };
}
