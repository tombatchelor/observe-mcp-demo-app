#!/usr/bin/env python3
"""
Traffic Generator with Periodic Errors
A demonstration app for the Observe MCP Server that generates continuous traffic
with periodic errors and stacktraces to showcase debugging and monitoring capabilities.
"""

import time
import random
import logging
import json
import threading
import traceback
from datetime import datetime
from typing import Dict, List, Any
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')
    ]
)

logger = logging.getLogger('TrafficGenerator')

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
        
        return {"rows": random.randint(0, 1000), "execution_time": random.uniform(0.1, 2.0)}
    
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
        
    def handle_request(self, endpoint: str, method: str = "GET", data: Dict = None):
        self.request_count += 1
        
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
            logger.error(f"API Error on {endpoint}: {str(e)}", exc_info=True)
            raise
    
    def handle_users(self, method: str, data: Dict = None):
        if method == "POST" and random.random() < 0.15:
            # Simulate validation error
            raise ValueError("Invalid user data: missing required field 'email'")
        
        return {
            "status": 200,
            "data": {"user_id": random.randint(1000, 9999)},
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def handle_orders(self, method: str, data: Dict = None):
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
    
    def handle_inventory(self, method: str, data: Dict = None):
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
    
    def handle_analytics(self, method: str, data: Dict = None):
        # Simulate complex calculation errors
        if random.random() < 0.12:
            # Division by zero
            result = 1 / 0
        
        # Simulate type errors
        if random.random() < 0.1:
            # Attempting to perform operations on incompatible types
            result = "string" + 123
        
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