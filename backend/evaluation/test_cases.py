EVAL_MODE = True
TEST_CASES = [
    {
        "id": "tc_001",
        "name": "Database connection pool exhaustion",
        "log_content": """
2024-01-15 03:12:01 INFO  payment-service Starting request processing
2024-01-15 03:13:12 WARN  payment-service Database connection pool at 95% (95/100)
2024-01-15 03:14:19 ERROR payment-service Connection pool exhausted (100/100)
2024-01-15 03:14:22 ERROR payment-service SQLException: Connection timeout after 30000ms
2024-01-15 03:14:23 ERROR payment-service HTTP 500 /api/payments/process
2024-01-15 03:14:41 ERROR payment-service Circuit breaker OPEN
        """.strip(),
        "expected": {
            "severity": "high",
            "affected_service": "payment-service",
            "probable_cause_keywords": [
                "connection pool", "exhausted", "timeout"
            ],
            "required_evidence_keywords": [
                "connection pool", "SQLException", "circuit breaker"
            ],
            "expected_actions_keywords": [
                "pool size", "connection", "restart"
            ]
        }
    },
    {
        "id": "tc_002",
        "name": "Out of memory error",
        "log_content": """
2024-01-16 09:00:01 INFO  order-service Processing orders
2024-01-16 09:15:22 WARN  order-service Memory usage at 85%
2024-01-16 09:22:45 WARN  order-service Memory usage at 95%
2024-01-16 09:23:11 ERROR order-service java.lang.OutOfMemoryError: Java heap space
2024-01-16 09:23:12 ERROR order-service Application crash imminent
2024-01-16 09:23:13 FATAL order-service Service terminated unexpectedly
        """.strip(),
        "expected": {
            "severity": "critical",
            "affected_service": "order-service",
            "probable_cause_keywords": [
                "memory", "heap", "OutOfMemoryError"
            ],
            "required_evidence_keywords": [
                "OutOfMemoryError", "heap", "memory"
            ],
            "expected_actions_keywords": [
                "memory", "heap", "restart", "JVM"
            ]
        }
    },
    {
        "id": "tc_003",
        "name": "Authentication service timeout",
        "log_content": """
2024-01-17 14:00:00 INFO  auth-service Handling login requests
2024-01-17 14:02:33 WARN  auth-service Response time degrading: 2300ms
2024-01-17 14:03:45 ERROR auth-service Request timeout after 5000ms
2024-01-17 14:03:46 ERROR auth-service HTTP 503 Service Unavailable
2024-01-17 14:04:00 ERROR auth-service Downstream dependency unreachable
        """.strip(),
        "expected": {
            "severity": "high",
            "affected_service": "auth-service",
            "probable_cause_keywords": [
                "timeout", "dependency", "unavailable"
            ],
            "required_evidence_keywords": [
                "timeout", "503", "unreachable"
            ],
            "expected_actions_keywords": [
                "timeout", "dependency", "retry"
            ]
        }
    }
]