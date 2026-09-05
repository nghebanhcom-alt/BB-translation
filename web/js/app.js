// Alpine.js app for web/index.html (US-01 upload, US-02 batch, US-07 progress,
// US-09 download, US-14 provider selection incl. BR-PROVIDER-01).
//
// Increment 6 (Nhiem vu 1a) fixed the deviation that used to be documented
// here: `estimateCost()` no longer creates a real Job (see below) — it calls
// `POST /api/estimate`, which never touches the `jobs`/`batches` tables.

const ALL_PROVIDERS = ["deepseek", "gemini", "openai", "claude", "ollama", "deepl"];
const PDF_FILE_TYPES = new Set(["pdf_digital", "pdf_scan"]);
// Architecture.md 6.11.4 Lop 3: "cost_capped" is a NEW terminal status — the
// system stopped the job to protect the user's budget. Terminal like
// failed/cancelled (stops polling), but must render distinctly on screen.
const TERMINAL_STATUSES = new Set(["completed", "failed", "cancelled", "cost_capped"]);
// Nhiem vu 1b: trang thai con "song" — khoi phuc lai list nay khi index.html
// load (F5/chuyen tab quay lai), khong chi dua vao state trong bo nho Alpine.
const RESTORABLE_STATUSES = [
  "queued",
  "chunking",
  "translating",
  "post_processing",
  "merging",
  "completed",
  "cancelled",
  "cost_capped",
];
// Lop 0 point 1: models more expensive than gpt-4o-mini by roughly this
// factor (Architecture.md 6.11.2: measured directly from the $6.50
// incident — gpt-4o cost 16.67x what the same job would have cost on
// gpt-4o-mini).
const EXPENSIVE_OPENAI_MODELS = new Set(["gpt-4o"]);
// Nhiem vu 3: trang thai duoc coi la "dang chay", hien nut "Dung".
const CANCELLABLE_STATUSES = new Set([
  "queued",
  "chunking",
  "translating",
  "post_processing",
  "merging",
]);

function translationApp() {
  return {
    files: [],
    dragOver: false,
    uploadError: "",
    // Nhiem vu 2: provider -> { has_key, model } tu GET /api/settings, dung
    // de hien "OpenAI (gpt-4o-mini)" trong dropdown chon provider.
    providerSettings: {},

    async init() {
      await this.loadProviderSettings();
      await this.restoreRecentJobs();
    },

    async loadProviderSettings() {
      try {
        const res = await fetch("/api/settings");
        if (res.ok) {
          const body = await res.json();
          this.providerSettings = body.providers || {};
        }
      } catch (err) {
        // non-fatal — dropdown just falls back to showing the bare provider name.
      }
    },

    // Nhiem vu 1b (mat trang thai khi chuyen tab): index.html la static
    // multi-page site (khong phai SPA) — chuyen trang la full page reload,
    // state Alpine trong bo nho bien mat. Goi lai danh sach job gan
    // day/dang chay tu server thay vi chi dua vao upload session hien tai.
    async restoreRecentJobs() {
      try {
        const params = new URLSearchParams({
          status: RESTORABLE_STATUSES.join(","),
          limit: "20",
        });
        const res = await fetch(`/api/jobs?${params}`);
        if (!res.ok) return;
        const body = await res.json();
        this.files = body.jobs.map((job) => ({
          file_id: null, // job da ton tai — khong can file_id de tao job moi
          filename: job.filename,
          file_type: job.file_type,
          size_bytes: null,
          page_count: null,
          job_type: job.job_type,
          provider: job.model,
          output_mode: job.bilingual_path ? "bilingual" : "monolingual",
          costEstimate: null,
          job,
        }));
        this.files.forEach((f) => this.trackJob(f));
      } catch (err) {
        // non-fatal — user just sees an empty list, same as before this fix.
      }
    },

    availableProviders(fileType) {
      // BR-PROVIDER-01: DeepL cannot receive glossary/prompt on the PDF pipeline.
      return PDF_FILE_TYPES.has(fileType)
        ? ALL_PROVIDERS.filter((p) => p !== "deepl")
        : ALL_PROVIDERS;
    },

    providerLabel(providerName) {
      const model = this.providerSettings[providerName]?.model;
      return model ? `${providerName} (${model})` : providerName;
    },

    statusBadgeClass(status) {
      const map = {
        completed: "bg-green-100 text-green-700",
        failed: "bg-red-100 text-red-700",
        cancelled: "bg-gray-200 text-gray-700",
        // Architecture.md 6.11.4 Lop 3: distinct from both "failed" (nothing
        // errored) and "cancelled" (user didn't ask) — its own color so it
        // reads as neither an error nor a user action.
        cost_capped: "bg-purple-100 text-purple-700",
        translating: "bg-amber-100 text-amber-700",
        post_processing: "bg-amber-100 text-amber-700",
        merging: "bg-amber-100 text-amber-700",
        chunking: "bg-blue-100 text-blue-700",
        queued: "bg-blue-100 text-blue-700",
      };
      return map[status] || "bg-gray-100 text-gray-600";
    },

    isCancellable(f) {
      return f.job && CANCELLABLE_STATUSES.has(f.job.status) && !f.job.cancel_requested;
    },

    // Lop 0 point 1: warn when the selected provider/model is the one
    // directly responsible for the $6.50 incident (Architecture.md 6.11.2).
    isExpensiveModel(f) {
      if (f.provider !== "openai") return false;
      const model = this.providerSettings.openai?.model;
      return EXPENSIVE_OPENAI_MODELS.has(model);
    },

    async handleFiles(fileList) {
      this.uploadError = "";
      // Nhiem vu 6: dien san provider/output_mode theo lua chon lan truoc
      // (localStorage — don gian, khong can bang DB moi cho 1-user local app).
      const lastProvider = localStorage.getItem("bb_last_provider");
      const lastOutputMode = localStorage.getItem("bb_last_output_mode");
      for (const file of Array.from(fileList)) {
        const form = new FormData();
        form.append("file", file);
        try {
          const res = await fetch("/api/upload", { method: "POST", body: form });
          const body = await res.json();
          if (!res.ok) {
            this.uploadError = body.detail || "Upload that bai";
            continue;
          }
          const available = this.availableProviders(body.file_type);
          const provider = available.includes(lastProvider) ? lastProvider : available[0];
          this.files.push({
            ...body,
            job_type: "translate",
            provider,
            output_mode: lastOutputMode || "monolingual",
            costEstimate: null,
            job: null,
          });
        } catch (err) {
          this.uploadError = "Loi ket noi khi upload: " + err;
        }
      }
    },

    rememberChoice(f) {
      localStorage.setItem("bb_last_provider", f.provider);
      localStorage.setItem("bb_last_output_mode", f.output_mode);
    },

    async createJob(f, force = false, confirmCost = false) {
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_id: f.file_id,
          job_type: f.job_type,
          provider: f.job_type === "translate" ? f.provider : null,
          output_mode: f.output_mode,
          force,
          confirm_cost: confirmCost,
        }),
      });
      const body = await res.json();

      // Architecture.md 6.11.4 Lop 2: pre-flight cost gate — the server
      // refused to even create a Job. Offer the explicit, one-shot bypass
      // instead of just showing an error (confirm_cost is NEVER remembered
      // across jobs, per spec — this dialog is the only place it is set).
      if (res.status === 402) {
        const detail = body.detail || {};
        const wantsBypass = confirm(
          `Chi phi uoc tinh $${(detail.estimated_cost_usd || 0).toFixed(2)} vuot tran ` +
            `$${(detail.cap_usd || 0).toFixed(2)}.\n\n` +
            `Nhan OK de dich du sao (vuot tran lan nay), Cancel de huy.`
        );
        if (wantsBypass) {
          return this.createJob(f, force, true);
        }
        f.jobError = detail.detail || "Chi phi uoc tinh vuot tran, da huy.";
        return null;
      }

      if (!res.ok) {
        f.jobError = body.detail;
        return null;
      }

      // AC-12.2 (Bug #3 fix, QA Round 1): file_hash already translated to
      // completion before -> ask the user whether to reuse the old result or
      // translate again, instead of silently reusing or silently redoing.
      if (body.status === "duplicate_found" && body.duplicate_of) {
        const completedDate = new Date(body.duplicate_of.completed_at).toLocaleString();
        const wantsRetranslate = confirm(
          `File nay da duoc dich vao ${completedDate}. Nhan OK de dich lai, Cancel de dung ket qua cu.`
        );
        if (wantsRetranslate) {
          return this.createJob(f, true);
        }
        f.job = { id: body.duplicate_of.job_id, status: "completed", progress_percent: 100 };
        this.trackJob(f);
        return body.duplicate_of.job_id;
      }

      f.job = { id: body.job_id, status: body.status, progress_percent: 0 };
      this.trackJob(f);
      return body.job_id;
    },

    async estimateCost(f) {
      // Bug fix (Nhiem vu 1a): truoc day goi createJob() o day khi file chua
      // co job — VO TINH tao 1 Job that va trigger dich that ngay lap tuc
      // (POST /api/jobs luon `asyncio.create_task()` chay job trong
      // background). Gio goi thang POST /api/estimate — endpoint nay KHONG
      // tao Job/Batch row nao, chi tinh toan tu upload metadata da co san.
      const res = await fetch("/api/estimate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_id: f.file_id,
          provider: f.provider,
          output_mode: f.output_mode,
        }),
      });
      const body = await res.json();
      if (res.ok) {
        f.costEstimate = body;
      } else {
        f.jobError = body.detail;
      }
    },

    async translateAll(confirmCost = false) {
      const pending = this.files.filter((f) => !f.job);
      if (pending.length === 0) return;

      if (pending.length === 1) {
        await this.createJob(pending[0]);
        return;
      }

      const res = await fetch("/api/batches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_ids: pending.map((f) => f.file_id),
          job_type: pending[0].job_type,
          provider: pending[0].job_type === "translate" ? pending[0].provider : null,
          output_mode: pending[0].output_mode,
          confirm_cost: confirmCost,
        }),
      });
      const body = await res.json();

      // Architecture.md 6.11.4 Lop 2 — same batch-level gate as createJob().
      if (res.status === 402) {
        const detail = body.detail || {};
        const wantsBypass = confirm(
          `Tong chi phi uoc tinh ca batch $${(detail.estimated_cost_usd || 0).toFixed(2)} ` +
            `vuot tran $${(detail.cap_usd || 0).toFixed(2)}.\n\n` +
            `Nhan OK de dich du sao (vuot tran lan nay), Cancel de huy.`
        );
        if (wantsBypass) {
          await this.translateAll(true);
          return;
        }
        this.uploadError = detail.detail || "Chi phi uoc tinh ca batch vuot tran, da huy.";
        return;
      }

      if (!res.ok) {
        this.uploadError = body.detail || "Tao batch that bai";
        return;
      }
      pending.forEach((f, i) => {
        f.job = { id: body.job_ids[i], status: "queued", progress_percent: 0 };
        this.trackJob(f);
      });
    },

    // Architecture.md 6.11.4 Lop 0 point 4: kill switch — client-side loop
    // over every cancellable job, reusing the existing per-job graceful
    // cancel (no new backend endpoint needed).
    async stopAllJobs() {
      const cancellable = this.files.filter((f) => this.isCancellable(f));
      await Promise.all(cancellable.map((f) => this.cancelJob(f)));
    },

    async retryJob(f, confirmCost = false) {
      if (!f.job) return;
      const res = await fetch(`/api/jobs/${f.job.id}/retry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm_cost: confirmCost }),
      });
      const body = await res.json();

      // Architecture.md 6.11.4 Lop 2 (6.11.7 #2: "retry cung phai qua gate") —
      // same explicit bypass dialog as createJob()/translateAll().
      if (res.status === 402) {
        const detail = body.detail || {};
        const wantsBypass = confirm(
          `Chi phi uoc tinh $${(detail.estimated_cost_usd || 0).toFixed(2)} vuot tran ` +
            `$${(detail.cap_usd || 0).toFixed(2)}.\n\n` +
            `Nhan OK de tiep tuc dich du sao, Cancel de huy.`
        );
        if (wantsBypass) {
          return this.retryJob(f, true);
        }
        f.jobError = detail.detail || "Chi phi uoc tinh vuot tran, da huy retry.";
        return;
      }

      if (res.ok) {
        f.job.status = body.status;
        f.job.error_message = null;
        f.job.cancel_requested = false;
        this.trackJob(f);
      } else {
        f.jobError = body.detail;
      }
    },

    // Nhiem vu 3: graceful cancel — chi dat co, khong dung ngay lap tuc.
    // UI cap nhat lien tuc thanh "Dang dung..." (qua `cancel_requested`) cho
    // toi khi poll/WebSocket thay status thuc su doi thanh "cancelled".
    async cancelJob(f) {
      if (!f.job) return;
      const res = await fetch(`/api/jobs/${f.job.id}/cancel`, { method: "POST" });
      const body = await res.json();
      if (res.ok) {
        f.job.cancel_requested = true;
      } else {
        f.jobError = body.detail;
      }
    },

    trackJob(f) {
      const poll = async () => {
        if (!f.job) return;
        const res = await fetch(`/api/jobs/${f.job.id}`);
        if (res.ok) {
          f.job = await res.json();
        }
        if (f.job && !TERMINAL_STATUSES.has(f.job.status)) {
          setTimeout(poll, 3000);
        }
      };

      // Realtime updates via WebSocket (US-07); polling is the fallback if
      // the socket never connects or drops.
      try {
        const proto = location.protocol === "https:" ? "wss" : "ws";
        const ws = new WebSocket(`${proto}://${location.host}/ws/jobs/${f.job.id}`);
        ws.onmessage = (event) => {
          const data = JSON.parse(event.data);
          if (data.type === "progress") {
            f.job = {
              ...f.job,
              status: data.status,
              progress_percent: Math.round((data.progress || 0) * 100),
              current_chunk: data.chunk,
              total_chunks: data.total_chunks,
            };
          } else if (
            data.type === "job_completed" ||
            data.type === "job_failed" ||
            data.type === "job_cancelled"
          ) {
            poll();
          }
        };
        ws.onerror = () => poll();
      } catch (err) {
        poll();
      }
      poll();
    },
  };
}
