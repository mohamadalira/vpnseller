from aiogram.fsm.state import State, StatesGroup


class AdminState(StatesGroup):
    add_config_category = State()
    add_config_text = State()
    broadcast = State()

    add_plan_name = State()
    add_plan_price = State()

    edit_plan_name = State()
    edit_plan_price = State()

    price_change = State()

    card_number = State()
    card_holder = State()

    add_channel = State()
    delete_channel = State()

    add_admin = State()
    delete_admin = State()
    edit_message_text = State()
    wallet_adjust = State()
