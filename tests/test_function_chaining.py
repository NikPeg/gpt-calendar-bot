"""
Тест для проверки цепочки вызовов функций (function chaining).
Проверяет, что LLM может делать несколько вызовов функций подряд.
"""

import json
from unittest.mock import patch

import pytest

from services.llm_service import _process_llm_response


@pytest.mark.asyncio
async def test_function_chaining_delete_event():
    """
    Тест цепочки вызовов: list_calendar_events -> delete_calendar_event.
    Симулирует удаление события "Обед" с правильным получением ID.
    """
    chat_id = 123456
    prompt = []
    functions = [
        {
            "name": "list_calendar_events",
            "description": "Получает список событий",
        },
        {
            "name": "delete_calendar_event",
            "description": "Удаляет событие",
        },
    ]

    # Первый ответ от LLM - вызов list_calendar_events
    first_response = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "list_calendar_events",
                    "arguments": json.dumps(
                        {
                            "max_results": 10,
                            "time_min": "2026-01-05T00:00:00Z",
                            "time_max": "2026-01-05T23:59:59Z",
                        }
                    ),
                },
            }
        ],
    }

    # Результат list_calendar_events - список событий с "Обед"
    list_events_result = """📅 Найдено событий: 2

1. Встреча с клиентом
   Время: 2026-01-05T10:00:00+03:00
   ID: abc123xyz

2. Обед
   Время: 2026-01-05T15:00:00+03:00
   ID: lunch_event_id_12345
"""

    # Второй ответ от LLM - вызов delete_calendar_event с правильным ID
    second_response = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_2",
                "type": "function",
                "function": {
                    "name": "delete_calendar_event",
                    "arguments": json.dumps({"event_id": "lunch_event_id_12345"}),
                },
            }
        ],
    }

    # Результат delete_calendar_event
    delete_event_result = (
        "✅ Событие удалено успешно!\n\nID: lunch_event_id_12345"
    )

    # Третий ответ от LLM - финальное сообщение пользователю
    final_response = {
        "role": "assistant",
        "content": "Отлично! Я удалил событие 'Обед' из вашего календаря на завтра.",
        "tool_calls": None,
    }

    # Мокаем execute_calendar_function
    with patch(
        "services.llm_service.execute_calendar_function"
    ) as mock_execute:
        # Настраиваем возвращаемые значения для разных вызовов
        mock_execute.side_effect = [list_events_result, delete_event_result]

        # Мокаем send_request_to_openrouter для возврата второго и третьего ответов
        with patch(
            "services.llm_service.send_request_to_openrouter"
        ) as mock_send:
            mock_send.side_effect = [second_response, final_response]

            # Вызываем функцию обработки
            result = await _process_llm_response(
                first_response, chat_id, prompt, functions, max_iterations=3
            )

            # Проверяем результат
            assert result is not None
            assert "Обед" in result
            assert "удалил" in result.lower()

            # Проверяем, что было 2 вызова функций
            assert mock_execute.call_count == 2

            # Проверяем первый вызов - list_calendar_events
            first_call = mock_execute.call_args_list[0]
            assert first_call[0][0] == "list_calendar_events"
            assert first_call[0][2] == chat_id

            # Проверяем второй вызов - delete_calendar_event с правильным ID
            second_call = mock_execute.call_args_list[1]
            assert second_call[0][0] == "delete_calendar_event"
            assert second_call[0][1]["event_id"] == "lunch_event_id_12345"
            assert second_call[0][2] == chat_id

            # Проверяем, что было 2 запроса к LLM после первоначального
            assert mock_send.call_count == 2


@pytest.mark.asyncio
async def test_function_chaining_max_iterations():
    """
    Тест проверяет, что цепочка вызовов ограничена max_iterations.
    """
    chat_id = 123456
    prompt = []
    functions = [{"name": "test_function", "description": "Test"}]

    # Ответ, который всегда возвращает tool_calls
    response_with_tool_calls = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "test_function",
                    "arguments": json.dumps({}),
                },
            }
        ],
    }

    with patch(
        "services.llm_service.execute_calendar_function"
    ) as mock_execute:
        mock_execute.return_value = "Test result"

        with patch(
            "services.llm_service.send_request_to_openrouter"
        ) as mock_send:
            # Всегда возвращаем ответ с tool_calls, чтобы создать бесконечный цикл
            mock_send.return_value = response_with_tool_calls

            # Вызываем с max_iterations=2
            await _process_llm_response(
                response_with_tool_calls,
                chat_id,
                prompt,
                functions,
                max_iterations=2,
            )

            # Должно остановиться после 2 итераций
            # Итерация 1: вызов функции из первого response + запрос к LLM
            # Итерация 2: вызов функции из второго response + запрос к LLM
            # Итого: 2 вызова функции
            assert mock_execute.call_count == 2
            assert mock_send.call_count == 2


@pytest.mark.asyncio
async def test_function_chaining_no_tool_calls():
    """
    Тест проверяет, что если LLM возвращает обычный ответ без tool_calls,
    цепочка прерывается корректно.
    """
    chat_id = 123456
    prompt = []
    functions = [{"name": "test_function", "description": "Test"}]

    # Первый ответ с tool_calls
    first_response = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "test_function",
                    "arguments": json.dumps({}),
                },
            }
        ],
    }

    # Второй ответ без tool_calls
    second_response = {
        "role": "assistant",
        "content": "Готово! Операция выполнена успешно.",
        "tool_calls": None,
    }

    with patch(
        "services.llm_service.execute_calendar_function"
    ) as mock_execute:
        mock_execute.return_value = "Test result"

        with patch(
            "services.llm_service.send_request_to_openrouter"
        ) as mock_send:
            mock_send.return_value = second_response

            result = await _process_llm_response(
                first_response, chat_id, prompt, functions, max_iterations=3
            )

            # Должно вернуть контент из второго ответа
            assert result == "Готово! Операция выполнена успешно."

            # Должен быть только 1 вызов функции
            assert mock_execute.call_count == 1

            # Должен быть только 1 запрос к LLM
            assert mock_send.call_count == 1


@pytest.mark.asyncio
async def test_function_chaining_triple_call():
    """
    Тест проверяет цепочку из 3 вызовов функций подряд.
    """
    chat_id = 123456
    prompt = []
    functions = [
        {"name": "func1", "description": "Function 1"},
        {"name": "func2", "description": "Function 2"},
        {"name": "func3", "description": "Function 3"},
    ]

    # Ответ 1: вызов func1
    response1 = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "func1", "arguments": "{}"},
            }
        ],
    }

    # Ответ 2: вызов func2
    response2 = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_2",
                "type": "function",
                "function": {"name": "func2", "arguments": "{}"},
            }
        ],
    }

    # Ответ 3: вызов func3
    response3 = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_3",
                "type": "function",
                "function": {"name": "func3", "arguments": "{}"},
            }
        ],
    }

    # Ответ 4: финальный текст
    response4 = {
        "role": "assistant",
        "content": "Все три функции выполнены!",
        "tool_calls": None,
    }

    with patch(
        "services.llm_service.execute_calendar_function"
    ) as mock_execute:
        mock_execute.side_effect = ["Result 1", "Result 2", "Result 3"]

        with patch(
            "services.llm_service.send_request_to_openrouter"
        ) as mock_send:
            mock_send.side_effect = [response2, response3, response4]

            result = await _process_llm_response(
                response1, chat_id, prompt, functions, max_iterations=5
            )

            assert result == "Все три функции выполнены!"
            assert mock_execute.call_count == 3
            assert mock_send.call_count == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

