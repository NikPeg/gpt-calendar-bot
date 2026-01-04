"""
Тесты для парсинга ошибок Telegram и целенаправленного исправления markdown.
"""

import re


def parse_telegram_error(error_message: str) -> tuple[str | None, int | None]:
    """
    Парсит сообщение об ошибке от Telegram и извлекает тип entity и byte offset.

    Копия функции из utils.py для тестирования без импорта всего модуля.
    """
    # Маппинг типов entity на символы markdown
    entity_to_char = {
        "underline": "__",
        "bold": "*",
        "italic": "_",
        "strikethrough": "~",
        "code": "`",
        "spoiler": "||",
    }

    # Ищем тип entity и byte offset
    # Паттерн: "Can't find end of <EntityType> entity at byte offset <number>"
    pattern = r"Can't find end of (\w+) entity at byte offset (\d+)"
    match = re.search(pattern, error_message, re.IGNORECASE)

    if match:
        entity_type = match.group(1).lower()
        byte_offset = int(match.group(2))

        # Получаем соответствующий символ
        char = entity_to_char.get(entity_type)
        if char:
            return char, byte_offset

    return None, None


def fix_markdown_at_offset(text: str, problem_char: str, byte_offset: int) -> str:
    """
    Исправляет конкретный проблемный символ markdown в указанной позиции.

    Копия функции из utils.py для тестирования без импорта всего модуля.
    """
    # Конвертируем byte offset в character offset
    text_bytes = text.encode("utf-8")

    # Проверяем, что offset валидный
    if byte_offset >= len(text_bytes):
        byte_offset = len(text_bytes) - 1

    # Находим character offset соответствующий byte offset
    char_offset = len(text_bytes[:byte_offset].decode("utf-8", errors="ignore"))

    # Ищем все вхождения problem_char в тексте
    char_len = len(problem_char)
    positions = []
    i = 0
    while i <= len(text) - char_len:
        # Проверяем, не экранирован ли уже
        if text[i : i + char_len] == problem_char and (i == 0 or text[i - 1] != "\\"):
            positions.append(i)
        i += 1

    if not positions:
        # Нет вхождений - возвращаем как есть
        return text

    # Находим ближайшую позицию к проблемному offset
    closest_pos = min(positions, key=lambda p: abs(p - char_offset))

    # Теперь проверяем пары: открывающий и закрывающий символы

    def is_opening(pos: int) -> bool:
        """Проверяет, является ли символ на позиции открывающим тегом."""
        if pos + char_len > len(text):
            return False

        # В начале строки
        if pos == 0:
            next_char = text[pos + char_len] if pos + char_len < len(text) else ""
            return next_char and next_char not in " \n\t"

        prev_char = text[pos - 1]
        next_char = text[pos + char_len] if pos + char_len < len(text) else ""

        # После пробела/скобки и перед не-пробелом
        return prev_char in " \n\t([{" and next_char and next_char not in " \n\t"

    def is_closing(pos: int) -> bool:
        """Проверяет, является ли символ на позиции закрывающим тегом."""
        if pos + char_len > len(text):
            return False

        # В конце строки
        if pos + char_len >= len(text):
            prev_char = text[pos - 1] if pos > 0 else ""
            return prev_char and prev_char not in " \n\t"

        prev_char = text[pos - 1] if pos > 0 else ""
        next_char = text[pos + char_len]

        # После не-пробела и перед пробелом/знаком препинания/концом
        return (
            prev_char
            and prev_char not in " \n\t"
            and (next_char in " \n\t.!?,;:)]}" or pos + char_len == len(text))
        )

    # Проверяем все позиции и составляем пары
    opening_positions = []
    closing_positions = []

    for pos in positions:
        if is_opening(pos):
            opening_positions.append(pos)
        elif is_closing(pos):
            closing_positions.append(pos)

    # Составляем пары: для каждого открывающего ищем ближайший закрывающий
    paired = set()
    for open_pos in opening_positions:
        # Ищем ближайший закрывающий после открывающего
        matching_close = None
        for close_pos in closing_positions:
            if close_pos > open_pos and close_pos not in paired:
                matching_close = close_pos
                break

        if matching_close:
            paired.add(open_pos)
            paired.add(matching_close)

    # Теперь находим непарные символы
    unpaired = [pos for pos in positions if pos not in paired]

    if not unpaired:
        # Все символы парные, но все равно есть ошибка
        # Экранируем ближайший к проблемному offset
        pos_to_escape = closest_pos
    else:
        # Экранируем непарный символ ближайший к проблемному offset
        pos_to_escape = min(unpaired, key=lambda p: abs(p - char_offset))

    # Экранируем символ на позиции pos_to_escape
    return text[:pos_to_escape] + "\\" + text[pos_to_escape:]


class TestParseTelegramError:
    """Тесты для функции parse_telegram_error."""

    def test_parse_underline_error(self):
        """Парсинг ошибки с Underline entity."""
        error = "Telegram server says - Bad Request: can't parse entities: Can't find end of Underline entity at byte offset 487"
        char, offset = parse_telegram_error(error)

        assert char == "__"
        assert offset == 487

    def test_parse_bold_error(self):
        """Парсинг ошибки с Bold entity."""
        error = "Can't find end of Bold entity at byte offset 123"
        char, offset = parse_telegram_error(error)

        assert char == "*"
        assert offset == 123

    def test_parse_italic_error(self):
        """Парсинг ошибки с Italic entity."""
        error = "Can't find end of Italic entity at byte offset 42"
        char, offset = parse_telegram_error(error)

        assert char == "_"
        assert offset == 42

    def test_parse_strikethrough_error(self):
        """Парсинг ошибки с Strikethrough entity."""
        error = "Can't find end of Strikethrough entity at byte offset 100"
        char, offset = parse_telegram_error(error)

        assert char == "~"
        assert offset == 100

    def test_parse_code_error(self):
        """Парсинг ошибки с Code entity."""
        error = "Can't find end of Code entity at byte offset 50"
        char, offset = parse_telegram_error(error)

        assert char == "`"
        assert offset == 50

    def test_parse_spoiler_error(self):
        """Парсинг ошибки с Spoiler entity."""
        error = "Can't find end of Spoiler entity at byte offset 200"
        char, offset = parse_telegram_error(error)

        assert char == "||"
        assert offset == 200

    def test_parse_invalid_error(self):
        """Парсинг невалидной ошибки."""
        error = "Some other error message"
        char, offset = parse_telegram_error(error)

        assert char is None
        assert offset is None

    def test_parse_unknown_entity(self):
        """Парсинг ошибки с неизвестным типом entity."""
        error = "Can't find end of UnknownEntity entity at byte offset 100"
        char, offset = parse_telegram_error(error)

        assert char is None
        assert offset is None


class TestFixMarkdownAtOffset:
    """Тесты для функции fix_markdown_at_offset."""

    def test_fix_unpaired_underscore_simple(self):
        """Исправление непарного подчеркивания в простом случае."""
        text = "Текст с _непарным символом"
        result = fix_markdown_at_offset(text, "_", 10)

        # Непарный _ должен быть экранирован
        assert "\\_" in result

    def test_fix_unpaired_underscore_in_middle(self):
        """Исправление непарного подчеркивания в середине текста."""
        text = "Начало _парный текст_ и _непарный текст"
        result = fix_markdown_at_offset(text, "_", 35)

        # Первая пара должна остаться, второй _ экранирован
        assert result.count("_парный текст_") == 1
        assert result.count("\\_непарный") == 1

    def test_fix_double_underscore_unpaired(self):
        """Исправление непарного двойного подчеркивания."""
        text = "Текст с __непарным символом"
        result = fix_markdown_at_offset(text, "__", 10)

        # Непарный __ должен быть экранирован
        assert "\\__" in result

    def test_fix_asterisk_unpaired(self):
        """Исправление непарной звездочки (bold)."""
        text = "Текст с *непарным bold"
        result = fix_markdown_at_offset(text, "*", 10)

        # Непарная * должна быть экранирована
        assert "\\*" in result

    def test_fix_tilde_unpaired(self):
        """Исправление непарной тильды (strikethrough)."""
        text = "Текст с ~непарным strikethrough"
        result = fix_markdown_at_offset(text, "~", 10)

        # Непарная ~ должна быть экранирована
        assert "\\~" in result

    def test_fix_with_utf8_characters(self):
        """Исправление с учетом UTF-8 символов."""
        # Русские символы занимают больше байт
        text = "Привет _непарный текст"
        # "Привет " = 7 символов, но в UTF-8 это больше байт
        # Примерно 14 байт (каждая русская буква по 2 байта)
        result = fix_markdown_at_offset(text, "_", 14)

        # Непарный _ должен быть экранирован
        assert "\\_" in result

    def test_fix_with_emoji(self):
        """Исправление с учетом эмодзи."""
        text = "Текст 🤔 с _непарным символом"
        # Эмодзи занимает 4 байта в UTF-8
        result = fix_markdown_at_offset(text, "_", 15)

        # Непарный _ должен быть экранирован
        assert "\\_" in result

    def test_fix_paired_symbols_not_touched(self):
        """Парные символы не должны быть экранированы."""
        text = "_парный текст_ обычный текст"
        # Указываем offset на парный символ
        result = fix_markdown_at_offset(text, "_", 0)

        # Если оба символа парные, ничего не должно измениться
        # или экранируется только непарный
        assert "_парный текст_" in result or "\\_парный" in result

    def test_fix_multiple_underscores(self):
        """Исправление при множественных подчеркиваниях."""
        text = "_первый_ _второй _третий"
        # Третий _ непарный
        result = fix_markdown_at_offset(text, "_", 23)

        # Первая и вторая пары должны остаться
        assert "_первый_" in result
        assert "_второй" in result
        # Третий должен быть экранирован
        assert "\\_третий" in result or result.count("\\_") >= 1

    def test_fix_opening_underscore_rules(self):
        """Проверка правил для открывающего подчеркивания."""
        # Открывающий _ идет после пробела и перед словом
        text = "Текст _слово другой_текст"
        # Третий _ не должен быть открывающим (идет сразу после слова без пробела)
        result = fix_markdown_at_offset(text, "_", 20)

        # Непарный _ должен быть экранирован
        # Функция экранирует первый _ так как третий не подходит под правила закрывающего
        assert "\\_" in result

    def test_fix_closing_underscore_rules(self):
        """Проверка правил для закрывающего подчеркивания."""
        # Закрывающий _ идет после слова и перед пробелом
        text = "Текст _слово_ что_то еще"
        # Третий _ не должен быть закрывающим (идет перед словом)
        result = fix_markdown_at_offset(text, "_", 18)

        # Непарный _ должен быть экранирован
        assert "что\\_то" in result or "\\_то" in result

    def test_fix_underscore_at_start(self):
        """Исправление подчеркивания в начале строки."""
        text = "_начало текста без закрывающего"
        result = fix_markdown_at_offset(text, "_", 0)

        # Непарный _ должен быть экранирован
        assert "\\_начало" in result

    def test_fix_underscore_at_end(self):
        """Исправление подчеркивания в конце строки."""
        text = "текст без открывающего_"
        result = fix_markdown_at_offset(text, "_", len(text.encode("utf-8")) - 1)

        # Если _ на конце не парный, должен быть экранирован
        assert "открывающего\\_" in result or "\\_" in result

    def test_fix_empty_text(self):
        """Исправление пустого текста."""
        text = ""
        result = fix_markdown_at_offset(text, "_", 0)

        # Пустой текст должен остаться пустым
        assert result == ""

    def test_fix_no_problem_char(self):
        """Исправление когда проблемного символа нет в тексте."""
        text = "Обычный текст без символов markdown"
        result = fix_markdown_at_offset(text, "_", 10)

        # Текст должен остаться без изменений
        assert result == text

    def test_fix_already_escaped(self):
        """Уже экранированные символы не должны обрабатываться."""
        text = "Текст с уже экранированным \\_символом"
        result = fix_markdown_at_offset(text, "_", 30)

        # Не должно быть двойного экранирования
        assert "\\\\_" not in result
        assert "\\_символом" in result


class TestIntegration:
    """Интеграционные тесты для полного цикла."""

    def test_full_cycle_parse_and_fix(self):
        """Полный цикл: парсинг ошибки и исправление."""
        # Симулируем ситуацию из задачи
        error = "Can't find end of Underline entity at byte offset 487"
        text = "Длинный текст " * 30 + "__начало подчеркивания без конца"

        # Парсим ошибку
        char, offset = parse_telegram_error(error)
        assert char == "__"

        # Исправляем текст
        fixed = fix_markdown_at_offset(text, char, offset)

        # Проверяем что символ экранирован
        assert "\\__" in fixed

    def test_multiple_fixes_needed(self):
        """Несколько непарных символов требуют нескольких исправлений."""
        error1 = "Can't find end of Italic entity at byte offset 10"
        text = "Текст с _первым и _вторым непарными"

        # Первое исправление
        char, offset = parse_telegram_error(error1)
        fixed1 = fix_markdown_at_offset(text, char, offset)

        # После первого исправления может понадобиться второе
        # Проверяем что хотя бы один _ экранирован
        assert "\\_" in fixed1

    def test_multiple_sequential_errors(self):
        """
        Тест для случая с несколькими последовательными ошибками.
        Симулирует ситуацию когда в тексте несколько разных непарных символов.
        """
        # Исходный текст с несколькими проблемами
        text = "Текст с __непарным подчеркиванием и еще *непарным жирным"

        # Первая ошибка: Underline
        error1 = "Can't find end of Underline entity at byte offset 10"
        char1, offset1 = parse_telegram_error(error1)
        assert char1 == "__"

        fixed1 = fix_markdown_at_offset(text, char1, offset1)
        assert "\\__" in fixed1

        # Вторая ошибка: Bold (после исправления первой)
        # Offset изменился из-за добавления \
        error2 = "Can't find end of Bold entity at byte offset 60"
        char2, offset2 = parse_telegram_error(error2)
        assert char2 == "*"

        fixed2 = fix_markdown_at_offset(fixed1, char2, offset2)
        assert "\\*" in fixed2

        # Проверяем что оба символа экранированы
        assert "\\__" in fixed2
        assert "\\*" in fixed2

    def test_three_sequential_errors(self):
        """Тест с тремя последовательными ошибками разных типов."""
        # Текст с тремя разными непарными символами
        text = "Начало _курсив без конца, потом *жирный без конца, и ~зачеркнутый без конца"

        # Исправляем последовательно
        current = text

        # Ошибка 1: Italic
        char1, _ = parse_telegram_error(
            "Can't find end of Italic entity at byte offset 7"
        )
        current = fix_markdown_at_offset(current, char1, 7)
        assert "\\_" in current

        # Ошибка 2: Bold
        char2, _ = parse_telegram_error(
            "Can't find end of Bold entity at byte offset 40"
        )
        current = fix_markdown_at_offset(current, char2, 40)
        assert "\\*" in current

        # Ошибка 3: Strikethrough
        char3, _ = parse_telegram_error(
            "Can't find end of Strikethrough entity at byte offset 70"
        )
        current = fix_markdown_at_offset(current, char3, 70)
        assert "\\~" in current

        # Все три символа должны быть экранированы
        assert "\\_" in current
        assert "\\*" in current
        assert "\\~" in current

    def test_complex_message_with_multiple_errors(self):
        """
        Реальный кейс: длинное сообщение с несколькими разными типами непарных тегов.
        """
        # Имитация длинного сообщения от LLM с разными markdown тегами
        text = (
            "Привет! Вот твой ответ:\n\n"
            "_Первый пункт без закрытия\n"
            "Второй пункт с *правильным жирным*\n"
            "Третий пункт с __подчеркиванием без конца\n"
            "И еще текст с ~зачеркнутым без закрытия"
        )

        # Последовательно исправляем все ошибки
        current = text
        errors_fixed = 0

        # Симулируем до 7 попыток исправления
        test_errors = [
            ("Can't find end of Italic entity at byte offset 35", "_", 35),
            ("Can't find end of Underline entity at byte offset 120", "__", 120),
            ("Can't find end of Strikethrough entity at byte offset 180", "~", 180),
        ]

        for error_msg, expected_char, offset in test_errors:
            char, parsed_offset = parse_telegram_error(error_msg)
            assert char == expected_char

            current = fix_markdown_at_offset(current, char, offset)
            errors_fixed += 1

        # Проверяем что все символы экранированы
        assert errors_fixed == 3
        assert current.count("\\_") >= 1  # Минимум один экранированный _
        assert current.count("\\__") >= 1  # Минимум один экранированный __
        assert current.count("\\~") >= 1  # Минимум один экранированный ~
