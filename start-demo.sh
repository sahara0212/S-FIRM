#!/bin/bash
# 시연용 로컬 실행 — 법령 실시간 연동 포함 (집 네트워크에서만 실시간 동작)
cd "$(dirname "$0")"

if [ ! -x .venv/bin/uvicorn ]; then
  echo "가상환경이 없습니다. 아래를 먼저 실행하세요:"
  echo "  ~/.local/bin/python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

# 기존 프로세스 정리
lsof -ti:8000 | xargs kill -9 2>/dev/null

echo "▶ S-FIRM 책무구조도 운영 플랫폼 기동 중..."
cd backend
../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/sfirm-local.log 2>&1 &
PID=$!
cd ..

for i in $(seq 1 20); do
  sleep 1
  if curl -s -o /dev/null -m 2 http://127.0.0.1:8000/; then
    STATUS=$(curl -s -m 20 "http://127.0.0.1:8000/api/v1/law-monitoring?days=90" \
      | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('law_api_status'),sum(len(v.get('changes',[])) for v in d['core'].values()))" 2>/dev/null)
    set -- $STATUS
    if [ "$1" = "live" ]; then
      echo "✅ 법령 실시간 연동 정상 — 변경 $2건"
    else
      echo "⚠️  법령 실시간 연동 실패 (현재 네트워크 IP 미등록) — 기준 법령으로 표시됩니다"
      echo "    현재 공인 IP: $(curl -s -m 5 https://api.ipify.org)"
    fi
    echo "✅ 준비 완료 (PID $PID)   로그: tail -f /tmp/sfirm-local.log"
    echo "   로그인: admin / sfirm2026"
    open http://localhost:8000
    exit 0
  fi
done
echo "❌ 기동 실패 — tail /tmp/sfirm-local.log 확인"
