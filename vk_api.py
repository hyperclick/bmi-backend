import hashlib
import hmac

import httpx
import os
from urllib.parse import parse_qsl, urlencode


try:
    VK_PROTECTED_KEY = os.environ["VK_PROTECTED_KEY"] 
    APP_ID = int(os.environ["VK_APP_ID"])
    VK_SERVICE_TOKEN = os.environ["VK_SERVICE_TOKEN"]
except KeyError as e:
    raise Exception(f"Missing required environment variable: {e}")
except ValueError:
    raise Exception("VK_APP_ID must be a valid integer")



async def check_user_subscription(user_id: int) -> bool:
    url = "https://vk.ru/method/orders.getSubscriptionByUserId"

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
        # Берем список подписок из ответа
        subscriptions = result.get("response")

        # Проверяем, что список не пуст, и смотрим статус первой подписки
        if subscriptions and isinstance(subscriptions, list) and len(subscriptions) > 0:
            first_subscription = subscriptions[0]
            if first_subscription.get("status") == "active":
                print(f"subscription: {first_subscription}")
                return True

        return False

def is_valid_vk_query(query_string: str) -> tuple[bool, int | None]:
    """
    Проверяет валидность параметров запуска VK и возвращает (True, user_id),
    если подпись верна. Иначе возвращает (False, None).
    """
    if not query_string:
        return False, None

    # Декодируем строку параметров в список кортежей
    try:
        query_params = dict(parse_qsl(query_string, keep_blank_values=True))
    except Exception:
        return False, None

    # Ищем подпись, которую прислал ВК
    vk_sign = query_params.get("sign")
    if not vk_sign:
        return False, None

    # Отбираем только параметры, начинающиеся на "vk_" и сортируем их по ключам
    vk_params = {k: v for k, v in query_params.items() if k.startswith("vk_")}
    sorted_params = sorted(vk_params.items())

    print(f'params: {sorted_params}')
    
    # Формируем строку для проверки (пары ключ=значение через &)
    sign_str = urlencode(sorted_params)

    # Считаем SHA256 HMAC подпись, используя наш Защищенный ключ приложения
    hash_code = hmac.new(
        VK_PROTECTED_KEY.encode("utf-8"),
        sign_str.encode("utf-8"),
        hashlib.sha256
    ).digest()

    # Кодируем в URL-safe base64 и убираем лишнее (алгоритм ВК требует хэш в таком формате)
    import base64
    calc_sign = base64.b64encode(hash_code).decode("utf-8")
    calc_sign = calc_sign.replace("+", "-").replace("/", "_").rstrip("=")

    if calc_sign == vk_sign:
        # Подпись верна! Возвращаем True и реальный ID пользователя из параметров
        return True, int(query_params.get("vk_user_id"))
        
    return False, None