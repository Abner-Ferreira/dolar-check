from requests import api
from requests.exceptions import RequestException, Timeout, ConnectionError, HTTPError
from decimal import Decimal, ROUND_HALF_UP
from dotenv import load_dotenv
import os
import psycopg2
from datetime import datetime

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TELEGRAM_TOKEN")
CHAT_TOKEN = os.getenv("CHAT_TELEGRAM_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")


current_date = datetime.now().strftime("%m-%d-%Y")

url_api_dolar = f"https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/CotacaoDolarDia(dataCotacao=@dataCotacao)?@dataCotacao='{current_date}'&$top=100&$format=json&$select=cotacaoCompra"

url_api_telegram = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"


def get_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"), sslmode="require")


def get_dolar():
    try:
        response = api.get(url_api_dolar, timeout=10)
        response.raise_for_status()

        data = response.json()
        value = value = data['value'][0]['cotacaoCompra']

        return Decimal(value).quantize(Decimal("0.00"), ROUND_HALF_UP)

    except Exception as e:
        print("❌ Erro ao buscar dólar comercial:", e)
        return None


def read_price():

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT price
                FROM dolar_price
                ORDER BY created_at DESC
                LIMIT 1
            """
            )
            row = cur.fetchone()

    return Decimal(row[0]) if row else None


def save_price(price: Decimal):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO dolar_price (price) VALUES (%s)", (price,))


def send_message(old_price, current_price, type_of_message):

    payload = {
        "chat_id": CHAT_TOKEN,
    }

    if type_of_message == "queda":
        payload["text"] = (
            "🚨 O preço do dólar caiu 🚨\n\n"
            f"Preço antigo: R$ {old_price}\n"
            f"Preço atual:  R$ {current_price}"
        )

    elif type_of_message == "aumento":
        payload["text"] = (
            "🚨 O preço do dólar aumentou 🚨\n\n"
            f"Preço antigo: R$ {old_price}\n"
            f"Preço atual:  R$ {current_price}"
        )

    else:
        payload["text"] = (
                    "🚨 O preço do dólar se manteve 🚨\n\n"
                    f"Preço antigo: R$ {old_price}\n"
                    f"Preço atual:  R$ {current_price}"
                )
    try:
        response = api.post(url_api_telegram, json=payload, timeout=10)

        print("Status code:", response.status_code)
        print("Resposta Telegram:", response.text)

        response.raise_for_status()

    except Timeout:
        print("⏱️ Timeout ao enviar mensagem")
    except ConnectionError:
        print("🌐 Sem conexão com a internet")
    except RequestException as e:
        print("❌ Erro ao enviar mensagem no Telegram:", e)
        return False

    return True


def main():
    current_price = get_dolar()


    if current_price is None:
        print("ℹ️ Execução finalizada sem atualizar preço")
        return

    old_price = read_price()

    # return print(old_price)
    if old_price is None:
        save_price(current_price)
        print(f"Preço inicial salvo: {current_price}")
        return 

    # Queda do dolar
    if current_price < old_price:
        # Salva o preço no banco de dados
        save_price(current_price)
        return send_message(old_price, current_price, "queda")

    # Aumento do dolar
    elif current_price > old_price:
        # Salva o preço no banco de dados
        save_price(current_price)
        return send_message(old_price, current_price, "aumento")

    # Preço do dolar manteve
    else:
        # Salva o preço no banco de dados
        save_price(current_price)
        return send_message(old_price, current_price, "igual")


if __name__ == "__main__":
    main()

