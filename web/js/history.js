// Alpine.js app for web/history.html (US-12).

function historyApp() {
  return {
    jobs: [],
    total: 0,
    limit: 20,
    offset: 0,
    statusFilter: "",

    statusBadgeClass(status) {
      const map = {
        completed: "bg-green-100 text-green-700",
        failed: "bg-red-100 text-red-700",
        cancelled: "bg-gray-200 text-gray-700",
        // Architecture.md 6.11.4 Lop 3 — a system-initiated budget stop,
        // distinct from both an error (failed) and a user action (cancelled).
        cost_capped: "bg-purple-100 text-purple-700",
        translating: "bg-amber-100 text-amber-700",
        queued: "bg-blue-100 text-blue-700",
      };
      return map[status] || "bg-gray-100 text-gray-600";
    },

    async load() {
      const params = new URLSearchParams({ limit: String(this.limit), offset: String(this.offset) });
      if (this.statusFilter) params.set("status", this.statusFilter);
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
