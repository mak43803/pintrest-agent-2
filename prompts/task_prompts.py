"""
Task Prompts - Task-specific instruction templates.

Templates for different Pinterest operations that are injected
into the prompt when the agent needs to perform specific tasks.
"""

SEARCH_PINS_PROMPT = """
Task: Search Pinterest for pins matching the query: "{query}"
Instructions:
1. Navigate to Pinterest search
2. Enter the search query
3. Wait for results to load
4. Extract pin data (title, image URL, link, engagement metrics)
5. Return the top {limit} results
""".strip()

SAVE_PIN_PROMPT = """
Task: Save a pin to a board.
Pin URL: {pin_url}
Target Board: {board_name}
Instructions:
1. Navigate to the pin URL
2. Click the Save button
3. Select the target board "{board_name}"
4. Confirm the save action
5. Verify the pin was saved successfully
""".strip()

CREATE_BOARD_PROMPT = """
Task: Create a new Pinterest board.
Board Name: {board_name}
Description: {description}
Instructions:
1. Navigate to your profile
2. Click "Create Board"
3. Enter the board name "{board_name}"
4. Enter the description
5. Set visibility to {visibility}
6. Confirm creation
""".strip()
