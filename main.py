import os

from pathlib import Path
from pydantic import VERSION, BaseModel, Field


from fastapi import FastAPI, HTTPException, Request as FastAPIRequest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from vk_api import check_user_subscription, is_valid_vk_query


VERSION = 11

# Находим путь к папке, где лежит сам файл main.py
BASE_DIR = Path(__file__).resolve().parent

DATABASE_URL = os.environ.get("DATABASE_URL") 
print(f"DATABASE_URL: {DATABASE_URL}, BASE_DIR: {BASE_DIR}")

# Изменяем пути для документации, чтобы Layero их не перехватывал
app = FastAPI(
    docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/openapi.json"
)


# Настраиваем CORS, чтобы фронтенд VK Mini App мог слать запросы к вашему бэкенду
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://bmi.layero.app",
        "https://bmi-react.layero.app",
        "http://localhost:8000",  # или порт, на котором запускаете фронт локально
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Описываем структуру входящих данных с валидацией через Pydantic
class BMIRequest(BaseModel):
    weight: float = Field(..., ge=20, le=300, description="Вес в кг от 20 до 300")
    height: float = Field(..., ge=100, le=250, description="Рост в см от 100 до 250")



# 1. Монтируем папку со статикой (css, js библиотеки)
# Передаем абсолютные пути, которые соберутся автоматически и на ПК, и на Layero
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# 2. Указываем папку, где лежат наши Jinja2 шаблоны 
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# 3. Главная ручка, которая собирает и возвращает готовую SPA-страницу
@app.get("/", response_class=HTMLResponse)
async def read_root(request: FastAPIRequest):
    # Метод TemplateResponse автоматически возьмет base.html,
    # выполнит в нем все инструкции {% include %} и вернет клиенту готовый HTML
    return templates.TemplateResponse("base.html", {"request": request})

@app.get("/api/ver")
async def version():
    return {"version": VERSION}


@app.post("/api/calculate")
async def calculate_bmi(data: BMIRequest, request: FastAPIRequest):

    try:

        # Извлекаем строку параметров запуска из кастомного заголовка
        print(f'headers: {request.headers}')
        vk_query = request.headers.get("X-VK-Sign")
        print(f'vk_query: {vk_query}')
        
        # Проверяем подпись
        is_valid, user_id = is_valid_vk_query(vk_query)
        
        if not is_valid or not user_id:
            raise HTTPException(
                status_code=401, 
                detail="Ошибка авторизации: поддельный запрос или истек срок сессии."
            )

        # Проверяем подписку по НАСТОЯЩЕМУ user_id, полученному из защищенной строки ВК
        has_subscription = await check_user_subscription(user_id)
        print(f'user_id: {user_id}, has_subscription: {has_subscription}')
        # if not has_subscription:
        #     raise HTTPException(
        #         status_code=403, 
        #         detail="Доступ запрещен. Оформите подписку."
        #     )

        # Логика расчета
        height_in_meters = data.height / 100
        bmi = round(data.weight / (height_in_meters**2), 1)

        # Определение статуса
        if bmi < 18.5:
            status = "Недостаточный вес"
        elif bmi < 25:
            status = "Нормальный вес"
        elif bmi < 30:
            status = "Избыточный вес"
        else:
            status = "Ожирение"

        return {"bmi": bmi, "status": status}

    except Exception as e:
        raise HTTPException(status_code=400, detail="Ошибка при расчете данных")



# Для локального запуска (python main.py), на Лаеро сервер запустится сам через uvicorn
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
