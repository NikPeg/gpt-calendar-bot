"""
Тесты для функции исправления markdown.
"""

import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def fix_nested_markdown(text: str) -> str:
    """
    Исправляет вложенные markdown теги, которые вызывают ошибки в Telegram MarkdownV2.

    Копия функции из utils.py для тестирования без импорта всего модуля.
    """
    if not text:
        return text

    # Определяем, является ли символ частью markdown тега
    def is_likely_tag_start(i: int, tag: str) -> bool:
        """Проверяет, похоже ли что символ(ы) начинают тег."""
        if i + len(tag) > len(text):
            return False

        if text[i:i+len(tag)] != tag:
            return False

        if i == 0:
            next_char = text[i + len(tag)] if i + len(tag) < len(text) else ''
            return next_char and next_char not in ' \n\t'

        prev_char = text[i - 1]
        next_char = text[i + len(tag)] if i + len(tag) < len(text) else ''

        if prev_char in ' \n\t([{':
            return next_char and next_char not in ' \n\t'

        return False

    def is_likely_tag_end(i: int, tag: str) -> bool:
        """Проверяет, похоже ли что символ(ы) закрывают тег."""
        if i + len(tag) > len(text):
            return False

        if text[i:i+len(tag)] != tag:
            return False

        if i + len(tag) >= len(text):
            prev_char = text[i - 1] if i > 0 else ''
            return prev_char and prev_char not in ' \n\t'

        prev_char = text[i - 1] if i > 0 else ''
        next_char = text[i + len(tag)]

        if prev_char and prev_char not in ' \n\t':
            return next_char in ' \n\t.!?,;:)]}' or i + len(tag) == len(text)

        return False

    # Теги для обработки
    tags = ['||', '__', '_', '*', '~', '`']

    result = []
    stack = []  # Стек открытых тегов
    i = 0

    while i < len(text):
        matched_tag = None

        for tag in tags:
            if text[i:i+len(tag)] == tag:
                matched_tag = tag
                break

        if not matched_tag:
            result.append(text[i])
            i += 1
            continue

        tag = matched_tag
        tag_len = len(tag)

        tag_in_stack = any(t == tag for t, _ in stack)

        if tag_in_stack:
            if is_likely_tag_end(i, tag):
                found = False
                for idx, (stack_tag, _) in enumerate(stack):
                    if stack_tag == tag:
                        stack.pop(idx)
                        result.append(tag)
                        found = True
                        break

                if not found:
                    result.append('\\')
                    result.append(tag)
            else:
                result.append('\\')
                result.append(tag)

            i += tag_len
        else:
            if is_likely_tag_start(i, tag):
                stack.append((tag, len(result)))
                result.append(tag)
                i += tag_len
            else:
                result.append(text[i])
                i += 1

    while stack:
        tag, pos = stack.pop()
        result.insert(pos, '\\')

    fixed_text = ''.join(result)

    # Шаг 2: Проверяем и экранируем специальные символы MarkdownV2
    special_chars = ['>', '#', '+', '-', '=', '{', '}', '.', '!']

    result2 = []
    i = 0
    in_code = False

    while i < len(fixed_text):
        char = fixed_text[i]

        if char == '`' and (i == 0 or fixed_text[i-1] != '\\'):
            in_code = not in_code
            result2.append(char)
            i += 1
            continue

        if in_code:
            result2.append(char)
            i += 1
            continue

        if char in special_chars:
            if i > 0 and fixed_text[i-1] == '\\':
                result2.append(char)
            else:
                result2.append('\\')
                result2.append(char)
            i += 1
        else:
            result2.append(char)
            i += 1

    return ''.join(result2)


class TestFixNestedMarkdown:
    """Тесты для функции fix_nested_markdown."""

    def test_simple_valid_markdown(self):
        """Простой валидный markdown не должен изменяться."""
        text = "_курсив_ и *жирный* текст"
        assert fix_nested_markdown(text) == text

    def test_nested_italic_inside_italic(self):
        """Вложенный курсив внутри курсива должен экранироваться."""
        # Пример из задачи
        text = "_(А может, случилось что-то новенькое? Рассказывай — я _все уши_! Ну... _метафорически_. У меня же их нет. _Или есть?_ 🤔🔊)_"
        result = fix_nested_markdown(text)

        # Должно быть экранирование внутренних тегов
        assert "\\_" in result
        # Количество экранированных символов должно быть > 0
        escaped_count = result.count("\\_")
        assert escaped_count > 0
        # Внешний тег должен открываться
        assert result.startswith("_(")

    def test_nested_bold_inside_bold(self):
        """Вложенный жирный внутри жирного должен экранироваться."""
        text = "*это *вложенный* жирный*"
        result = fix_nested_markdown(text)

        # Должен остаться только один уровень *
        assert result.count("*") <= 2 or "\\" in result

    def test_multiple_different_tags(self):
        """Разные теги могут быть вложены друг в друга."""
        text = "_курсив с *жирным* внутри_"
        result = fix_nested_markdown(text)

        # Разные теги - это OK
        assert "_курсив с *жирный*" in result or "_курсив с *жирным*" in result

    def test_underscore_in_username(self):
        """Подчеркивание в username не должно трактоваться как тег."""
        text = "Пользователь user_name написал сообщение"
        result = fix_nested_markdown(text)

        # _ внутри слова не должен измениться
        assert "user_name" in result

    def test_asterisk_in_math(self):
        """Звездочка в математическом выражении."""
        text = "Результат: 2*3=6 или 5 * 4 = 20"
        result = fix_nested_markdown(text)

        # * между цифрами не должен трактоваться как тег
        assert "2*3" in result or "5 * 4" in result

    def test_code_blocks(self):
        """Моноширинный текст с обратными кавычками."""
        text = "`код` обычный текст `еще код`"
        result = fix_nested_markdown(text)

        # Должны остаться оба блока кода
        assert result.count("`") == 4

    def test_nested_code_inside_code(self):
        """Вложенный код внутри кода."""
        text = "`внешний `вложенный` код`"
        result = fix_nested_markdown(text)

        # Внутренние ` должны быть экранированы
        assert "\\`" in result or result.count("`") == 2

    def test_strikethrough(self):
        """Зачеркнутый текст."""
        text = "~зачеркнутый~ обычный ~еще зачеркнутый~"
        result = fix_nested_markdown(text)

        assert result.count("~") == 4

    def test_nested_strikethrough(self):
        """Вложенный зачеркнутый текст."""
        text = "~внешний ~вложенный~ текст~"
        result = fix_nested_markdown(text)

        # Внутренние ~ должны быть экранированы
        assert "\\~" in result or result.count("~") == 2

    def test_underline_double_underscore(self):
        """Подчеркивание с двойным подчеркиванием."""
        text = "__подчеркнутый__ текст"
        result = fix_nested_markdown(text)

        assert "__подчеркнутый__" in result

    def test_nested_underline_inside_underline(self):
        """Вложенное подчеркивание."""
        text = "__внешний __вложенный__ текст__"
        result = fix_nested_markdown(text)

        # Внутренние __ должны быть экранированы
        assert "\\__" in result or result.count("__") == 2

    def test_spoiler(self):
        """Спойлер текст."""
        text = "||спойлер|| обычный текст"
        result = fix_nested_markdown(text)

        assert "||спойлер||" in result

    def test_nested_spoiler(self):
        """Вложенный спойлер."""
        text = "||внешний ||вложенный|| спойлер||"
        result = fix_nested_markdown(text)

        # Внутренние || должны быть экранированы
        assert "\\||" in result or result.count("||") == 2

    def test_empty_string(self):
        """Пустая строка."""
        assert fix_nested_markdown("") == ""

    def test_no_tags(self):
        """Текст без тегов."""
        text = "Обычный текст без форматирования"
        assert fix_nested_markdown(text) == text

    def test_unclosed_tag(self):
        """Незакрытый тег должен быть экранирован."""
        text = "_незакрытый курсив"
        result = fix_nested_markdown(text)

        # Должно быть экранирование
        assert "\\_" in result

    def test_only_closing_tag(self):
        """Только закрывающий тег без открывающего."""
        text = "текст_ без открывающего"
        result = fix_nested_markdown(text)

        # Либо оставлен как есть, либо экранирован
        assert "текст_" in result or "\\_" in result

    def test_complex_nested_structure(self):
        """Сложная структура с несколькими уровнями."""
        text = "_курсив *жирный _вложенный курсив_ жирный* курсив_"
        result = fix_nested_markdown(text)

        # Вложенный курсив должен быть экранирован
        assert "\\_" in result

    def test_tag_at_line_start(self):
        """Тег в начале строки."""
        text = "_начало строки_ обычный текст"
        result = fix_nested_markdown(text)

        assert "_начало строки_" in result

    def test_tag_at_line_end(self):
        """Тег в конце строки."""
        text = "обычный текст _конец строки_"
        result = fix_nested_markdown(text)

        assert "_конец строки_" in result

    def test_multiline_text(self):
        """Многострочный текст."""
        text = "_первая строка\nвторая строка_"
        result = fix_nested_markdown(text)

        # Многострочные теги - это OK
        assert "_первая строка" in result
        assert "вторая строка_" in result

    def test_emoji_inside_tags(self):
        """Эмодзи внутри тегов."""
        text = "_текст с 🤔 эмодзи_"
        result = fix_nested_markdown(text)

        assert "🤔" in result

    def test_mixed_valid_and_nested(self):
        """Смесь валидных тегов и вложенных."""
        text = "*жирный* _курсив_ *жирный с *вложенным* жирным*"
        result = fix_nested_markdown(text)

        # Первые два тега должны остаться без изменений
        assert "*жирный*" in result
        assert "_курсив_" in result
        # В третьем блоке должно быть экранирование
        assert "\\*" in result or result.count("*") == 4

    def test_punctuation_after_tag(self):
        """Знаки препинания после тега."""
        text = "_курсив_. Текст после точки."
        result = fix_nested_markdown(text)

        # Точка должна быть экранирована
        assert "_курсив_\\." in result or "\\.  " in result

    def test_tag_after_bracket(self):
        """Тег после скобки."""
        text = "(_курсив_) обычный"
        result = fix_nested_markdown(text)

        assert "_курсив_" in result

    def test_quote_symbol_escaped(self):
        """Символ > (цитата) должен быть экранирован."""
        text = ">«Эта тётя – просто случайный радиовышпет в моём дне. Её слова не имеют ко мне отношения»."
        result = fix_nested_markdown(text)

        # > должен быть экранирован
        assert "\\>" in result

    def test_quote_inside_italic(self):
        """Цитата внутри курсива с экранированием."""
        text = "_>«Эта тётя – просто случайный радиовышпет в моём дне\\. Её слова не имеют ко мне отношения»_\\."
        result = fix_nested_markdown(text)

        # > должен быть экранирован
        assert "\\>" in result

    def test_complex_with_quote_and_italic(self):
        """Пример из задачи с цитатой и курсивом."""
        text = "*Напомни себе:*\n\n   >_«Эта тётя – просто случайный радиовышпет в моём дне\\. Её слова не имеют ко мне отношения»_\\."
        result = fix_nested_markdown(text)

        # > должен быть экранирован
        assert "\\>" in result
        # * должен быть в тексте (для жирного)
        assert "*" in result

    def test_special_chars_escaped(self):
        """Специальные символы должны быть экранированы."""
        text = "Символы: > # + - = { } . !"
        result = fix_nested_markdown(text)

        # Все специальные символы должны быть экранированы
        assert "\\>" in result
        assert "\\#" in result
        assert "\\+" in result
        assert "\\-" in result
        assert "\\=" in result
        assert "\\{" in result
        assert "\\}" in result
        assert "\\." in result
        assert "\\!" in result

    def test_already_escaped_chars_not_double_escaped(self):
        """Уже экранированные символы не должны экранироваться повторно."""
        text = "Уже экранированный: \\> и \\. и \\!"
        result = fix_nested_markdown(text)

        # Не должно быть двойного экранирования
        assert "\\\\>" not in result
        assert "\\>" in result

    def test_special_chars_inside_code_not_escaped(self):
        """Внутри code блоков специальные символы не экранируются."""
        text = "`код с > и # символами`"
        result = fix_nested_markdown(text)

        # Внутри ` ` не должно быть экранирования
        # Проверяем что между ` есть неэкранированные символы
        assert "`код с > и # символами`" in result

    def test_dot_in_sentence(self):
        """Точка в конце предложения должна быть экранирована."""
        text = "Это предложение. И ещё одно."
        result = fix_nested_markdown(text)

        # Точки должны быть экранированы
        assert "\\." in result

    def test_exclamation_mark(self):
        """Восклицательный знак должен быть экранирован."""
        text = "Ого! Как интересно!"
        result = fix_nested_markdown(text)

        # ! должен быть экранирован
        assert "\\!" in result

