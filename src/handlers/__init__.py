from handlers import birthday, guild_manager, user_manager, game_info, resin_cap, daily_checkin

all_handlers = [
    # Commands
    birthday.BirthdayHandler,
    game_info.GameInfoHandler,
    guild_manager.GuildSettingManager,
    user_manager.UserManager,

    # Tasks
    resin_cap.ResinCapReminder,
    daily_checkin.HoyolabDailyCheckin,
]
