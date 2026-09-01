

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import httpx
import os 



try:
    APP_ID = int(os.environ["VK_APP_ID"])
    VK_SERVICE_TOKEN = os.environ["VK_SERVICE_TOKEN"]
except KeyError as e:
    raise Exception(f"Missing required environment variable: {e}")
except ValueError:
    raise Exception("VK_APP_ID must be a valid integer")


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
    user_id: int = Field(..., description="ID пользователя ВКонтакте")
    weight: float = Field(..., ge=20, le=300, description="Вес в кг от 20 до 300")
    height: float = Field(..., ge=100, le=250, description="Рост в см от 100 до 250")


@app.get("/api/ver")
async def version():
    return {"version": 5}


@app.post("/api/calculate")
async def calculate_bmi(data: BMIRequest):
    try:
        # Проверяем подписку в реальном времени через VK API
        has_subscription = await check_user_subscription(data.user_id)

        if not has_subscription:
            raise HTTPException(
                status_code=403,
                detail="Доступ запрещен. Оформите подписку в приложении.",
            )

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


async def check_user_subscription(user_id: int) -> bool:
    url = "https://vk.ru"

    params = {
        "access_token": VK_SERVICE_TOKEN,
        "v": "5.131",  # Версия API ВК
        "user_id": user_id,
        "app_id": APP_ID,
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)

        if response.status_code != 200:
            return False

        result = response.json()

        # Если ВК вернул ошибку (например, платежи не настроены)
        if "error" in result:
            print(f"Ошибка VK API: {result['error']['error_msg']}")
            return False

        subscription = result.get("response")

        # Если подписка найдена и её статус "active" (активна)
        if subscription and subscription.get("status") == "active":
            print(f"subscription: {subscription}")
            return True

        return False


# Для локального запуска (python main.py), на Лаеро сервер запустится сам через uvicorn
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
