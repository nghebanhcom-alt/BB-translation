// Alpine.js app for web/glossary.html (US-03), calling the glossary API
// that already existed from Increment 2 (src/api/routes/glossary.py) — no
// backend changes needed here.

function glossaryApp() {
  return {
    entries: [],
    total: 0,
    scopeFilter: "",
    // US-18 (Architecture.md 6.16.2): search server-side, cong don voi
    // scopeFilter. searchDebounceTimer dung de debounce ~250ms (YA-2.3).
    searchQuery: "",
    searchDebounceTimer: null,
    // Nhiem vu 5: phan trang UI that (thay vi hardcode limit=200/offset=0),
    // theo dung pattern history.js da co (limit/offset + nut Truoc/Sau).
    limit: 25,
    offset: 0,
    importPreview: null,
    editingId: null,
    editDraft: { term_vi: "", notes: "" },
    // US-17 (Architecture.md 6.16.3): modal "Them tu moi" + xac nhan ghi de
    // (BR-GLOSS-07).
    showAddModal: false,
    addForm: { term_en: "", term_vi: "", notes: "" },
    addError: null,
    addConflict: null,
    addSubmitting: false,

    async load() {
      const params = new URLSearchParams({
        limit: String(this.limit),
        offset: String(this.offset),
      });
      if (this.scopeFilter) params.set("scope", this.scopeFilter);
      if (this.searchQuery.trim()) params.set("q", this.searchQuery.trim());
      const res = await fetch(`/api/glossary?${params}`);
      const body = await res.json();
      this.entries = body.entries;
      this.total = body.total;
    },

    onSearchInput() {
      // AC-18 dong 3 / YA-2.3: moi thay doi searchQuery phai reset offset=0
      // truoc khi load(), debounce ~250ms de khong goi API tren tung phim go.
      clearTimeout(this.searchDebounceTimer);
      this.searchDebounceTimer = setTimeout(() => {
        this.offset = 0;
        this.load();
      }, 250);
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

    openAddModal() {
      this.addForm = { term_en: "", term_vi: "", notes: "" };
      this.addError = null;
      this.addConflict = null;
      this.showAddModal = true;
    },

    closeAddModal() {
      this.showAddModal = false;
      this.addError = null;
      this.addConflict = null;
    },

    async submitAdd(force) {
      const termEn = this.addForm.term_en.trim();
      if (!termEn) {
        this.addError = "term_en không được để trống";
        return;
      }
      this.addSubmitting = true;
      this.addError = null;
      try {
        const res = await fetch("/api/glossary", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            term_en: termEn,
            term_vi: this.addForm.term_vi.trim() || null,
            notes: this.addForm.notes.trim() || null,
            force: !!force,
          }),
        });
        if (res.status === 201) {
          this.showAddModal = false;
          this.addConflict = null;
          await this.load();
          return;
        }
        if (res.status === 409) {
          // BR-GLOSS-07: server tra ve entry cu trong `detail.existing` de
          // hoi xac nhan ghi de (xem create_entry() trong glossary.py).
          const body = await res.json().catch(() => ({}));
          const detail = body.detail || {};
          this.addConflict = detail.existing || null;
          this.addError = detail.detail || "Từ này đã có trong glossary.";
          // Reviewer round 1 non-blocking (docs/review-report.md muc 7): neu
          // user chua tu go term_vi/notes, pre-fill tu entry cu de "Ghi de"
          // khong am tham xoa mat du lieu da curate (bulk_import() thay toan
          // bo field, khong patch tung field) — giu nguyen neu user da go.
          if (this.addConflict) {
            if (!this.addForm.term_vi.trim()) this.addForm.term_vi = this.addConflict.term_vi || "";
            if (!this.addForm.notes.trim()) this.addForm.notes = this.addConflict.notes || "";
          }
          return;
        }
        const body = await res.json().catch(() => ({}));
        this.addError = body.detail || "Không thêm được từ mới";
      } finally {
        this.addSubmitting = false;
      }
    },
  };
}
