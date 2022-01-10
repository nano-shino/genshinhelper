from handlers import birthday, guild_manager, user_manager, game_info, resin_cap, daily_checkin, parametric_transformer, \
    mora_runs, redeem_codes, farm_route, bot_manager, genshin_events, genshin_codes, role_manager, emotes

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

    # Tasks
    resin_cap.ResinCapReminder,
    daily_checkin.HoyolabDailyCheckin,
    parametric_transformer.ParametricTransformer,
    genshin_events.GenshinEventScanner,
    genshin_codes.GenshinCodeScanner,
]

# Adding a command (implemented with application command) to this list will also enable a prefix version of it
prefix_commands = [
    (game_info.GameInfoHandler, ['resin'])
]
