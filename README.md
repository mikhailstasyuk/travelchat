# travelchat

RAG-система для поиска информации по чат-данным Тбилиси.

## Быстрый запуск

1. `make setup` — создаёт файл `.env`
2. Отредактируйте `.env`, добавив ваш OpenAI API ключ
3. `make quick-start` — собирает и запускает всё необходимое


## Сервисы

- **API**: http://localhost:8000 - FastAPI бэкенд
- **Streamlit**: http://localhost:8501 - веб-интерфейс
- **Weaviate**: http://localhost:8080 - векторная БД

## Использование

1. Загрузите CSV с колонкой `messages_json` через Streamlit и проиндексируйте
2. Задавайте вопросы о данных чата

## Команды

```bash
make up        # Запустить сервисы
make down      # Остановить
make logs      # Посмотреть логи
```
