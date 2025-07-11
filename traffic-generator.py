#!/usr/bin/env python3
"""
Traffic Generator with Periodic Errors
A demonstration app for the Observe MCP Server that generates continuous traffic
with periodic errors and stacktraces to showcase debugging and monitoring capabilities.

# pyright: reportMissingImports=false
"""

import time
import random
import logging
import json
import threading
import traceback
from datetime import datetime
from typing import Dict, List, Any, Optional
import sys
from contextlib import nullcontext
import os

# Optional OpenTelemetry instrumentation
try:
    from opentelemetry import trace, metrics  # type: ignore
    from opentelemetry.sdk.resources import Resource  # type: ignore
    from opentelemetry.sdk.trace import TracerProvider  # type: ignore
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter  # type: ignore
    from opentelemetry.sdk.metrics import MeterProvider  # type: ignore
    from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader  # type: ignore
    from opentelemetry.instrumentation.logging import LoggingInstrumentor  # type: ignore
    OTEL_AVAILABLE = True
except ImportError:
    # OpenTelemetry not installed; continue without instrumentation
    OTEL_AVAILABLE = False

# Optional OTLP exporters (HTTP/protobuf)
try:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # type: ignore
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter  # type: ignore
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter  # type: ignore
    OTLP_AVAILABLE = True
except ImportError:
    OTLP_AVAILABLE = False

# Optional OpenTelemetry logs SDK (still evolving)
try:
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler  # type: ignore
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor  # type: ignore
    OTLP_LOGS_SDK_AVAILABLE = True
except ImportError as e:
    OTLP_LOGS_SDK_AVAILABLE = False

# --------------------------------------------
# Debug helper to log OTLP HTTP requests
# --------------------------------------------
if OTLP_AVAILABLE:
    class DebugOTLPLogExporter(OTLPLogExporter):
        """Subclass that logs HTTP request details with masked headers when root logger is DEBUG."""

        def __init__(self, *args, **kwargs):  # type: ignore
            super().__init__(*args, **kwargs)

        def export(self, batch):  # type: ignore
            if logging.getLogger().level <= logging.DEBUG:
                # Mask authorization header if present
                masked_headers = {}
                for key, value in getattr(self, 'headers', {}).items():
                    if key.lower() == "authorization":
                        masked_headers[key] = value[:10] + "...<redacted>"
                    else:
                        masked_headers[key] = value

                endpoint = getattr(self, "_endpoint", getattr(self, "_url", "<unknown>"))
                logger.debug(
                    "OTLP Log Exporter: sending %s records to %s with headers=%s",
                    len(batch),
                    endpoint,
                    masked_headers,
                )

            return super().export(batch)

# ------------------
# Configure logging
# ------------------
LOG_LEVEL_ENV = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL_ENV, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)

# Emit debug logs from OpenTelemetry internals when root level is DEBUG
if logging.getLogger().level <= logging.DEBUG:
    logging.getLogger("opentelemetry").setLevel(logging.DEBUG)
    logging.getLogger("urllib3").setLevel(logging.DEBUG)

logger = logging.getLogger('TrafficGenerator')

# Debug: Show what's available
logger.debug(f"OTEL_AVAILABLE: {OTEL_AVAILABLE}")
logger.debug(f"OTLP_AVAILABLE: {OTLP_AVAILABLE}")
logger.debug(f"OTLP_LOGS_SDK_AVAILABLE: {OTLP_LOGS_SDK_AVAILABLE}")

# ------------------------------
# OpenTelemetry setup (optional)
# ------------------------------
if OTEL_AVAILABLE:
    resource = Resource(attributes={
        "service.name": "traffic-generator",
        "deployment.environment": "prod",
    })

    # Tracer provider & exporter
    tracer_provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(tracer_provider)
    tracer = trace.get_tracer(__name__)

    # Choose exporter based on availability
    span_exporter = OTLPSpanExporter() if OTLP_AVAILABLE else ConsoleSpanExporter()
    tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))

    # Metrics exporter / reader (default interval 5s)
    metric_exporter = OTLPMetricExporter() if OTLP_AVAILABLE else ConsoleMetricExporter()
    metric_reader = PeriodicExportingMetricReader(
        metric_exporter,
        export_interval_millis=5000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    meter = metrics.get_meter(__name__)

    # Metrics instruments
    request_counter = meter.create_counter(
        name="api_requests_total",
        description="Total number of API requests",
        unit="1",
    )
    error_counter = meter.create_counter(
        name="api_errors_total",
        description="Total number of API errors",
        unit="1",
    )
    db_query_hist = meter.create_histogram(
        name="db_query_execution_time_ms",
        description="Execution time of database queries",
        unit="ms",
    )

    # Logs exporter / provider
    logger.debug("Checking if logs exporter should be initialized...")
    if OTLP_AVAILABLE and OTLP_LOGS_SDK_AVAILABLE:
        logger.debug("Initializing OTLP logs exporter...")
        logger_provider = LoggerProvider(resource=resource)
        # Note: otel_logs.set_logger_provider not available in experimental API

        # Choose exporter class based on log level
        log_exporter_cls = DebugOTLPLogExporter if logging.getLogger().level <= logging.DEBUG else OTLPLogExporter
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter_cls()))

        # Attach OpenTelemetry logging handler to root so standard log records are exported.
        logging.getLogger().addHandler(LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider))
        logger.debug("OTLP logs exporter initialized successfully!")
    else:
        logger.debug("OTLP logs exporter NOT initialized - missing dependencies")

    # Enrich log records with OTEL context (trace/span IDs in log fmt)
    LoggingInstrumentor().instrument(set_logging_format=True)
else:
    tracer = None
    request_counter = None
    error_counter = None
    db_query_hist = None

class DatabaseSimulator:
    """Simulates database operations with occasional failures"""
    
    def __init__(self, failure_rate: float = 0.1):
        self.failure_rate = failure_rate
        self.connection_pool = []
        self.max_connections = 10
        
    def connect(self):
        if random.random() < self.failure_rate:
            raise ConnectionError("Failed to connect to database: Connection refused")
        
        if len(self.connection_pool) >= self.max_connections:
            raise RuntimeError(f"Connection pool exhausted: {len(self.connection_pool)}/{self.max_connections}")
        
        conn_id = f"conn_{len(self.connection_pool)}"
        self.connection_pool.append(conn_id)
        logger.debug(f"Database connection established: {conn_id}")
        return conn_id
    
    def query(self, conn_id: str, query: str):
        span_cm = tracer.start_as_current_span("db.query") if tracer else nullcontext()
        with span_cm:
            if conn_id not in self.connection_pool:
                raise ValueError(f"Invalid connection ID: {conn_id}")

            # Simulate slow queries
            if "complex_join" in query:
                time.sleep(random.uniform(2, 5))

            # Simulate query errors
            if random.random() < self.failure_rate / 2:
                if random.choice([True, False]):
                    raise TimeoutError(f"Query timeout after 30s: {query}")
                else:
                    raise SyntaxError(f"Invalid SQL syntax: {query}")

            exec_time = random.uniform(0.1, 2.0)

            # Record execution time metric
            if db_query_hist:
                db_query_hist.record(exec_time * 1000, {"query_type": "complex" if "complex_join" in query else "simple"})

            return {"rows": random.randint(0, 1000), "execution_time": exec_time}
    
    def disconnect(self, conn_id: str):
        if conn_id in self.connection_pool:
            self.connection_pool.remove(conn_id)
            logger.debug(f"Database connection closed: {conn_id}")

class APISimulator:
    """Simulates API endpoints with various response patterns"""
    
    def __init__(self):
        self.endpoints = {
            "/users": self.handle_users,
            "/orders": self.handle_orders,
            "/inventory": self.handle_inventory,
            "/analytics": self.handle_analytics
        }
        self.request_count = 0
        self.error_count = 0
        
    def handle_request(self, endpoint: str, method: str = "GET", data: Optional[Dict[str, Any]] = None):
        self.request_count += 1

        # OpenTelemetry metrics & tracing
        if request_counter:
            request_counter.add(1, {"endpoint": endpoint, "method": method})

        span_cm = tracer.start_as_current_span(f"{method} {endpoint}") if tracer else nullcontext()
        with span_cm:
            try:
                if endpoint not in self.endpoints:
                    raise ValueError(f"Unknown endpoint: {endpoint}")
                
                logger.info(f"API Request: {method} {endpoint}")
                
                # Simulate rate limiting
                if self.request_count % 50 == 0:
                    raise RuntimeError("Rate limit exceeded: 429 Too Many Requests")
                
                response = self.endpoints[endpoint](method, data)
                logger.info(f"API Response: {endpoint} - Status: {response['status']}")
                return response
                
            except Exception as e:
                self.error_count += 1
                if error_counter:
                    error_counter.add(1, {"endpoint": endpoint, "method": method})
                logger.error(f"API Error on {endpoint}: {str(e)}", exc_info=True)
                raise
    
    def handle_users(self, method: str, data: Optional[Dict[str, Any]] = None):
        if method == "POST" and random.random() < 0.15:
            # Simulate validation error
            raise ValueError("Invalid user data: missing required field 'email'")
        
        return {
            "status": 200,
            "data": {"user_id": random.randint(1000, 9999)},
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def handle_orders(self, method: str, data: Optional[Dict[str, Any]] = None):
        # Simulate intermittent service unavailability
        if random.random() < 0.05:
            raise ConnectionError("Order service temporarily unavailable")
        
        # Simulate data inconsistency
        if random.random() < 0.1:
            raise AssertionError("Data integrity check failed: order total mismatch")
        
        return {
            "status": 200,
            "data": {"order_id": f"ORD-{random.randint(100000, 999999)}"},
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def handle_inventory(self, method: str, data: Optional[Dict[str, Any]] = None):
        # Simulate memory issues with large responses
        if random.random() < 0.08:
            # This could cause memory errors in a real scenario
            large_data = [{"item_id": i, "data": "x" * 1000} for i in range(10000)]
            raise MemoryError("Insufficient memory to process inventory request")
        
        return {
            "status": 200,
            "data": {"items": random.randint(100, 1000)},
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def handle_analytics(self, method: str, data: Optional[Dict[str, Any]] = None):
        # Simulate complex calculation errors
        if random.random() < 0.12:
            # Division by zero
            result = 1 / 0
        
        # Simulate type errors
        if random.random() < 0.1:
            # Attempting to perform operations on incompatible types
            result = "string" + 123  # type: ignore[arg-type]
        
        return {
            "status": 200,
            "data": {"metric": random.uniform(0.5, 0.95)},
            "timestamp": datetime.utcnow().isoformat()
        }

class BackgroundTaskRunner:
    """Simulates background tasks with various failure modes"""
    
    def __init__(self):
        self.tasks = []
        self.running = True
        
    def add_task(self, name: str, func, interval: float):
        task = {
            "name": name,
            "func": func,
            "interval": interval,
            "last_run": 0,
            "run_count": 0,
            "error_count": 0
        }
        self.tasks.append(task)
        
    def run_tasks(self):
        while self.running:
            current_time = time.time()
            
            for task in self.tasks:
                if current_time - task["last_run"] >= task["interval"]:
                    try:
                        logger.info(f"Running background task: {task['name']}")
                        task["func"]()
                        task["run_count"] += 1
                        task["last_run"] = current_time
                        
                    except Exception as e:
                        task["error_count"] += 1
                        logger.error(
                            f"Background task failed: {task['name']} "
                            f"(run #{task['run_count']}, errors: {task['error_count']})",
                            exc_info=True
                        )
            
            time.sleep(1)
    
    def stop(self):
        self.running = False

# Background task functions
def cleanup_task():
    """Simulates a cleanup task that occasionally fails"""
    logger.info("Starting cleanup task")
    
    if random.random() < 0.2:
        raise IOError("Failed to access temporary directory")
    
    files_cleaned = random.randint(10, 100)
    logger.info(f"Cleanup completed: {files_cleaned} files removed")

def sync_task():
    """Simulates a data sync task with network issues"""
    logger.info("Starting data synchronization")
    
    if random.random() < 0.15:
        raise ConnectionError("Network timeout during sync")
    
    if random.random() < 0.1:
        raise json.JSONDecodeError("Invalid response from sync server", "", 0)
    
    records_synced = random.randint(100, 1000)
    logger.info(f"Sync completed: {records_synced} records synchronized")

def cache_refresh_task():
    """Simulates cache refresh with occasional corruption"""
    logger.info("Refreshing cache")
    
    if random.random() < 0.1:
        raise ValueError("Cache corruption detected: invalid checksum")
    
    if random.random() < 0.05:
        # Simulate a recursive error
        def recursive_error(depth=0):
            if depth > 10:
                raise RecursionError("Maximum recursion depth exceeded in cache rebuild")
            recursive_error(depth + 1)
        recursive_error()
    
    logger.info("Cache refresh completed successfully")

def monitoring_task():
    """Simulates a monitoring task that reports system metrics"""
    metrics = {
        "cpu_usage": random.uniform(20, 95),
        "memory_usage": random.uniform(40, 85),
        "disk_usage": random.uniform(30, 90),
        "active_connections": random.randint(10, 100)
    }
    
    # Simulate metric threshold alerts
    if metrics["cpu_usage"] > 80:
        logger.warning(f"High CPU usage detected: {metrics['cpu_usage']:.1f}%")
    
    if metrics["memory_usage"] > 75:
        logger.warning(f"High memory usage detected: {metrics['memory_usage']:.1f}%")
        if random.random() < 0.3:
            raise MemoryError("Out of memory: unable to allocate buffer")
    
    logger.info(f"System metrics: {json.dumps(metrics, indent=2)}")

def main():
    """Main application loop"""
    logger.info("=== Traffic Generator Started ===")
    logger.info("Generating continuous traffic with periodic errors...")
    logger.info("Press Ctrl+C to stop")
    
    # Initialize components
    db = DatabaseSimulator(failure_rate=0.15)
    api = APISimulator()
    task_runner = BackgroundTaskRunner()
    
    # Add background tasks
    task_runner.add_task("cleanup", cleanup_task, 10)
    task_runner.add_task("sync", sync_task, 15)
    task_runner.add_task("cache_refresh", cache_refresh_task, 20)
    task_runner.add_task("monitoring", monitoring_task, 5)
    
    # Start background tasks in a separate thread
    task_thread = threading.Thread(target=task_runner.run_tasks)
    task_thread.daemon = True
    task_thread.start()
    
    # Main traffic generation loop
    try:
        endpoints = ["/users", "/orders", "/inventory", "/analytics"]
        methods = ["GET", "POST", "PUT", "DELETE"]
        
        while True:
            try:
                # Simulate API traffic
                endpoint = random.choice(endpoints)
                method = random.choice(methods) if endpoint != "/analytics" else "GET"
                
                api.handle_request(endpoint, method, {"test": "data"})
                
                # Simulate database operations
                if random.random() < 0.7:  # 70% chance of DB operation
                    conn_id = None
                    try:
                        conn_id = db.connect()
                        
                        # Perform various queries
                        queries = [
                            "SELECT * FROM users WHERE active = true",
                            "INSERT INTO logs (message) VALUES ('test')",
                            "UPDATE inventory SET quantity = quantity - 1",
                            "SELECT * FROM orders complex_join products ON ...",
                            "DELETE FROM sessions WHERE expired = true"
                        ]
                        
                        query = random.choice(queries)
                        result = db.query(conn_id, query)
                        logger.info(f"Query executed: {query[:50]}... - {result['rows']} rows")
                        
                    finally:
                        if conn_id:
                            db.disconnect(conn_id)
                
                # Add some variety to the traffic pattern
                sleep_time = random.uniform(0.1, 2.0)
                time.sleep(sleep_time)
                
                # Periodically log statistics
                if api.request_count % 20 == 0:
                    error_rate = (api.error_count / api.request_count) * 100 if api.request_count > 0 else 0
                    logger.info(
                        f"Stats - Requests: {api.request_count}, "
                        f"Errors: {api.error_count}, "
                        f"Error Rate: {error_rate:.1f}%, "
                        f"DB Connections: {len(db.connection_pool)}"
                    )
                
            except Exception as e:
                # Log unexpected errors but continue running
                logger.error(f"Unexpected error in main loop: {str(e)}", exc_info=True)
                time.sleep(1)
                
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
        task_runner.stop()
        task_thread.join(timeout=5)
        logger.info("=== Traffic Generator Stopped ===")

if __name__ == "__main__":
    main()