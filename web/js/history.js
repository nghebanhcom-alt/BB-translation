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
    // US moi (2026-09-06): "+ Glossary" tren tung job — modal them 1 entry.
    addGlossaryJob: null,
    glossaryDraft: { term_en: "", term_vi: "" },
    glossaryError: "",

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

    // a. Mo modal them 1 cap thuat ngu vao glossary, goi tu hang cua 1 job.
    openAddGlossary(job) {
      this.addGlossaryJob = job;
      this.glossaryDraft = { term_en: "", term_vi: "" };
      this.glossaryError = "";
    },

    async saveGlossaryTerm() {
      const term_en = this.glossaryDraft.term_en.trim();
      if (!term_en) {
        this.glossaryError = "Thuật ngữ (EN) không được để trống.";
        return;
      }
      const res = await fetch("/api/glossary", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ term_en, term_vi: this.glossaryDraft.term_vi || null }),
      });
      if (res.ok) {
        this.addGlossaryJob = null;
      } else {
        const body = await res.json().catch(() => ({}));
        this.glossaryError = body.detail || "Không thêm được thuật ngữ.";
      }
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
