#!/usr/bin/env python3
"""
Network connectivity test script for containerized services
"""
import os
import sys
import time

import requests


def test_connection(service_name, url, max_retries=5, delay=2):
    """Test connection to a service with retries"""
    print(f"\n🔍 Testing connection to {service_name}: {url}")

    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=10)
            print(f"✅ {service_name}: HTTP {response.status_code}")
            if response.status_code == 200:
                return True
            else:
                print(f"   Response: {response.text[:200]}")
        except requests.exceptions.ConnectionError as e:
            print(f"❌ {service_name}: Connection failed - {str(e)}")
        except requests.exceptions.Timeout:
            print(f"⏰ {service_name}: Request timeout")
        except Exception as e:
            print(f"❌ {service_name}: Unexpected error - {str(e)}")

        if attempt < max_retries - 1:
            print(
                f"   Retrying in {delay} seconds... "
                f"({attempt + 1}/{max_retries})"
            )
            time.sleep(delay)

    return False


def main():
    print("🚀 Starting network connectivity tests...")

    # Environment variables
    weaviate_url = os.getenv("WEAVIATE_URL", "http://weaviate:8080")
    api_url = os.getenv("API_URL", "http://api:8000")

    print("Environment variables:")
    print(f"   WEAVIATE_URL: {weaviate_url}")
    print(f"   API_URL: {api_url}")

    # Test connections
    results = {}

    # Test Weaviate
    results["weaviate"] = test_connection(
        "Weaviate", f"{weaviate_url}/v1/.well-known/ready"
    )

    # Test API health endpoint
    results["api_health"] = test_connection("API Health", f"{api_url}/health")

    # Test API root endpoint
    results["api_root"] = test_connection("API Root", f"{api_url}/")

    # Test external connections (from container perspective)
    if "localhost" not in api_url and "localhost" not in weaviate_url:
        print("\n🌐 Testing external accessibility...")
        results["api_external"] = test_connection(
            "API External", "http://localhost:8000/"
        )
        results["streamlit_external"] = test_connection(
            "Streamlit External", "http://localhost:8501/"
        )

    # Summary
    print("\n📊 Summary:")
    for service, success in results.items():
        status = "✅ OK" if success else "❌ FAILED"
        print(f"   {service}: {status}")

    # Exit with appropriate code
    if all(results.values()):
        print("\n🎉 All connections successful!")
        sys.exit(0)
    else:
        print("\n⚠️  Some connections failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
