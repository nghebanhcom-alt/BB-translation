// Alpine.js app for web/glossary.html (US-03), calling the glossary API
// that already existed from Increment 2 (src/api/routes/glossary.py) — no
// backend changes needed here.

function glossaryApp() {
  return {
    entries: [],
    total: 0,
    scopeFilter: "",
    // Nhiem vu 5: phan trang UI that (thay vi hardcode limit=200/offset=0),
    // theo dung pattern history.js da co (limit/offset + nut Truoc/Sau).
    limit: 25,
    offset: 0,
    importPreview: null,
    editingId: null,
    editDraft: { term_vi: "", notes: "" },

    async load() {
      const params = new URLSearchParams({
        limit: String(this.limit),
        offset: String(this.offset),
      });
      if (this.scopeFilter) params.set("scope", this.scopeFilter);
      const res = await fetch(`/api/glossary?${params}`);
      const body = await res.json();
      this.entries = body.entries;
      this.total = body.total;
    },

    changePageSize(newLimit) {
      this.limit = Number(newLimit);
      this.offset = 0;
      this.load();
    },

    prevPage() {
      this.offset = Math.max(0, this.offset - this.limit);
      this.load();
    },

    nextPage() {
      this.offset += this.limit;
      this.load();
    },

    async previewImport(file) {
      if (!file) return;
      const form = new FormData();
      form.append("file", file);
      const res = await fetch("/api/glossary/import", { method: "POST", body: form });
      const body = await res.json();
      if (res.ok) {
        this.importPreview = body;
      } else {
        alert(body.detail || "Import that bai");
      }
    },

    async confirmImport() {
      if (!this.importPreview) return;
      const res = await fetch("/api/glossary/import/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entries: this.importPreview.entries, scope: "global" }),
      });
      if (res.ok) {
        this.importPreview = null;
        await this.load();
      }
    },

    startEdit(entry) {
      this.editingId = entry.id;
      this.editDraft = { term_vi: entry.term_vi || "", notes: entry.notes || "" };
    },

    async saveEdit(entry) {
      const res = await fetch(`/api/glossary/${entry.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(this.editDraft),
      });
      if (res.ok) {
        const updated = await res.json();
        Object.assign(entry, updated);
      }
      this.editingId = null;
    },

    async deleteEntry(entry) {
      if (!confirm(`Xóa entry "${entry.term_en}"?`)) return;
      const res = await fetch(`/api/glossary/${entry.id}`, { method: "DELETE" });
      if (res.ok) {
        await this.load();
      }
    },
  };
}
