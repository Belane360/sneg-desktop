#!/bin/bash
set -eu
# Finder launcher. All writes go to user-owned Application Support, not the bundle.
resources="$(cd -- "$(dirname -- "$0")/../Resources" && pwd)"
support="$HOME/Library/Application Support/Sneg"
mkdir -p "$support"
log="$support/launch.log"
exec >>"$log" 2>&1
fail() {
  /usr/bin/osascript -e 'display dialog "Не удалось запустить Снег. Подробности сохранены в launch.log; сейчас откроется папка с ним." with title "Снег" buttons {"OK"} default button "OK"' || true
  /usr/bin/open "$support"
  exit 1
}
trap fail ERR
runtime="$support/runtime-v2"
if ! "$runtime/bin/python" -c 'from PySide6 import QtWidgets, QtMultimedia; import PySide6; assert PySide6.__version__ == "6.8.3"' 2>/dev/null; then
  /usr/bin/osascript -e 'display dialog "Первый запуск: Снег загрузит необходимые компоненты (около 450 МБ). Нужен интернет; подготовка может занять несколько минут. После неё приложение откроется само. Повторные запуски — без установки." with title "Подготовка Снега" buttons {"Отмена", "Продолжить"} default button "Продолжить" cancel button "Отмена"' || exit 0
  chosen=""
  for candidate in /Library/Frameworks/Python.framework/Versions/{3.13,3.12,3.11,3.10,3.9}/bin/python3 /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    if [ -x "$candidate" ] && "$candidate" -c 'import sys; assert (3,9) <= sys.version_info[:2] < (3,14)' 2>/dev/null; then
      chosen="$candidate"; break
    fi
  done
  if [ -z "$chosen" ]; then
    /usr/bin/osascript -e 'display dialog "Нужен Python версии 3.9–3.13. Установите Python 3.12 с python.org, затем откройте Снег повторно." with title "Снег" buttons {"OK"} default button "OK"'
    exit 1
  fi
  "$chosen" -m venv "$runtime"
  "$runtime/bin/python" -m pip install --upgrade --only-binary=:all: 'pip<26'
  "$runtime/bin/python" -m pip install --only-binary=:all: -r "$resources/requirements.txt"
fi
cd "$resources"
"$runtime/bin/python" main.py
