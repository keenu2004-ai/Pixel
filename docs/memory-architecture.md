# PIXEL — Memory Architecture & Privacy Policy
**Status:** Approved Source of Truth  
**Version:** 1.0.0  

---

## 1. Memory Tiering Strategy

PIXEL enforces a 5-tier hierarchical memory model to prevent context bloat and guarantee data sovereignty:

```
+-------------------------------------------------------------------------+
| Tier 1: WORKING MEMORY (Active turn scratchpad, volatile, ephemeral)    |
+-------------------------------------------------------------------------+
                                    │ Summarize & Extract
                                    ▼
+-------------------------------------------------------------------------+
| Tier 2: EPISODIC MEMORY (Specific interactions, time-indexed events)     |
+-------------------------------------------------------------------------+
                                    │ Distill Facts & Preferences
                                    ▼
+-------------------------------------------------------------------------+
| Tier 3: SEMANTIC MEMORY (User profile, verified facts, preferences)     |
+-------------------------------------------------------------------------+
                                    │ Extract Workflows
                                    ▼
+-------------------------------------------------------------------------+
| Tier 4: PROCEDURAL MEMORY (Learned tool chains, custom routines)        |
+-------------------------------------------------------------------------+
                                    │ Sync Across Devices
                                    ▼
+-------------------------------------------------------------------------+
| Tier 5: DEVICE & TOPOLOGY MEMORY (Known nodes, OS capabilities, status) |
+-------------------------------------------------------------------------+
```

---

## 2. Tier Specifications & Storage Engine

| Tier | Storage Engine | Retention Policy | Indexing Strategy | Privacy Boundary |
| :--- | :--- | :--- | :--- | :--- |
| **Working** | In-memory / Redis | Current session lifespan ($< 1$ hour) | FIFO sliding window with token truncation | Raw conversation data; never persisted to disk unencrypted |
| **Episodic** | PostgreSQL (`pixel_episodes`) | 30 days default (user configurable) | Time-series + vector embeddings (`pgvector`) | Contains sanitized interaction summaries |
| **Semantic** | PostgreSQL (`pixel_facts`) | Permanent until deleted/updated | Categorized key-value + semantic similarity | User can inspect, edit, or delete any fact via UI |
| **Procedural** | PostgreSQL (`pixel_procedures`)| Versioned scripts/templates | Tag-based & intent triggers | Reusable automation blueprints |
| **Device** | PostgreSQL (`pixel_devices`) | Dynamic heartbeat lease | Device UUID + capability flags | Local network metadata only |

---

## 3. Privacy & Data Governance Rules

1. **Explicit Extraction Policy**: The LLM does not write raw conversation logs to semantic memory. The background `MemoryAgent` runs a sanitized extraction prompt that extracts only structured facts (e.g., `user.work_hours = "9am-6pm"`, `user.preferred_editor = "VS Code"`).
2. **Right to Forget**: Complete cryptographic deletion of facts and episodic memories by user command ("Pixel, forget what I said about project X").
3. **Sensitive Data Redaction**: Automatic Regex and NER filters scrub API keys, credit card numbers, passwords, and PII before memory persistence.
