#!/bin/sh
# Start the apply site (Flask, loopback only) and the chat (Chainlit, public port).
set -e
export PYTHONPATH="$(pwd)"
# The public chat must be password protected. Set ALLOW_NO_AUTH=1 only for local tests.
if [ "$ALLOW_NO_AUTH" != "1" ]; then
  : "${APP_USERNAME:?APP_USERNAME is not set (chat login)}"
  : "${APP_PASSWORD:?APP_PASSWORD is not set (chat login)}"
  : "${CHAINLIT_AUTH_SECRET:?CHAINLIT_AUTH_SECRET is not set (session signing secret)}"
fi

python -m sandbox reset
python -m sandbox seed

python -m sandbox serve --port 5000 &

# Wait until the apply site answers (up to about 20 seconds).
i=0
until python -c "
import urllib.request, urllib.error
try:
    urllib.request.urlopen('http://127.0.0.1:5000/jobs/job_001', timeout=2)
except urllib.error.HTTPError:
    pass  # any HTTP answer means the server is up
" 2>/dev/null; do
  i=$((i + 1))
  if [ "$i" -ge 20 ]; then
    echo "Apply site did not start" >&2
    exit 1
  fi
  sleep 1
done

exec chainlit run ui/app.py --host 0.0.0.0 --port "${PORT:-7860}" --headless
