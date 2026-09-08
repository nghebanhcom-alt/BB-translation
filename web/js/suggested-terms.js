// US-20 "Cac tu moi" — khu vuc "Cho duyet" trong tab Glossary
// (Architecture.md 6.18.4). Alpine component rieng voi glossaryApp() (khac
// data source: /api/glossary/suggested, khong phai /api/glossary).

function suggestedTermsApp() {
  return {
    entries: [],
    total: 0,
    noiseHiddenCount: 0,
    limit: 50,
    offset: 0,
    sort: "rank",
    minNgram: 1,
    includeNoise: false,
    collapsed: false,
    selectedIds: [],
    draftVi: {},
    suggestingTranslation: false,
    lastSuggestCost: null,

    async load() {
      const params = new URLSearchParams({
        status: "pending",
        limit: String(this.limit),
        offset: String(this.offset),
        sort: this.sort,
        min_ngram: String(this.minNgram),
        include_noise: String(this.includeNoise),
      });
      const res = await fetch(`/api/glossary/suggested?${params}`);
      if (!res.ok) return;
      const body = await res.json();
      this.entries = body.entries;
      this.total = body.total;
      this.noiseHiddenCount = body.noise_hidden_count;
      // Giu lai draft VI da go cho cac term van con hien; xoa draft cua
      // term khong con trong trang hien tai (da duoc thu vao/bo qua). Voi
      // term vua duoc "Goi y ban dich" tra ve tu server (suggested_term_vi)
      // ma user chua tu go gi, dung ban goi y do lam draft mac dinh.
      const stillVisible = new Set(this.entries.map((e) => e.id));
      for (const id of Object.keys(this.draftVi)) {
        if (!stillVisible.has(id)) delete this.draftVi[id];
      }
      for (const entry of this.entries) {
        if (!(entry.id in this.draftVi) && entry.suggested_term_vi) {
          this.draftVi[entry.id] = entry.suggested_term_vi;
        }
      }
      this.selectedIds = this.selectedIds.filter((id) => stillVisible.has(id));
    },

    prevPage() {
      this.offset = Math.max(0, this.offset - this.limit);
      this.load();
    },

    nextPage() {
      this.offset += this.limit;
      this.load();
    },

    async promote(term) {
      const termVi = (this.draftVi[term.id] || "").trim() || null;
      const res = await fetch(`/api/glossary/suggested/${term.id}/promote`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ term_vi: termVi }),
      });
      if (res.ok) {
        await this.load();
        // glossaryApp() (bang chinh o duoi trang) khong tu biet entry moi
        // vua duoc them qua duong US-20 — bao cho no load lai.
        window.dispatchEvent(new CustomEvent("glossary-entries-changed"));
      } else {
        const body = await res.json().catch(() => ({}));
        alert(body.detail || "Khong the them vao glossary");
      }
    },

    async dismiss(term) {
      const res = await fetch(`/api/glossary/suggested/${term.id}/dismiss`, { method: "POST" });
      if (res.ok) {
        await this.load();
      }
    },

    async suggestTranslation() {
      if (this.selectedIds.length === 0) return;
      if (
        !confirm(
          `Gợi ý bản dịch cho ${this.selectedIds.length} từ — hành động này gọi LLM và phát sinh chi phí. Tiếp tục?`
        )
      ) {
        return;
      }
      this.suggestingTranslation = true;
      try {
        const res = await fetch("/api/glossary/suggested/suggest-translation", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids: this.selectedIds }),
        });
        if (res.ok) {
          const body = await res.json();
          this.lastSuggestCost = body.total_cost_usd;
          await this.load();
        } else {
          const body = await res.json().catch(() => ({}));
          alert(body.detail || "Goi y ban dich that bai");
        }
      } finally {
        this.suggestingTranslation = false;
      }
    },
  };
}
