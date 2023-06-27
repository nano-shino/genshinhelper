from handlers import (
    birthday,
    guild_manager,
    user_manager,
    game_info,
    notes_monitor,
    daily_checkin,
    mora_runs,
    redeem_codes,
    farm_route,
    bot_manager,
    genshin_events,
    genshin_codes,
    role_manager,
    emotes,
    spiral_abyss,
    remind,
)

all_handlers = [
    # Commands
    birthday.BirthdayHandler,
    game_info.GameInfoHandler,
    guild_manager.GuildSettingManager,
    user_manager.UserManager,
    mora_runs.MoraRunHandler,
    redeem_codes.RedeemCodes,
    farm_route.FarmRouteHandler,
    bot_manager.BotCommandHandler,
    role_manager.RoleManager,
    emotes.EmoteHandler,
    spiral_abyss.SpiralAbyssHandler,
    remind.RemindHandler,

    # Tasks
    notes_monitor.RealTimeNotesMonitor,
    daily_checkin.HoyolabDailyCheckin,
    genshin_events.GenshinEventScanner,
    genshin_codes.GenshinCodeScanner,
]

# Optional
try:
    import pixivpy3
    from optional.pixiv import daily_best_feed
    all_handlers.append(daily_best_feed.DailyBestIllustFeed)
except ModuleNotFoundError:
    pass

# Adding a command (implemented with application command) to this list will also enable a prefix version of it
prefix_commands = [(game_info.GameInfoHandler, ["resin"])]
