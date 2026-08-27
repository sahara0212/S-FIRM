#!/bin/bash
lsof -ti:8000 | xargs kill -9 2>/dev/null && echo "✅ 종료됨" || echo "실행 중인 서버 없음"
