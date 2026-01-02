from datetime import datetime
import os
import time
from contextlib import contextmanager, asynccontextmanager

import mysql.connector
from mysql.connector import Error
from fastapi import FastAPI, Request, Depends, Header
from typing import Optional


# --- 1. Конфигурация ---
# Считываем конфигурацию БД из переменных окружения
db_host = os.environ.get('DB_HOST', 'db')
db_user = os.environ.get('DB_USER', 'app')
db_password = os.environ.get('DB_PASSWORD', 'QwErTy1234')
db_name = os.environ.get('DB_NAME', 'example')

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Код, который выполнится перед запуском приложения
    print("=" * 50)
    print("ПРИЛОЖЕНИЕ ЗАПУСКАЕТСЯ...")
    print(f"Параметры БД: host={db_host}, user={db_user}, db={db_name}")
    print("=" * 50)

    # МНОГОКРАТНЫЕ ПОПЫТКИ подключения
    max_retries = 15  # Увеличили до 15 попыток
    connected = False

    for attempt in range(max_retries):
        try:
            print(f"\n[Попытка {attempt + 1}/{max_retries}] Подключение к БД...")
            with get_db_connection() as db:
                cursor = db.cursor()
                print("✅ Подключение успешно!")

                # Проверяем/создаем таблицу
                create_table_query = """
                CREATE TABLE IF NOT EXISTS requests (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    request_date DATETIME,
                    request_ip VARCHAR(255)
                )
                """
                cursor.execute(create_table_query)
                db.commit()

                # Проверяем что таблица существует
                cursor.execute("SHOW TABLES LIKE 'requests'")
                result = cursor.fetchone()
                if result:
                    print("✅ Таблица 'requests' существует или создана")
                else:
                    print("⚠️  Таблица 'requests' не найдена после создания")

                cursor.close()
                connected = True
                print("🎉 БД готова к работе!")
                break  # Успешно, выходим из цикла

        except Error as err:
            print(f"❌ Ошибка подключения: {err}")
            if attempt < max_retries - 1:
                wait_time = 3
                print(f"⏳ Жду {wait_time} секунд перед следующей попыткой...")
                time.sleep(wait_time)
            else:
                print("💥 Не удалось подключиться к БД после всех попыток")

    if not connected:
        print("🚨 ВНИМАНИЕ: Приложение запускается БЕЗ подключения к БД!")

    print("=" * 50)
    yield
    print("Приложение останавливается.")


# Создаем экземпляр FastAPI с использованием lifespan
app = FastAPI(
    title="Shvirtd Example FastAPI",
    description="Учебный проект, FastAPI+Docker.",
    version="1.0.0",
    lifespan=lifespan
)


# --- 2. Управление соединением с БД ---
@contextmanager
def get_db_connection():
    db = None
    try:
        db = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            ssl_ca='/etc/ssl/certs/yandex-ca.pem',  # Путь к CA-сертификату
            ssl_verify_cert=True
        )
        yield db
    finally:
        if db is not None and db.is_connected():
            db.close()


# --- 3. Зависимость для получения IP ---
def get_client_ip(x_real_ip: Optional[str] = Header(None)):
    return x_real_ip


# --- 4. Основной эндпоинт ---
@app.get("/")
def index(request: Request, ip_address: Optional[str] = Depends(get_client_ip)):
    final_ip = ip_address  # Только из X-Forwarded-For, без fallback

    now = datetime.now()
    current_time = now.strftime("%Y-%m-%d %H:%M:%S")

    try:
        with get_db_connection() as db:
            cursor = db.cursor()
            query = "INSERT INTO requests (request_date, request_ip) VALUES (%s, %s)"
            values = (current_time, final_ip)
            cursor.execute(query, values)
            db.commit()
            cursor.close()
    except mysql.connector.Error as err:
        return {"error": f"Ошибка при работе с базой данных: {err}"}

    # Подсказка для студентов при неправильном обращении
    if final_ip is None:
        ip_display = "похоже, что вы направляете запрос в неверный порт(например curl http://127.0.0.1:5000). Правильное выполнение задания - отправить запрос в порт 8090."
    else:
        ip_display = final_ip

    return f'TIME: {current_time}, IP: {ip_display}'


# --- 5. Отладочный эндпоинт ---
@app.get("/debug")
def debug_headers(request: Request):
    """Показывает все заголовки для отладки откуда берется IP"""
    return {
        "headers": dict(request.headers),
        "client_host": request.client.host if request.client else None,
        "x_forwarded_for": request.headers.get('x-forwarded-for'),
        "real_ip": request.headers.get('x-real-ip'),
        "forwarded": request.headers.get('forwarded')
    }


# --- 6. Эндпоинт для просмотра записей в БД ---
@app.get("/requests")
def get_requests():
    """Возвращает все записи из таблицы requests для проверки"""
    try:
        with get_db_connection() as db:
            cursor = db.cursor()
            query = "SELECT id, request_date, request_ip FROM requests ORDER BY id DESC LIMIT 50"
            cursor.execute(query)
            records = cursor.fetchall()
            cursor.close()

            # Преобразуем записи в читабельный формат
            result = []
            for record in records:
                result.append({
                    "id": record[0],
                    "request_date": record[1].strftime("%Y-%m-%d %H:%M:%S") if record[1] else None,
                    "request_ip": record[2]
                })

            return {
                "total_records": len(result),
                "records": result
            }
    except mysql.connector.Error as err:
        return {"error": f"Ошибка при чтении из базы данных: {err}"}


# --- 7. Запуск приложения ---
# Для запуска этого файла используется ASGI-сервер, например, uvicorn.
# Команда: uvicorn main:app --reload
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=5000)
