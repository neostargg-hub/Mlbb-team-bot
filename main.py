import asyncio
import logging
import uvicorn
from bot import dp, bot
from api import app as fastapi_app

async def main():
    # Запускаем веб-сервер
    server_config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=10000, log_level="info")
    server = uvicorn.Server(server_config)
    
    # Запускаем бота в фоне
    bot_task = asyncio.create_task(dp.start_polling(bot))
    
    # Запускаем сервер
    await server.serve()
    bot_task.cancel()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())