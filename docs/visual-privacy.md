# Visual Privacy & Zero-Surveillance Architecture

## Zero-Surveillance Principles
PIXEL guarantees bounded, user-initiated, ephemeral visual perception. PIXEL will never run an unconstrained continuous background camera or screen surveillance loop.

## Lifecycle States & Data Retention

1. **Camera Permission Lifecycle**:
   - `UNAVAILABLE` → `PERMISSION_REQUIRED` → `IDLE` → `ACTIVE_STREAMING` → `FRAME_CAPTURED` → `RELEASED`.
   - Access is denied by default until explicitly granted by the user.
   - Captured frames default to `is_ephemeral=True`. Once processed by perceptual models, frame byte buffers are immediately released.

2. **Sensitive Screen Redaction**:
   - Automatic regex-based identification of:
     - API Keys & Secrets (`sk-*`, `ghp_*`, `AKIA*`, Bearer tokens)
     - Passwords & credential fields
     - One-Time Passwords (OTPs / PINs)
     - Credit Card numbers
   - When sensitive regions are detected:
     - The screen frame is marked with `has_sensitive_data=True`.
     - Remote model routing is blocked; execution is confined strictly to local on-device models.

3. **Visual Memory & Right-to-Forget**:
   - Only explicitly approved facts (`USER_APPROVED_MEMORY`, `DERIVED_FACT`) are retained in visual memory stores.
   - Ephemeral UI states and screen captures expire according to TTL rules.
   - Right-to-forget API (`DELETE /api/v1/multimodal/memory`) enables immediate purging of all stored visual knowledge.
