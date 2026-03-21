#!/bin/bash
# add_master.sh — добавить нового мастера одной командой
#
# Использование:
#   ./add_master.sh master3 "Студия Оля" "г. Минск, ул. Советская 10" "токен" "111222333"

set -e

NAME=$1        # уникальный ключ: master3
STUDIO=$2      # название студии
ADDRESS=$3     # адрес
TOKEN=$4       # токен бота от @BotFather
ADMIN_ID=$5    # Telegram ID мастера

if [ -z "$NAME" ] || [ -z "$TOKEN" ] || [ -z "$ADMIN_ID" ]; then
    echo "Использование: ./add_master.sh <ключ> <студия> <адрес> <токен> <admin_id>"
    echo "Пример: ./add_master.sh master3 'Студия Оля' 'ул. Ленина 1' 'токен' '123456'"
    exit 1
fi

# Добавляем секцию в docker-compose.yml
cat >> docker-compose.yml << EOF

  bot_${NAME}:
    build: .
    restart: always
    environment:
      - BOT_TOKEN=${TOKEN}
      - ADMIN_IDS=${ADMIN_ID}
      - STUDIO_NAME=${STUDIO}
      - STUDIO_ADDRESS=${ADDRESS}
      - TIMEZONE=Europe/Minsk
      - SLOT_DURATION=15
    volumes:
      - ./data/${NAME}:/app/data
EOF

# Создаём папку для данных
mkdir -p ./data/${NAME}

echo "✅ Мастер ${NAME} добавлен!"
echo ""
echo "Запустите бота:"
echo "  docker compose up -d bot_${NAME}"
echo ""
echo "Или перезапустите всех:"
echo "  docker compose up -d"
