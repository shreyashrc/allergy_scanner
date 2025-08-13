"""
Test script for the FastAPI Allergy Scanner API.

Run:
  python test_api.py --base-url http://127.0.0.1:8000

This script will:
1) Register a new user with an allergen profile
2) Login to obtain a JWT token
3) Scan several real Open Food Facts barcodes
4) Fetch scan history
5) Fetch product info

Uses httpx sync client. Prints colored PASS/FAIL with details.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any, Dict, Optional, Tuple

import httpx


# ANSI colors (avoid external dependencies)
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"


def color(text: str, c: str) -> str:
    return f"{c}{text}{RESET}"


def print_header(title: str) -> None:
    print("\n" + color(f"=== {title} ===", CYAN))


def print_result(name: str, ok: bool, details: str = "") -> None:
    status = color("PASS", GREEN) if ok else color("FAIL", RED)
    print(f"[{status}] {name}")
    if details:
        print(details)


def safe_json(response: httpx.Response) -> Tuple[bool, Any]:
    try:
        return True, response.json()
    except Exception:
        return False, response.text


def request_with_logging(client: httpx.Client, method: str, url: str, *, headers: Optional[Dict[str, str]] = None, json: Optional[Dict[str, Any]] = None) -> httpx.Response:
    try:
        resp = client.request(method, url, headers=headers, json=json)
        return resp
    except httpx.RequestError as e:
        print_result(f"HTTP {method} {url}", False, details=color(str(e), YELLOW))
        raise


def run_register(client: httpx.Client, base_url: str) -> Tuple[bool, Optional[str], str, str]:
    """Register a new user with random email; return (ok, token, email, password)."""
    print_header("Register User")
    timestamp = int(time.time())
    email = f"test_{timestamp}@example.com"
    password = "test123"
    payload = {"email": email, "password": password, "allergens": ["nuts", "dairy"]}
    url = f"{base_url}/register"
    resp = request_with_logging(client, "POST", url, json=payload)
    ok_json, data = safe_json(resp)
    ok = resp.status_code == 200 and ok_json and isinstance(data, dict) and "access_token" in data
    details = f"Status: {resp.status_code}\nResponse: {data}"
    print_result("POST /register", ok, details)
    token = data.get("access_token") if ok else None  # type: ignore[attr-defined]
    return ok, token, email, password


def run_login(client: httpx.Client, base_url: str, email: str, password: str) -> Tuple[bool, Optional[str]]:
    print_header("Login")
    url = f"{base_url}/login"
    payload = {"email": email, "password": password}
    resp = request_with_logging(client, "POST", url, json=payload)
    ok_json, data = safe_json(resp)
    ok = resp.status_code == 200 and ok_json and isinstance(data, dict) and "access_token" in data
    details = f"Status: {resp.status_code}\nResponse: {data}"
    print_result("POST /login", ok, details)
    token = data.get("access_token") if ok else None  # type: ignore[attr-defined]
    return ok, token


def run_scan(client: httpx.Client, base_url: str, token: str, barcode: str, label: str) -> bool:
    print_header(f"Scan product: {label} ({barcode})")
    url = f"{base_url}/scan"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"barcode": barcode}
    resp = request_with_logging(client, "POST", url, headers=headers, json=payload)
    ok_json, data = safe_json(resp)
    ok_structure = ok_json and isinstance(data, dict) and all(k in data for k in ["risk_level", "user_allergens"])
    ok = resp.status_code == 200 and ok_structure
    details = f"Status: {resp.status_code}\nResponse: {data}"
    print_result("POST /scan", ok, details)
    return ok


def run_scan_history(client: httpx.Client, base_url: str, token: str) -> bool:
    print_header("Scan History")
    url = f"{base_url}/scan-history"
    headers = {"Authorization": f"Bearer {token}"}
    resp = request_with_logging(client, "GET", url, headers=headers)
    ok_json, data = safe_json(resp)
    ok_list = ok_json and isinstance(data, list)
    ok = resp.status_code == 200 and ok_list
    details = f"Status: {resp.status_code}\nCount: {len(data) if isinstance(data, list) else 'n/a'}\nResponse: {data}"
    print_result("GET /scan-history", ok, details)
    return ok


def run_product(client: httpx.Client, base_url: str, barcode: str, label: str) -> bool:
    print_header(f"Product info: {label} ({barcode})")
    url = f"{base_url}/product/{barcode}"
    resp = request_with_logging(client, "GET", url)
    ok_json, data = safe_json(resp)
    ok_structure = ok_json and isinstance(data, dict) and all(k in data for k in ["name", "brand", "ingredients", "allergens_found"])
    ok = resp.status_code == 200 and ok_structure
    details = f"Status: {resp.status_code}\nResponse: {data}"
    print_result("GET /product/{barcode}", ok, details)
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Test the Allergy Scanner API")
    parser.add_argument("--base-url", default=os.environ.get("ALLERGEN_API_BASE_URL", "http://127.0.0.1:8000"))
    args = parser.parse_args()
    base_url: str = args.base_url.rstrip("/")

    # Known barcodes from Open Food Facts (examples)
    test_barcodes = [
        ("3017620422003", "Nutella"),
        ("5449000214799", "Coca-Cola"),
        ("8076809513388", "Barilla pasta"),
        ("3017620425035", "Ferrero Rocher"),
    ]

    timeout = httpx.Timeout(20.0, connect=10.0)
    with httpx.Client(base_url=base_url, timeout=timeout) as client:
        try:
            resp = request_with_logging(client, "GET", f"{base_url}/health")
            ok_json, data = safe_json(resp)
            ok = resp.status_code == 200 and ok_json and isinstance(data, dict) and data.get("status") == "healthy"
            print_result("GET /health", ok, f"Status: {resp.status_code}\nResponse: {data}")
        except Exception:
            print(color("Health check failed; continuing tests...", YELLOW))

        reg_ok, reg_token, email, password = run_register(client, base_url)
        token: Optional[str] = reg_token

        # If registration failed due to email reuse, still attempt login using generated credentials
        login_ok = False
        if not reg_ok:
            login_ok, token = run_login(client, base_url, email, password)
        else:
            # Validate token works by fetching profile
            prof_url = f"{base_url}/profile"
            resp = request_with_logging(client, "GET", prof_url, headers={"Authorization": f"Bearer {token}"})
            ok_json, data = safe_json(resp)
            ok = resp.status_code == 200 and ok_json and isinstance(data, dict) and data.get("email") == email
            print_result("GET /profile", ok, f"Status: {resp.status_code}\nResponse: {data}")
            login_ok = True

        # If still no token, attempt login explicitly
        if not token:
            login_ok, token = run_login(client, base_url, email, password)

        if not login_ok or not token:
            print(color("Cannot continue tests without a valid token.", RED))
            return 2

        # Scan products
        for code, label in test_barcodes:
            try:
                run_scan(client, base_url, token, code, label)
            except Exception as e:
                print_result(f"Scan {label}", False, details=color(str(e), YELLOW))

        # History
        try:
            run_scan_history(client, base_url, token)
        except Exception as e:
            print_result("Scan history", False, details=color(str(e), YELLOW))

        # Product info
        for code, label in test_barcodes:
            try:
                run_product(client, base_url, code, label)
            except Exception as e:
                print_result(f"Product {label}", False, details=color(str(e), YELLOW))

    return 0


if __name__ == "__main__":
    sys.exit(main())

