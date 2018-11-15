import json
import logging as log

import sys
import datetime



from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode


import MainController
import GamesController
from Constants.Config import STATS, SPECTATORS_GROUP
from Boardgamebox.Board import Board
from Boardgamebox.Game import Game
from Boardgamebox.Player import Player
from Constants.Config import ADMIN
from Persistence.Ranking import Ranking

# Enable logging
log.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                level=log.INFO,
                filename='logs/logging.log')

logger = log.getLogger(__name__)

commands = [  # command description used in the "help" command
    '/calltovote - Calls the players to vote',
    '/spectate - See as a spectator the real actions and roles (messages recieved in admin chat only and if you are not part of the game)',
    '/help - Gives you information about the available commands',
    '/start - Gives you a short piece of information about Secret Hitler',
    '/symbols - Shows you all possible symbols of the board',
    '/rules - Gives you a link to the official Secret Hitler rules',
    '/newgame - Creates a new game',
    '/join - Joins an existing game',
    '/startgame - Starts an existing game when all players have joined',
    '/startrebalanced - Starts an existing game in rebalanced mode, when all players have joined',
    '/cancelgame - Cancels an existing game. All data of the game will be lost',
    '/board - Prints the current board with fascist and liberals tracks, presidential order and election counter',
    '/votes - Prints who voted',
    '/retry - Execute again one of the last 3 game actions, resetting the board to that action\'s state. Use only for game blocking issues',
    '/stats - Show received and played policies as claimed by players',
    '/ranking - Show the top 5 players in the group'
]

symbols = [
    u"\u25FB\uFE0F" + ' Empty field without special power',
    u"\u2716\uFE0F" + ' Field covered with a card',  # X
    u"\U0001F52E" + ' Presidential Power: Policy Peek',  # crystal
    u"\U0001F50E" + ' Presidential Power: Investigate Loyalty',  # inspection glass
    u"\U0001F5E1" + ' Presidential Power: Execution',  # knife
    u"\U0001F454" + ' Presidential Power: Call Special Election',  # tie
    u"\U0001F54A" + ' Liberals win',  # dove
    u"\u2620" + ' Fascists win'  # skull
]


def command_symbols(bot, update):
    cid = update.message.chat_id
    symbol_text = "The following symbols can appear on the board: \n"
    for i in symbols:
        symbol_text += i + "\n"
    bot.send_message(cid, symbol_text)


def command_board(bot, update):
    cid = update.message.chat_id
    if cid in GamesController.games.keys():
        if GamesController.games[cid].board:
            bot.send_message(cid, GamesController.games[cid].board.print_board())
        else:
            bot.send_message(cid, "There is no running game in this chat. Please start the game with /startgame or /startrebalanced")
    else:
        bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")


def command_start(bot, update):
    cid = update.message.chat_id
    bot.send_message(cid,
                     "\"Secret Hitler is a social deduction game for 5-10 people about finding and stopping the Secret Hitler."
                     " The majority of players are liberals. If they can learn to trust each other, they have enough "
                     "votes to control the table and win the game. But some players are fascists. They will say whatever "
                     "it takes to get elected, enact their agenda, and blame others for the fallout. The liberals must "
                     "work together to discover the truth before the fascists install their cold-blooded leader and win "
                     "the game.\"\n- official description of Secret Hitler\n\nAdd me to a group and type /newgame to create a game!")
    command_help(bot, update)


def command_rules(bot, update):
    cid = update.message.chat_id
    btn = [[InlineKeyboardButton("Rules", url="http://www.secrethitler.com/assets/Secret_Hitler_Rules.pdf")]]
    rulesMarkup = InlineKeyboardMarkup(btn)
    bot.send_message(cid, "Read the official Secret Hitler rules:", reply_markup=rulesMarkup)


# pings the bot
def command_ping(bot, update):
    cid = update.message.chat_id
    log.info('ping called from ' + str(cid))
    bot.send_message(cid, 'pong - The Punisher')


# prints statistics, only ADMIN
def command_admin_stats(bot, update):
    cid = update.message.chat_id
    if cid == ADMIN:
        with open(STATS, 'r') as f:
            stats = json.load(f)
        stattext = "+++ Statistics +++\n" + \
                    "Liberal Wins (policies): " + str(stats.get("libwin_policies")) + "\n" + \
                    "Liberal Wins (killed Hitler): " + str(stats.get("libwin_kill")) + "\n" + \
                    "Fascist Wins (policies): " + str(stats.get("fascwin_policies")) + "\n" + \
                    "Fascist Wins (Hitler chancellor): " + str(stats.get("fascwin_hitler")) + "\n" + \
                    "Games cancelled: " + str(stats.get("cancelled")) + "\n\n" + \
                    "Total amount of groups: " + str(len(stats.get("groups"))) + "\n" + \
                    "Games running right now: "
        bot.send_message(cid, stattext)


# help page
def command_help(bot, update):
    cid = update.message.chat_id
    help_text = "The following commands are available:\n"
    for i in commands:
        help_text += i + "\n"
    bot.send_message(cid, help_text)


def command_newgame(bot, update):
    cid = update.message.chat_id
    game = GamesController.games.get(cid, None)
    groupType = update.message.chat.type
    if groupType not in ['group', 'supergroup']:
        bot.send_message(cid, "You have to add me to a group first and type /newgame there!")
    elif game:
        bot.send_message(cid, "There is currently a game running. If you want to end it please type /cancelgame!")
    else:
        GamesController.games[cid] = Game(cid, update.message.from_user.id)
        with open(STATS, 'r') as f:
            stats = json.load(f)
        if cid not in stats.get("groups"):
            stats.get("groups").append(cid)
            with open(STATS, 'w') as f:
                json.dump(stats, f)
        bot.send_message(cid, "New game created! Each player has to /join the game.\nThe initiator of this game (or the admin) can /join too and type /startgame or /startrebalanced when everyone has joined the game!")


def command_join(bot, update):
    groupName = update.message.chat.title
    cid = update.message.chat_id
    groupType = update.message.chat.type
    game = GamesController.games.get(cid, None)
    fname = update.message.from_user.first_name

    if groupType not in ['group', 'supergroup']:
        bot.send_message(cid, "You have to add me to a group first and type /newgame there!")
    elif not game:
        bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")
    elif game.board:
        bot.send_message(cid, "The game has started. Please wait for the next game!")
    elif update.message.from_user.id in game.playerlist:
        bot.send_message(game.cid, "You already joined the game, %s!" % fname)
    elif len(game.playerlist) >= 10:
        bot.send_message(game.cid, "You have reached the maximum amount of players. Please start the game with /startgame or /startrebalanced!")
    else:
        uid = update.message.from_user.id
        player = Player(fname, uid)
        try:
            bot.send_message(uid, "You joined a game in %s. I will soon tell you your secret role." % groupName)
            game.add_player(uid, player)
        except Exception:
            bot.send_message(game.cid,
                             fname + ", I can\'t send you a private message. Please go to @secrectfascistbr_bot and click \"Start\".\nYou then need to send /join again.")
        else:
            log.info("%s (%d) joined a game in %d" % (fname, uid, game.cid))
            try:
                bot.kick_chat_member(SPECTATORS_GROUP, uid, 30)
            except:
                log.error("Unable to ban user " + fname + ", " + sys.exc_info()[0])
                bot.send_message(SPECTATORS_GROUP, "%s, you joined a game but I couldn't kick you from the spectators group. "
                                                   "Please leave the chat to prevent cheating" % fname)
            if len(game.playerlist) > 4:
                bot.send_message(game.cid, fname + " has joined the game. Type /startgame or /startrebalanced if this was the last player and you want to start with %d players!" % len(game.playerlist))
            elif len(game.playerlist) == 1:
                bot.send_message(game.cid, "%s has joined the game. There is currently %d player in the game and you need 5-10 players." % (fname, len(game.playerlist)))
            else:
                bot.send_message(game.cid, "%s has joined the game. There are currently %d players in the game and you need 5-10 players." % (fname, len(game.playerlist)))


def command_startgame(bot, update, rebalance=False):
    log.info('command_startgame called')
    log.info(bot)
    log.info(update)
    cid = update.message.chat_id
    game = GamesController.games.get(cid, None)
    if not game:
        bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")
    elif game.board:
        bot.send_message(cid, "The game is already running!")
    elif update.message.from_user.id != game.initiator and bot.getChatMember(cid, update.message.from_user.id).status not in ("administrator", "creator"):
        bot.send_message(game.cid, "Only the initiator of the game or a group admin can start the game with /startgame or /startrebalanced")
    elif len(game.playerlist) < 5:
        bot.send_message(game.cid, "There are not enough players (min. 5, max. 10). Join the game with /join")
    else:
        player_number = len(game.playerlist)
        MainController.inform_players(bot, game, game.cid, player_number)
        MainController.inform_fascists(bot, game, player_number)
        if rebalance and len(game.playerlist) == 6:
            bot.send_message(cid,
                             "Game started in rebalanced mode. One F will be played at the start to help the poor helpless fascists.")
            game.board = Board(player_number, game)
            game.board.state.player_claims.append(['F elected at start of game'])
            game.board.state.fascist_track += 1
        elif rebalance and len(game.playerlist) in [7, 9]:
            removeF = 1 if len(game.playerlist) == 7 else 2
            label = "policy" if removeF == 1 else "policies"
            bot.send_message(cid,
                             "Game started in rebalanced mode. %d F %s will be removed from the deck for this game, so the liberals at least have a chancce now."
                             % (removeF, label))
            game.board = Board(player_number, game, removeF)
            game.board.state.player_claims.append(["%d F %s removed from deck" % (removeF, label)])
        else:
            game.board = Board(player_number, game)
        log.info(game.board)
        log.info("len(games) Command_startgame: " + str(len(GamesController.games)))
        game.shuffle_player_sequence()
        game.board.state.player_counter = 0
        bot.send_message(game.cid, game.board.print_board())
        #group_name = update.message.chat.title
        #bot.send_message(ADMIN, "Game of Secret Hitler started in group %s (%d)" % (group_name, cid))
        MainController.start_round(bot, game)


def command_startgame_rebalanced(bot, update):
    command_startgame(bot, update, True)


def command_cancelgame(bot, update):
    log.info('command_cancelgame called')
    cid = update.message.chat_id
    if cid in GamesController.games.keys():
        game = GamesController.games[cid]
        status = bot.getChatMember(cid, update.message.from_user.id).status
        if update.message.from_user.id == game.initiator or status in ("administrator", "creator"):
            MainController.end_game(bot, game, 99)
        else:
            bot.send_message(cid, "Only the initiator of the game or a group admin can cancel the game with /cancelgame")
    else:
        bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")


def command_votes(bot, update):
    try:
        #Send message of executing command
        cid = update.message.chat_id
        #bot.send_message(cid, "Looking for history...")
        #Check if there is a current game
        if cid in GamesController.games.keys():
            game = GamesController.games.get(cid, None)
            if not game.dateinitvote:
                # If date of init vote is null, then the voting didnt start
                bot.send_message(cid, "The voting didn't start yet.")
            else:
                #If there is a time, compare it and send history of votes.
                start = game.dateinitvote
                stop = datetime.datetime.now()
                elapsed = stop - start
                if elapsed > datetime.timedelta(minutes=1):
                    history_text = "Vote history for President %s and Chancellor %s:\n\n" % (game.board.state.nominated_president.name, game.board.state.nominated_chancellor.name)
                    for player in game.player_sequence:
                        # If the player is in the last_votes (He voted), mark him as he registered a vote
                        if player.uid in game.board.state.last_votes:
                            history_text += "%s registered a vote.\n" % (game.playerlist[player.uid].name)
                        else:
                            history_text += "%s didn't register a vote.\n" % (game.playerlist[player.uid].name)
                    bot.send_message(cid, history_text)
                else:
                    bot.send_message(cid, "Five minutes must pass to see the votes")
        else:
            bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")
    except Exception as e:
        bot.send_message(cid, str(e))


def DEL_command_calltokill(bot, update):
    try:
        #Send message of executing command
        cid = update.message.chat_id
        #bot.send_message(cid, "Looking for history...")
        #Check if there is a current game
        if cid in GamesController.games.keys():
            game = GamesController.games.get(cid, None)
            if not game.dateinitvote:
                # If date of init vote is null, then the voting didnt start
                bot.send_message(cid, "The voting didn't start yet.")
            else:
                #If there is a time, compare it and send history of votes.
                start = game.dateinitvote
                stop = datetime.datetime.now()
                elapsed = stop - start
                if elapsed > datetime.timedelta(minutes=1):
                    # Only remember to vote to players that are still in the game
                    for player in game.player_sequence:
                        # If the player is not in last_votes send him reminder
                        if player.uid in game.board.state.last_votes:
                            MainController.choose_kill(bot, update, player.uid)
                else:
                    bot.send_message(cid, "10 minutes must pass to kill lazies")
        else:
            bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")
    except Exception as e:
        bot.send_message(cid, str(e))


def command_calltovote(bot, update):
    try:
        #Send message of executing command
        cid = update.message.chat_id
        #bot.send_message(cid, "Looking for history...")
        #Check if there is a current game
        if cid in GamesController.games.keys():
            game = GamesController.games.get(cid, None)
            if not game.dateinitvote:
                # If date of init vote is null, then the voting didnt start
                bot.send_message(cid, "The voting didn't start yet.")
            else:
                #If there is a time, compare it and send history of votes.
                start = game.dateinitvote
                stop = datetime.datetime.now()
                elapsed = stop - start
                if elapsed > datetime.timedelta(minutes=1):
                    # Only remember to vote to players that are still in the game
                    history_text = ""
                    for player in game.player_sequence:
                        # If the player is not in last_votes send him reminder
                        if player.uid not in game.board.state.last_votes:
                            history_text += "It's time to vote [%s](tg://user?id=%d).\n" % (game.playerlist[player.uid].name, player.uid)
                    bot.send_message(cid, text=history_text, parse_mode=ParseMode.MARKDOWN)
                else:
                    bot.send_message(cid, "Five minutes must pass to see call to vote")
        else:
            bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")
    except Exception as e:
        bot.send_message(cid, str(e))


def command_calltopunish(bot, update):
    log.info('command_calltopunish called')
    cid = update.message.chat_id
    if cid in GamesController.games.keys():
        game = GamesController.games.get(cid, None)
        if not game.dateinitvote:
            # If date of init vote is null, then the voting didnt start
            bot.send_message(cid, "The voting didn't start yet.")
        else:
            # If there is a time, compare it and start punishment voting
            start = game.dateinitvote
            stop = datetime.datetime.now()
            elapsed = stop - start
            if elapsed < datetime.timedelta(hours=1):
                bot.send_message(cid, "One hour must pass to punish inactive voters")
            elif game.board.state.punish_players:
                voters_text = "There's already a punish vote going.\n"
                # list the people that still need to vote for punishment to pass
                for p_uid in game.board.state.punish_players:
                    voters_text += "Votes for punishing %s:\n" % game.playerlist[p_uid].name
                    for uid in game.board.state.punish_players[p_uid]:
                        vote = game.board.state.punish_players[p_uid][uid]
                        if vote == "Ja" or vote == "Nein":
                            voters_text += "  %s registered a vote!\n" % game.playerlist[uid].name
                        else:
                            voters_text += "  %s didn't register a vote\n" % game.playerlist[uid].name
                bot.send_message(cid, voters_text)
            else:
                MainController.vote_punish(bot, game)
                bot.send_message(cid, "A vote to punish inactive voter(s) was initiated.")
    else:
        bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")


def command_retry(bot, update):
    log.info('command_retry called')
    cid = update.message.chat_id
    user = update.message.from_user
    if cid in GamesController.games.keys():
        game = GamesController.games[cid]
        if game.last_action['depth'] == 0:
            bot.send_message(game.cid,
                             "There was no repeatable action executed yet!")
        else:
            status = bot.getChatMember(cid, user.id).status
            if user.id == game.initiator or status in ("administrator", "creator"):
                bot.send_message(game.cid,
                                 ("Attempt to repeat one of the 3 last actions was initiated by %s. The game will be reset to that action's state, please wait.\n"
                                 "%s, please go to our private chat and choose an action to retry.") % (user.first_name, user.first_name))
                MainController.retry_last_command(bot, game, user.id)
            else:
                bot.send_message(cid, "Only the initiator of the game or a group admin can reset the game's last action with /retry")
    else:
        bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")


def command_ranking(bot, update):
    cid = update.message.chat_id
    bot.send_message(cid, text=Ranking().print_ranking(cid), parse_mode=ParseMode.MARKDOWN)


def command_stats(bot, update):
    log.info('command_stats called')
    cid = update.message.chat_id
    if cid in GamesController.games.keys():
        game = GamesController.games[cid]
        if len(game.board.state.player_claims) == 0:
            stats = 'No stats available'
        else:
            stats = "Players stats:"
            for claim in game.board.state.player_claims:
                if len(claim) >= 1:
                    stats += "\n" + " ".join(claim)
        bot.send_message(game.cid, stats)
    else:
        bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")


def command_spectate(bot, update):
    log.info('command_spectate called')
    cid = update.message.chat_id
    if cid in GamesController.games.keys():
        game = GamesController.games[cid]
        if game.board:
            uid = update.message.from_user.id
            fname = update.message.from_user.first_name
            if uid in game.playerlist and not game.playerlist[uid].is_dead:
                bot.send_message(cid, "No cheating, %s!" % fname)
            elif uid in game.spectators:
                bot.send_message(cid, "You're already a spectator, %s. Wait for new actions" % fname)
            else:
                bot.send_message(uid, MainController.join_spectate(game, uid))
        else:
            bot.send_message(cid, "There is no running game in this chat. Please start the game with /startgame or /startrebalanced")
    else:
        bot.send_message(cid, "There is no game in this chat. Create a new game with /newgame")


def command_heudon(bot, update):
    log.info('command_heudon called')
    cid = update.message.chat_id
    uid = update.message.from_user.id
    fname = update.message.from_user.first_name
    if uid != 575538231:
        bot.send_message(cid, "You all are playing like F\nI'm the only L in this game\nNein\nNein\nkoeskoskooeaskoskke")
