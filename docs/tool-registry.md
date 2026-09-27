# PIXEL — Tool Registry & Capability Contract Specification
**Status:** Approved Source of Truth  
**Version:** 1.0.0  

---

## 1. Tool Governance & Risk Classification Matrix

Every capability in PIXEL must be declared as a typed tool with strict JSON schema definitions, a defined timeout, retry policy, and an explicit risk class.

| Risk Class | Description | Approval Policy | Example Tools |
| :--- | :--- | :--- | :--- |
| `READ` | Pure read-only inspection with zero side effects. | Auto-executed | `system_info`, `search_files`, `read_calendar`, `get_weather`, `semantic_search` |
| `REVERSIBLE_WRITE` | Local, low-impact state modifications that can be easily undone. | Auto-executed with notification toast | `create_alarm`, `set_timer`, `create_reminder_draft`, `write_clipboard`, `play_media` |
| `EXTERNAL_COMMUNICATION` | Actions that communicate with external parties or public endpoints. | Requires interactive confirmation unless explicit white-list configured | `send_sms`, `make_call`, `send_email`, `post_webhook`, `publish_pr` |
| `HIGH_IMPACT` | Destructive operations, permanent file deletion, financial actions, or credential changes. | Mandatory interactive biometric / PIN / confirmation modal | `delete_file`, `git_push_force`, `execute_arbitrary_shell`, `modify_credentials` |

---

## 2. Core Tool Definitions (Sample Schemas)

### 2.1 `create_alarm`
- **Purpose**: Schedules an alarm on the target device clock.
- **Risk Class**: `REVERSIBLE_WRITE`
- **Timeout**: `3000ms`
- **Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "target_time": { "type": "string", "format": "time", "description": "ISO 8601 time e.g. 07:00:00" },
    "date": { "type": "string", "format": "date", "description": "Target date YYYY-MM-DD" },
    "label": { "type": "string", "description": "Alarm label description" },
    "recurring_days": { "type": "array", "items": { "type": "string" } }
  },
  "required": ["target_time", "date"]
}
```
- **Output Schema**:
```json
{
  "type": "object",
  "properties": {
    "success": { "type": "boolean" },
    "alarm_id": { "type": "string" },
    "normalized_time": { "type": "string" },
    "message": { "type": "string" }
  },
  "required": ["success", "alarm_id", "normalized_time"]
}
```

### 2.2 `semantic_code_search` (Serena Bridge)
- **Purpose**: Retrieves code symbols, function signatures, and AST relationships.
- **Risk Class**: `READ`
- **Timeout**: `8000ms`
- **Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "query": { "type": "string", "description": "Natural language or symbol name to look up" },
    "repository_path": { "type": "string" },
    "symbol_kind": { "type": "string", "enum": ["function", "class", "variable", "all"] }
  },
  "required": ["query", "repository_path"]
}
```

### 2.3 `execute_sandbox_command`
- **Purpose**: Runs a strictly allowlisted command inside the project sandbox.
- **Risk Class**: `HIGH_IMPACT` (if unconstrained) / `REVERSIBLE_WRITE` (if allowlisted test runner)
- **Timeout**: `30000ms`
- **Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "command": { "type": "string", "description": "The command line string" },
    "cwd": { "type": "string", "description": "Target working directory" },
    "env_vars": { "type": "object", "additionalProperties": { "type": "string" } }
  },
  "required": ["command", "cwd"]
}
```
