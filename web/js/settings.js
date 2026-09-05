// Alpine.js app for web/settings.html (Increment 6, Nhiem vu 2).
//
// GET/PUT /api/settings already existed (Increment 5) for API keys +
// default_provider; this page is the first UI on top of it, plus the new
// `provider_models` field (src/api/routes/settings.py).

// Vai lua chon model pho bien moi provider — nguoi dung van co the go tay
// (dropdown + input tu do) vi model that dang dung co the khac tuy version
// API key/account cua ho.
const MODEL_OPTIONS = {
  claude: [
    "claude-sonnet-5",
    "claude-opus-5",
    "claude-haiku-4-5-20251001",
    "claude-fable-5-1",
    "claude-sonnet-4-5-20250514",
  ],
  openai: ["gpt-4o-mini", "gpt-4o"],
  deepseek: ["deepseek-v4-flash", "deepseek-v4-pro"],
  gemini: ["gemini-2.5-pro", "gemini-2.5-flash"],
};

const PROVIDER_LABELS = {
  claude: "Claude (Anthropic)",
  openai: "OpenAI",
  deepseek: "DeepSeek",
  gemini: "Gemini (Google)",
  deepl: "DeepL",
  ollama: "Ollama (local)",
};

function settingsApp() {
  return {
    defaultProvider: "",
    maxConcurrentFiles: 3,
    // Architecture.md 6.11.4 Lop 2 — user-tunable pre-flight/running cost gate.
    maxCostPerJobUsd: 2.0,
    maxCostPerBatchUsd: 5.0,
    costCapEnabled: true,
    // Architecture.md 6.12.6 — Ollama co dinh thread, khong AIMD; gia tri
    // dung phu thuoc VRAM/so core cua may user, app khong tu suy ra duoc.
    ollamaThread: 2,
    providers: {},
    apiKeyDrafts: {}, // provider -> chuoi key moi go (rong = khong doi)
    modelDrafts: {}, // provider -> model da chon
    saveMessage: "",
    saveError: "",

    modelOptions(providerName) {
      return MODEL_OPTIONS[providerName] || [];
    },

    providerLabel(providerName) {
      return PROVIDER_LABELS[providerName] || providerName;
    },

    hasModel(providerName) {
      return providerName in MODEL_OPTIONS || providerName === "ollama";
    },

    async load() {
      const res = await fetch("/api/settings");
      if (!res.ok) return;
      const body = await res.json();
      this.defaultProvider = body.default_provider;
      this.maxConcurrentFiles = body.max_concurrent_files;
      this.maxCostPerJobUsd = body.max_cost_per_job_usd;
      this.maxCostPerBatchUsd = body.max_cost_per_batch_usd;
      this.costCapEnabled = body.cost_cap_enabled;
      this.ollamaThread = body.ollama_thread;
      this.providers = body.providers;
      this.apiKeyDrafts = {};
      this.modelDrafts = {};
      for (const [name, status] of Object.entries(body.providers)) {
        // API key: KHONG BAO GIO hien lai gia tri that (chi has_key) —
        // dung dung thiet ke da co san tu Increment 5.
        this.apiKeyDrafts[name] = "";
        this.modelDrafts[name] = status.model || "";
      }
    },

    async save() {
      this.saveMessage = "";
      this.saveError = "";

      const provider_api_keys = {};
      for (const [name, value] of Object.entries(this.apiKeyDrafts)) {
        if (value.trim() !== "") provider_api_keys[name] = value.trim();
      }

      const provider_models = {};
      for (const [name, value] of Object.entries(this.modelDrafts)) {
        if (value.trim() !== "" && this.hasModel(name)) provider_models[name] = value.trim();
      }

      const res = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          default_provider: this.defaultProvider,
          max_concurrent_files: Number(this.maxConcurrentFiles),
          max_cost_per_job_usd: Number(this.maxCostPerJobUsd),
          max_cost_per_batch_usd: Number(this.maxCostPerBatchUsd),
          cost_cap_enabled: this.costCapEnabled,
          ollama_thread: Number(this.ollamaThread),
          provider_api_keys,
          provider_models,
        }),
      });
      const body = await res.json();
      if (res.ok) {
        this.saveMessage = "Đã lưu cài đặt.";
        this.defaultProvider = body.default_provider;
        this.maxConcurrentFiles = body.max_concurrent_files;
        this.maxCostPerJobUsd = body.max_cost_per_job_usd;
        this.maxCostPerBatchUsd = body.max_cost_per_batch_usd;
        this.costCapEnabled = body.cost_cap_enabled;
        this.ollamaThread = body.ollama_thread;
        this.providers = body.providers;
        for (const name of Object.keys(this.apiKeyDrafts)) this.apiKeyDrafts[name] = "";
        for (const [name, status] of Object.entries(body.providers)) {
          this.modelDrafts[name] = status.model || "";
        }
      } else {
        this.saveError = body.detail || "Lưu cài đặt thất bại";
      }
    },
  };
}
