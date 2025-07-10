# Traffic Generator Demo App for Observe

A comprehensive Python application that generates continuous traffic with periodic errors and stacktraces. Ideal for demonstrating the Observe MCP Server's capabilities and exploring observability signals (logs, metrics, traces) with OpenTelemetry.

---

## Key Features

* **Multiple Error Types**  
  * Connection errors (database, API)  
  * Timeout errors  
  * Memory errors  
  * Data-validation errors  
  * Type errors & division-by-zero  
  * Recursion errors  
  * Rate-limiting errors

* **Realistic Components**  
  * **Database Simulator** – connection pooling, query delays, syntax/timeout errors  
  * **API Simulator** – multiple endpoints, each with unique failure patterns  
  * **Background Tasks** – cleanup, sync, cache-refresh, and monitoring jobs  
  * **Comprehensive Logging** – structured logs at varying severity levels

* **Traffic Patterns**  
  * Continuous API requests across random endpoints  
  * Database operations with connection management  
  * Concurrent background tasks on separate cadences  
  * Periodic statistics reporting

* **OpenTelemetry Instrumentation**  
  * Traces, metrics, and logs exported via OTLP/HTTP  
  * Console fallback when OTEL exporters are not installed  
  * Metrics: `api_requests_total`, `api_errors_total`, `db_query_execution_time_ms`

---

## Why This Is Useful for the Observe MCP Server

1. **Feedback Loop** – After the application (or an AI agent) applies a fix, Observe immediately shows the impact in error rates and patterns.
2. **Pattern Recognition** – Rich logs expose trends such as:
   * Rising error rates before failures
   * Resource-exhaustion warnings preceding crashes
   * Correlations among different error classes
3. **Iterative Debugging** – Agents (human or AI) can:
   * Detect error patterns in telemetry  
   * Propose fixes (increase connection pool, add retries, etc.)  
   * Observe reduced error rates post-change  
   * Iterate on new insights

---

## Prerequisites

* Python 3.8+
* Recommended: virtual environment (`venv`, `virtualenv`, `conda`, etc.)

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Optional: Export to Observe via OTEL

1. Use **Add Data → Linux** in Observe to generate an ingest token.

```bash
# Traces
export OTEL_TRACES_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_TRACES_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="<YOUR_OBSERVE_COLLECTION_ENDPOINT>/v2/otel/v1/traces"
export OTEL_EXPORTER_OTLP_TRACES_HEADERS="authorization=Bearer <token>,x-observe-target-package=Tracing"

# For metrics
export OTEL_METRICS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_METRICS_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_METRICS_ENDPOINT="<YOUR_OBSERVE_COLLECTION_ENDPOINT>/v2/otel/v1/metrics"
export OTEL_EXPORTER_OTLP_METRICS_HEADERS="authorization=Bearer <token>,x-observe-target-package=Metrics"

# Logs
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_LOGS_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_LOGS_ENDPOINT="<YOUR_OBSERVE_COLLECTION_ENDPOINT>/v2/otel/v1/logs"
export OTEL_EXPORTER_OTLP_LOGS_HEADERS="authorization=Bearer <token>,x-observe-target-package=Host Explorer"
```

> Replace `<token>` with your Observe ingest token.

Example endpoint (Observe Cloud): `https://123456789012.collect.observeinc.com`

---

## Usage

Run the traffic generator:

```bash
python traffic_generator.py
```

The app will:

* Log to **console** and **app.log** file
* Generate **continuous traffic**
* Inject **periodic errors** with full stacktraces
* Continue until you press **Ctrl+C**

---

## Example Demo Scenarios

| Scenario | What to Watch | Possible Fix |
| --- | --- | --- |
| **Connection-pool exhaustion** | DB connection errors increase | Increase `max_connections`, implement retries |
| **Memory leaks** | Rising memory metrics, OOM errors | Optimize payload sizes, fix leaks |
| **API rate limiting** | 429 errors in logs | Add exponential backoff |
| **Background task failures** | Recurring task-specific errors | Add error handling, adjust intervals |

These scenarios showcase how Observe (and AI agents) enable a real-time feedback loop to validate fixes.

---

## License

MIT © 2024 