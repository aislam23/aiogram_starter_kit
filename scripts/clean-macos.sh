#!/bin/bash

# Скрипт для очистки macOS артефактов из проекта
# Использование: ./scripts/clean-macos.sh

set -e

echo "🧹 Cleaning macOS artifacts from project..."

# Удаляем .DS_Store файлы
echo "🗑️  Removing .DS_Store files..."
find . -name ".DS_Store" -delete 2>/dev/null || true

# Удаляем ._* файлы (resource forks)
echo "🗑️  Removing resource fork files..."
find . -name "._*" -delete 2>/dev/null || true

# Удаляем .Spotlight-V100
echo "🗑️  Removing Spotlight files..."
find . -name ".Spotlight-V100" -delete 2>/dev/null || true

# Удаляем .Trashes
echo "🗑️  Removing Trash files..."
find . -name ".Trashes" -delete 2>/dev/null || true

# Удаляем Thumbs.db (Windows)
echo "🗑️  Removing Windows thumbnail files..."
find . -name "Thumbs.db" -delete 2>/dev/null || true
find . -name "ehthumbs.db" -delete 2>/dev/null || true

echo "✅ macOS artifacts cleaned successfully!"
echo "💡 These files are now ignored in .gitignore and .dockerignore"
