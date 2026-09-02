from fastapi import FastAPI, HTTPException, Request as FastAPIRequest
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from vk_api import check_user_subscription, is_valid_vk_query

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


@app.get("/")
async def index():
    return await version()

@app.get("/api/ver")
async def version():
    return {"version": 10}


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
