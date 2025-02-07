import random
import Secret
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Этапы диалога
SELECT_USER, VERIFY_PASSWORD, SELECT_MODEL, HANDLE_COMMAND = range(4)

# Данные пользователей и объектов
users = ["Админ", "Гость", "Пользователь-1", "Пользователь-2", "Пользователь-3"]
objects = ["Файл-1", "Файл-2", "Диск", "Флешка"]

# Пароли пользователей
user_passwords = {
    "Админ": "Admin123",
    "Гость": "Guest123",
    "Пользователь-1": "User123",
    "Пользователь-2": "User234",
    "Пользователь-3": "User345",
}
# Уровни безопасности
SECURITY_LEVELS = {"Открытые данные": 0, "Секретно": 1, "Совершенно секретно": 2}

# Матрица прав для дискреционной модели (кодировка прав: 0–7 в битовом виде)
access_matrix = [
    [7, 7, 7, 7],  # Админ: все права
    [0, 4, 4, 0],  # Гость: чтение Файл-2 и Диск
    [5, 6, 7, 0],  # Пользователь-1: разные права
    [2, 0, 3, 0],  # Пользователь-2: разные права
    [1, 1, 1, 1],  # Пользователь-3: разные права
]

# Уровни конфиденциальности для мандатной модели (заполняются случайно)
object_confidentiality = {obj: random.choice(list(SECURITY_LEVELS.values())) for obj in objects}
user_clearance = {user: random.choice(list(SECURITY_LEVELS.values())) for user in users}

current_user = None  # Текущий пользователь
use_mandatory_model = True  # Флаг для выбора модели (мандатная по умолчанию)


def decode_rights(value: int) -> str:
    """Преобразование числовых прав в текст."""
    binary = f"{value:03b}"
    rights = []
    if binary[0] == '1':
        rights.append("Чтение")
    if binary[1] == '1':
        rights.append("Запись")
    if binary[2] == '1':
        rights.append("Передача прав")
    return ", ".join(rights) if rights else "Запрет"


def decode_security_level(level):
    """Преобразование уровня безопасности в текст."""
    for name, value in SECURITY_LEVELS.items():
        if level == value:
            return name
    return "Неизвестный уровень"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало работы: выбор пользователя."""
    keyboard = [[user] for user in users]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text("Добро пожаловать! Выберите пользователя:", reply_markup=reply_markup)
    return SELECT_USER


async def select_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрос ввода пароля после выбора пользователя."""
    global current_user
    current_user = update.message.text
    if current_user not in users:
        await update.message.reply_text("Пользователь не найден. Попробуйте снова.")
        return SELECT_USER

    await update.message.reply_text(f"Введите пароль для пользователя {current_user}:")
    return VERIFY_PASSWORD


async def verify_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Проверка пароля пользователя."""
    global current_user
    password = update.message.text

    if user_passwords.get(current_user) == password:
        keyboard = [["Мандатная", "Дискреционная"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        await update.message.reply_text(f"Пароль верен! Выберите модель безопасности:", reply_markup=reply_markup)
        return SELECT_MODEL  # Переход к выбору модели
    else:
        await update.message.reply_text("Неверный пароль. Попробуйте снова или выберите другого пользователя.")
        current_user = None
        return SELECT_USER


async def handle_selected_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора модели безопасности."""
    global use_mandatory_model
    model = update.message.text.lower()

    if model not in ["мандатная", "дискреционная"]:
        await update.message.reply_text("Ошибка: выберите модель безопасности из предложенных вариантов.")
        return SELECT_MODEL  # Повторно запросить выбор модели

    use_mandatory_model = (model == "мандатная")

    if use_mandatory_model:
        user_level = user_clearance[current_user]
        accessible_objects = [obj for obj, level in object_confidentiality.items() if user_level >= level]
        response = f"Вы выбрали мандатную модель безопасности.\nВаш уровень допуска: {decode_security_level(user_level)}\nДоступные объекты:\n"
        response += "\n".join(f"{obj}: {decode_security_level(object_confidentiality[obj])}" for obj in accessible_objects)
    else:
        user_index = users.index(current_user)
        response = f"Вы выбрали дискреционную модель безопасности.\nВаши права:\n"
        for i, obj in enumerate(objects):
            response += f"{obj}: {decode_rights(access_matrix[user_index][i])}\n"

    await update.message.reply_text(response + "\nВведите команду (например, 'запрос <объект>' для мандатной модели или '<чтение, запись или наделить> <объект>' для дискреционной модели).\nИспользуйте /switch_user для смены пользователя или /switch_model для смены модели.")
    return HANDLE_COMMAND  # Переход к обработке команд


async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка команд пользователя в зависимости от выбранной модели."""
    global current_user, use_mandatory_model

    user_index = users.index(current_user)
    message = update.message.text.split()

    if len(message) < 2:
        if use_mandatory_model:
            await update.message.reply_text("Ошибка: введите команду в формате 'запрос <объект>'.")
        else:
            await update.message.reply_text("Ошибка: введите команду в формате '<операция: чтение, запись, наделить> <объект> [пользователь] [1-право на чтение/2-право на запись/3-чтение и запись]'.")
        return HANDLE_COMMAND

    operation = message[0].lower()
    obj = message[1]

    if obj not in objects:
        await update.message.reply_text(f"Объект '{obj}' не найден.")
        return HANDLE_COMMAND

    obj_index = objects.index(obj)

    # Мандатная модель
    if use_mandatory_model:
        user_level = user_clearance[current_user]
        obj_level = object_confidentiality[obj]
        if operation == "запрос":
            if user_level >= obj_level:
                await update.message.reply_text(f"Доступ к '{obj}' разрешен.")
            else:
                await update.message.reply_text(f"Доступ к '{obj}' запрещен. Недостаточно прав.")
        else:
            await update.message.reply_text("Неизвестная команда для мандатной модели. Используйте 'запрос <объект>'.")
    else:
        # Дискреционная модель: проверка прав по матрице доступа
        if operation == "наделить" or operation == "3":
            if len(message) != 4:
                await update.message.reply_text("Ошибка: для передачи прав укажите пользователя и уровень.")
                return HANDLE_COMMAND

            target_user = message[2]
            if target_user not in users:
                await update.message.reply_text(f"Пользователь '{target_user}' не найден.")
                return HANDLE_COMMAND

            level_need = int(message[3])
            if level_need not in (1, 2, 3):
                await update.message.reply_text("Ошибка: указано некорректное право передачи.")
                return HANDLE_COMMAND

            if not check_rights(user_index, obj_index, "наделить"):
                await update.message.reply_text("У вас нет прав на передачу прав на этот объект.")
                return HANDLE_COMMAND

            level = (
                6 if level_need == 3 and check_rights(user_index, obj_index, "запись") and check_rights(user_index, obj_index, "чтение") else
                4 if level_need == 1 and check_rights(user_index, obj_index, "чтение") else
                2 if level_need == 2 and check_rights(user_index, obj_index, "запись") else
                None
            )

            if level is None:
                await update.message.reply_text("Ошибка: недостаточно прав для передачи данных прав.")
                return HANDLE_COMMAND

            target_index = users.index(target_user)
            access_matrix[target_index][obj_index] = level
            await update.message.reply_text(f"Права уровня {level} на объект '{obj}' успешно переданы пользователю '{target_user}'.")
        else:
            # Проверка других операций
            if not check_rights(user_index, obj_index, operation):
                await update.message.reply_text(f"У вас нет прав на выполнение операции '{operation}' над объектом '{obj}'.")
            else:
                await update.message.reply_text(f"Операция '{operation}' над '{obj}' выполнена успешно.")

    return HANDLE_COMMAND


def check_rights(user_index: int, obj_index: int, operation: str) -> bool:
    """Проверка прав пользователя на выполнение операции в дискреционной модели."""
    rights = access_matrix[user_index][obj_index]
    if (operation == "чтение" or operation == "1") and rights & 4:
        return True
    if (operation == "запись" or operation == "2") and rights & 2:
        return True
    if (operation == "наделить" or operation == "3") and rights & 1:
        return True
    return False


async def switch_model(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Команда для смены модели безопасности."""
    keyboard = [["Мандатная", "Дискреционная"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    await update.message.reply_text("Выберите новую модель безопасности:", reply_markup=reply_markup)
    return SELECT_MODEL  # Возврат в состояние выбора модели


async def switch_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Команда для смены пользователя."""
    global current_user, use_mandatory_model
    current_user = None
    use_mandatory_model = True  # Сбрасываем модель безопасности по умолчанию
    await update.message.reply_text("Вы вернулись к выбору пользователя.")
    return await start(update, context)  # Переход к выбору пользователя


async def info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отображение таблицы прав доступа и уровней конфиденциальности."""
    header = " Кто | " + " | ".join(objects) + " |\n"
    separator = "--" * len(header) + "\n"
    table = header + separator

    for i, user in enumerate(users):
        row = f"{user:<5} | " + " | ".join(
            f"{decode_rights(access_matrix[i][j])}" for j in range(len(objects))) + " |\n"
        table += row

    object_info = "\n".join(f"{obj}: {decode_security_level(level)}" for obj, level in object_confidentiality.items())
    user_info = "\n".join(f"{user}: {decode_security_level(level)}" for user, level in user_clearance.items())
    await update.message.reply_text(f"Таблица прав доступа (дискреционная модель):\n\n{table}\n\n"
                                    f"Уровни конфиденциальности объектов (мандатная модель):\n{object_info}\n"
                                    f"Уровни допуска пользователей:\n{user_info}")


async def quit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Выход пользователя из системы."""
    global current_user
    if current_user:
        await update.message.reply_text(f"Пользователь '{current_user}' вышел из системы. До свидания!")
    else:
        await update.message.reply_text("Вы не вошли в систему.")
    current_user = None
    return await start(update, context)  # Возврат к выбору пользователя


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена текущей операции."""
    if current_user:
        await update.message.reply_text("Операция отменена. Вы можете ввести новую команду.")
        return HANDLE_COMMAND
    else:
        await update.message.reply_text("Операция отменена. Возврат к выбору пользователя.")
        return SELECT_USER  # Возврат к выбору пользователя


def main():
    """Запуск бота."""
    token = Secret.token  # Замените на ваш токен
    application = ApplicationBuilder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_user)],
            VERIFY_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_password)],
            SELECT_MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_selected_model)],
            HANDLE_COMMAND: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_command),
                CommandHandler("switch_user", switch_user),
                CommandHandler("switch_model", switch_model),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("quit", quit),
        ],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("info", info))  # Обработчик команды /info

    application.run_polling()


if __name__ == "__main__":
    main()
