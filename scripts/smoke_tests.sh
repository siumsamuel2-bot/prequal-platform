#!/bin/bash
# Smoke Test Suite - Prequal Platform
# Usage: ./smoke_tests.sh <base_url> [auth_token]

set -e

BASE_URL="${1:-https://localhost:3000}"
AUTH_TOKEN="${2:-}"
FAILED=0
PASSED=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASSED++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAILED++))
}

log_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

test_endpoint() {
    local method=$1
    local path=$2
    local expected_status=$3
    local description=$4
    local data=$5

    local url="${BASE_URL}${path}"
    local http_code

    log_info "Testing: $method $path - $description"

    if [ "$method" = "GET" ]; then
        if [ -n "$AUTH_TOKEN" ]; then
            http_code=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $AUTH_TOKEN" "$url")
        else
            http_code=$(curl -s -o /dev/null -w "%{http_code}" "$url")
        fi
    elif [ "$method" = "POST" ]; then
        if [ -n "$AUTH_TOKEN" ]; then
            http_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "Authorization: Bearer $AUTH_TOKEN" -H "Content-Type: application/json" -d "$data" "$url")
        else
            http_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST -H "Content-Type: application/json" -d "$data" "$url")
        fi
    fi

    if [ "$http_code" = "$expected_status" ]; then
        log_pass "$description (HTTP $http_code)"
    else
        log_fail "$description - Expected $expected_status, got $http_code"
    fi
}

test_ssl() {
    log_info "Testing SSL certificate..."

    local domain=$(echo "$BASE_URL" | sed -E 's|https?://([^/:]+).*|\1|')
    local cert_info

    cert_info=$(echo | openssl s_client -connect "$domain:443" -servername "$domain" 2>/dev/null | openssl x509 -noout -dates 2>/dev/null || echo "SSL_ERROR")

    if [ "$cert_info" = "SSL_ERROR" ]; then
        log_fail "SSL certificate check failed"
    elif echo "$cert_info" | grep -q "notAfter"; then
        local expiry_date=$(echo "$cert_info" | grep notAfter | cut -d= -f2)
        log_pass "SSL certificate valid (expires: $expiry_date)"
    else
        log_fail "Could not parse certificate info"
    fi
}

test_https_redirect() {
    log_info "Testing HTTPS redirect..."

    local domain=$(echo "$BASE_URL" | sed -E 's|https?://([^/:]+).*|\1|')
    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" -L "http://$domain/" 2>/dev/null || echo "000")

    if [ "$http_code" = "200" ]; then
        log_pass "HTTPS redirect working (returns 200)"
    else
        log_fail "HTTPS redirect failed (HTTP $http_code)"
    fi
}

echo "========================================"
echo "Prequal Platform - Smoke Test Suite"
echo "========================================"
echo "Base URL: $BASE_URL"
echo "Started: $(date)"
echo "========================================"
echo ""

log_info "Starting smoke tests..."
echo ""

echo "--- Health Checks ---"
test_endpoint "GET" "/api/health" "200" "API health check"
test_endpoint "GET" "/api/health/live" "200" "Liveness probe"
test_endpoint "GET" "/api/health/ready" "200" "Readiness probe"
echo ""

echo "--- Authentication ---"
test_endpoint "POST" "/api/auth/login" "200" "Login endpoint exists" '{"email":"test@example.com","password":"test"}'

test_endpoint "POST" "/api/auth/login" "401" "Login with invalid credentials" '{"email":"bad@test.com","password":"wrong"}'
echo ""

echo "--- Dashboard & Compliance ---"
test_endpoint "GET" "/api/compliance/dashboard/summary" "200" "Dashboard summary endpoint"
test_endpoint "GET" "/api/compliance/subcontractors" "200" "Subcontractors endpoint"
test_endpoint "GET" "/api/compliance/status" "200" "Compliance status endpoint"
echo ""

echo "--- Alerts ---"
test_endpoint "GET" "/api/alerts" "200" "Alerts endpoint"
test_endpoint "GET" "/api/alerts/summary" "200" "Alerts summary"
echo ""

echo "--- Credentials ---"
test_endpoint "POST" "/api/credentials/subcontractors/00000000-0000-0000-0000-000000000001/credentials/upload" "401" "Credentials upload (unauthenticated)"
echo ""

echo "--- Billing ---"
test_endpoint "GET" "/api/billing/plans" "200" "Billing plans endpoint"
test_endpoint "GET" "/api/billing/subscription" "200" "Billing subscription endpoint"
echo ""

echo "--- SSL/TLS ---"
test_ssl
test_https_redirect
echo ""

echo "========================================"
echo "Test Results"
echo "========================================"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo "Completed: $(date)"
echo "========================================"

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}SMOKE TESTS FAILED${NC}"
    exit 1
else
    echo -e "${GREEN}ALL SMOKE TESTS PASSED${NC}"
    exit 0
fi