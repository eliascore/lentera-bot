#!/bin/bash

# Script untuk add + commit + push semua perubahan di Codespaces ke GitHub
# Pemakaian: ./push_all.sh "Pesan commit"

# Kalau user nggak ngisi pesan commit
if [ -z "$1" ]; then
  echo "⚠️  Harap isi pesan commit. Contoh: ./push_all.sh \"Update bot forwarder\""
  exit 1
fi

# Tambahkan semua file
git add -A

# Commit dengan pesan dari argumen
git commit -m "$1"

# Push ke branch aktif
BRANCH=$(git branch --show-current)
git push origin $BRANCH
