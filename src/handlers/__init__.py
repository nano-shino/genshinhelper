from handlers import birthday, guild_manager, user_manager, game_info

all_handlers = [
    birthday.BirthdayHandler,
    game_info.GameInfoHandler,
    guild_manager.GuildSettingManager,
    user_manager.UserManager,
]
