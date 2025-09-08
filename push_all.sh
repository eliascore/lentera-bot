#!/bin/bash
if [ -z "$1" ]; then
  echo "⚠️  Harap isi pesan commit. Contoh: ./push_all.sh \"Update bot forwarder\""
  exit 1
fi

git add -A
git commit -m "$1"

BRANCH=$(git branch --show-current)

# Tarik update terbaru sebelum push
git pull --rebase origin $BRANCH

# Push setelah sinkron
git push origin $BRANCH
