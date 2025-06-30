#!/bin/bash

# Скрипт для настройки глобального .gitignore для macOS
# Использование: ./scripts/setup-git-macos.sh

set -e

echo "🔧 Setting up global .gitignore for macOS..."

# Путь к глобальному .gitignore
GLOBAL_GITIGNORE="$HOME/.gitignore_global"

# Создаем или обновляем глобальный .gitignore
cat > "$GLOBAL_GITIGNORE" << 'EOF'
# macOS General
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Folder config file
[Dd]esktop.ini

# Recycle Bin
$RECYCLE.BIN/

# Windows thumbnail cache files
Thumbs.db:encryptable
ehthumbs_vista.db

# Dump file
*.stackdump

# Icon must end with two \r
Icon

EOF

# Настраиваем Git на использование глобального .gitignore
git config --global core.excludesfile "$GLOBAL_GITIGNORE"

echo "✅ Global .gitignore configured successfully!"
echo "📍 File location: $GLOBAL_GITIGNORE"
echo "🔧 Git configured to use global excludes"
echo ""
echo "💡 This will prevent macOS files from being tracked in ALL your Git repositories"
