#!/usr/bin/env python
# -*- coding: utf-8 -*-
__author__ = "Julian Schrittwieser"

import json
import logging as log
import random
import re
from random import randrange
from time import sleep
import sys

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import (Updater, CommandHandler, CallbackQueryHandler)

import Commands
from Constants.Cards import playerSets
from Constants.Config import TOKEN, STATS, LOGGING_PATH, SPECTATORS_JOIN_URL, SPECTATORS_GROUP
from Boardgamebox.Game import Game
from Boardgamebox.Player import Player
from Persistence.Ranking import Ranking
import GamesController

import datetime


class Dummy:
    pass


# Enable logging
log.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                level=log.INFO)

logger = log.getLogger(__name__)


def initialize_testdata():
    # Sample game for quicker tests
    groupid = -255761120
    testgame = Game(groupid, 490969284)
    GamesController.games[groupid] = testgame
    # Player("Arius", 592645156)
    players = [Player("Theoziran", 490969284),Player("Marco", 21478624),
               Player("Marian", 423826839),Player("Josafa", 590382102),Player("Marlies", 15176565)]
    for player in players:
        testgame.add_player(player.uid, player)


##
#
# Beginning of round
#
##

def start_round(bot, game):
    log.info('start_round called')
    if game.board.state.chosen_president is None:
        game.board.state.nominated_president = game.player_sequence[game.board.state.player_counter]
    else:
        game.board.state.nominated_president = game.board.state.chosen_president
        game.board.state.chosen_president = None

    message = "The next presidential canditate is %s.\n[%s](tg://user?id=%d), please nominate a Chancellor in our private chat!" % (
        game.board.state.nominated_president.name, game.board.state.nominated_president.name,
        game.board.state.nominated_president.uid)
    bot.send_message(game.cid, text=message, parse_mode=ParseMode.MARKDOWN)
    choose_chancellor(bot, game)
    # --> nominate_chosen_chancellor --> vote --> handle_voting --> count_votes --> voting_aftermath --> draw_policies
    # --> choose_policy --> pass_two_policies --> choose_policy --> enact_policy --> start_round


def choose_chancellor(bot, game):
    log.info('choose_chancellor called')
    game.store_last_action(choose_chancellor)
    strcid = str(game.cid)
    pres_uid = 0
    chan_uid = 0
    btns = []
    if game.board.state.president is not None:
        pres_uid = game.board.state.president.uid
    if game.board.state.chancellor is not None:
        chan_uid = game.board.state.chancellor.uid
    for uid in game.playerlist:
        # If there are only five players left in the
        # game, only the last elected Chancellor is
        # ineligible to be Chancellor Candidate; the
        # last President may be nominated.
        if len(game.player_sequence) > 5:
            if uid != game.board.state.nominated_president.uid and game.playerlist[
                uid].is_dead == False and uid != pres_uid and uid != chan_uid:
                name = game.playerlist[uid].name
                btns.append([InlineKeyboardButton(name, callback_data=strcid + "_chan_" + str(uid))])
        else:
            if uid != game.board.state.nominated_president.uid and game.playerlist[
                uid].is_dead == False and uid != chan_uid:
                name = game.playerlist[uid].name
                btns.append([InlineKeyboardButton(name, callback_data=strcid + "_chan_" + str(uid))])

    chancellorMarkup = InlineKeyboardMarkup(btns)
    bot.send_message(game.board.state.nominated_president.uid, game.board.print_board())
    bot.send_message(game.board.state.nominated_president.uid, 'Please nominate your chancellor!',
                     reply_markup=chancellorMarkup)


def nominate_chosen_chancellor(bot, update):
    log.info('nominate_chosen_chancellor called')
    log.info(GamesController.games.keys())
    callback = update.callback_query
    regex = re.search("(-[0-9]*)_chan_([0-9]*)", callback.data)
    cid = int(regex.group(1))
    chosen_uid = int(regex.group(2))
    try:
        game = GamesController.games.get(cid, None)
        log.info(game)
        log.info(game.board)
        game.board.state.nominated_chancellor = game.playerlist[chosen_uid]
        log.info("President %s (%d) nominated %s (%d)" % (
            game.board.state.nominated_president.name, game.board.state.nominated_president.uid,
            game.board.state.nominated_chancellor.name, game.board.state.nominated_chancellor.uid))
        bot.edit_message_text("You nominated %s as Chancellor!" % game.board.state.nominated_chancellor.name,
                              callback.from_user.id, callback.message.message_id)
        bot.send_message(game.cid,
                         "President %s nominated %s as Chancellor. Please vote now!" % (
                             game.board.state.nominated_president.name, game.board.state.nominated_chancellor.name))
        vote(bot, game)
    except AttributeError as e:
        log.error("nominate_chosen_chancellor: Game or board should not be None! Eror: " + str(e))
    except Exception as e:
        log.error("Unknown error: " + str(e))


def vote(bot, game):
    log.info('vote called')
    game.store_last_action(vote)
    # When voting starts we start the counter to see later with the vote/calltovote command we can see who voted.
    game.dateinitvote = datetime.datetime.now()
    strcid = str(game.cid)
    btns = [[InlineKeyboardButton("Ja", callback_data=strcid + "_Ja"),
             InlineKeyboardButton("Nein", callback_data=strcid + "_Nein")]]
    voteMarkup = InlineKeyboardMarkup(btns)
    for uid in game.playerlist:
        if not game.playerlist[uid].is_dead:
            if game.playerlist[uid] is not game.board.state.nominated_president:
                # the nominated president already got the board before nominating a chancellor
                bot.send_message(uid, game.board.print_board())
            message = bot.send_message(uid,
                             "Do you want to elect President %s and Chancellor %s?" % (
                                 game.board.state.nominated_president.name, game.board.state.nominated_chancellor.name),
                             reply_markup=voteMarkup)
            game.board.state.vote_message_ids[uid] = message.message_id


def handle_voting(bot, update):
    callback = update.callback_query
    log.info('handle_voting called: %s' % callback.data)
    regex = re.search("(-[0-9]*)_(.*)", callback.data)
    cid = int(regex.group(1))
    answer = regex.group(2)
    try:
        game = GamesController.games[cid]
        uid = callback.from_user.id
        bot.edit_message_text("Thank you for your vote: %s to a President %s and a Chancellor %s" % (
            answer, game.board.state.nominated_president.name, game.board.state.nominated_chancellor.name), uid,
                              callback.message.message_id)
        log.info("Player %s (%d) voted %s" % (callback.from_user.first_name, uid, answer))
        if uid in game.board.state.punish_players:
            del game.board.state.punish_players[uid]
        if uid not in game.board.state.last_votes:
            game.board.state.last_votes[uid] = answer
        if len(game.board.state.last_votes) == len(game.player_sequence):
            count_votes(bot, game)
    except:
        log.error("handle_voting: Game or board should not be None!")


def count_votes(bot, game):
    log.info('count_votes called')
    game.store_last_action(count_votes)
    # Voted Ended
    game.dateinitvote = None
    voting_text = ""
    voting_success = False
    for player in game.player_sequence:
        if game.board.state.last_votes[player.uid] == "Ja":
            voting_text += game.playerlist[player.uid].name + " voted Ja!\n"
        elif game.board.state.last_votes[player.uid] == "Nein":
            voting_text += game.playerlist[player.uid].name + " voted Nein!\n"
    if list(game.board.state.last_votes.values()).count("Ja") > (
        len(game.player_sequence) / 2):  # because player_sequence doesnt include dead
        # VOTING WAS SUCCESSFUL
        log.info("Voting successful")
        inform_spectators(bot, game, "President %s and Chancellor %s got elected" % (
            game.board.state.nominated_president.name, game.board.state.nominated_chancellor.name))
        voting_text += "Hail President [%s](tg://user?id=%d)! Hail Chancellor [%s](tg://user?id=%d)!" % (
            game.board.state.nominated_president.name, game.board.state.nominated_president.uid, game.board.state.nominated_chancellor.name, game.board.state.nominated_chancellor.uid)
        game.board.state.chancellor = game.board.state.nominated_chancellor
        game.board.state.president = game.board.state.nominated_president
        game.board.state.nominated_president = None
        game.board.state.nominated_chancellor = None
        voting_success = True
        game.board.state.player_claims.append(["%s+%s:" % (
            game.board.state.president.name, game.board.state.chancellor.name), "???", "??", "?"])
        bot.send_message(game.cid, text=voting_text, parse_mode=ParseMode.MARKDOWN)
        voting_aftermath(bot, game, voting_success)
    else:
        log.info("Voting failed")
        voting_text += "The people didn't like the two candidates!"
        game.board.state.nominated_president = None
        game.board.state.nominated_chancellor = None
        game.board.state.failed_votes += 1
        bot.send_message(game.cid, voting_text)
        if game.board.state.failed_votes == 3:
            do_anarchy(bot, game)
        else:
            voting_aftermath(bot, game, voting_success)


def voting_aftermath(bot, game, voting_success):
    log.info('voting_aftermath called')
    game.board.state.last_votes = {}
    if voting_success:
        if game.board.state.fascist_track >= 3 and game.board.state.chancellor.role == "Hitler":
            # fascists win, because Hitler was elected as chancellor after 3 fascist policies
            game.board.state.game_endcode = -2
            end_game(bot, game, game.board.state.game_endcode)
        elif game.board.state.fascist_track >= 3 and game.board.state.chancellor.role != "Hitler" and game.board.state.chancellor not in game.board.state.not_hitlers:
            game.board.state.not_hitlers.append(game.board.state.chancellor)
            draw_policies(bot, game)
        else:
            # voting was successful and Hitler was not nominated as chancellor after 3 fascist policies
            draw_policies(bot, game)
    else:
        bot.send_message(game.cid, game.board.print_board())
        start_next_round(bot, game)


def vote_punish(bot, game):
    log.info('vote_punish called')
    try:
        game.store_last_action(vote_punish)
        # Only players that have already voted can vote for punishment
        players_who_voted = []
        for player in game.player_sequence:
            if player.uid in game.board.state.last_votes:
                players_who_voted.append(player.uid)
            else:
                game.board.state.punish_players[player.uid] = {}
        strcid = str(game.cid)
        for uid in players_who_voted:
            for p_uid in game.board.state.punish_players:
                btns = [[InlineKeyboardButton("Ja", callback_data=strcid + "_" + str(p_uid) + "_Ja"),
                         InlineKeyboardButton("Nein", callback_data=strcid + "_" + str(p_uid) + "_Nein")]]
                voteMarkup = InlineKeyboardMarkup(btns)
                message = bot.send_message(uid,
                                 "Do you want to punish %s?" % game.playerlist[p_uid].name,
                                 reply_markup=voteMarkup)
                game.board.state.punish_players[p_uid][uid] = message.message_id
    except Exception as e:
        log.error("vote_punish error: " + str(e))


def handle_vote_punish(bot, update):
    callback = update.callback_query
    log.info('handle_vote_punish called: %s' % callback.data)
    regex = re.search("(-[0-9]*)_(.*)_(.*)", callback.data)
    cid = int(regex.group(1))
    p_uid = int(regex.group(2))
    answer = regex.group(3)
    try:
        game = GamesController.games[cid]
        uid = callback.from_user.id
        punish_player = game.playerlist[p_uid]
        if p_uid not in game.board.state.punish_players:
            bot.edit_message_text("Sorry, %s's punishment was canceled" % punish_player.name,
                                  uid, callback.message.message_id)
        else:
            bot.edit_message_text("Thank you for your vote '%s' to punish %s" % (answer, punish_player.name),
                                  uid, callback.message.message_id)
            log.info("Player %s (%d) voted for %s's punishment: %s" %
                     (callback.from_user.first_name, uid, punish_player.name, answer))
            game.board.state.punish_players[p_uid][uid] = answer
            count_punish_votes(bot, game, p_uid)
    except:
        log.error("handle_vote_punish: Game or board should not be None! " + str(e))


def count_punish_votes(bot, game, p_uid):
    log.info('count_punish_votes called')
    num_votes = {"Ja": 0, "Nein": 0}
    voting_text = ""
    try:
        for uid in game.board.state.punish_players[p_uid]:
            answer = game.board.state.punish_players[p_uid][uid]
            if answer == "Ja":
                num_votes["Ja"] += 1
            elif answer == "Nein":
                num_votes["Nein"] += 1
        if len(game.board.state.punish_players[p_uid]) == num_votes["Ja"] + num_votes["Nein"]:
            log.info("Punishment voting ended")
            del game.board.state.punish_players[p_uid]
            if num_votes["Ja"] > num_votes["Nein"]:
                voting_text += "The punishment for %s passed!\n" % game.playerlist[p_uid].name
                game.board.state.punish_history.append(p_uid)
                punish_number = game.board.state.punish_history.count(p_uid)
                if punish_number > 2:
                    voting_text += "Punishment: Death!\nThe presidency will be canceled! (does not count as failed)"
                    bot.send_message(game.cid, voting_text)
                    punished_player = game.playerlist[p_uid]
                    punished_player.is_dead = True
                    if game.player_sequence.index(punished_player) <= game.board.state.player_counter:
                        game.board.state.player_counter -= 1
                    game.player_sequence.remove(punished_player)
                    game.board.state.dead += 1
                    game.board.state.player_claims.append(
                        ["%s was killed as a punishment" % punished_player.name])
                    log.info("Player %s (%d) was killed as a punishment" % (
                        punished_player.name, punished_player.uid))
                    try:
                        bot.unban_chat_member(SPECTATORS_GROUP, p_uid)
                    except:
                        log.error("Unable to remove ban for user " + punished_player.name + ", " + sys.exc_info()[0])
                        bot.send_message(SPECTATORS_GROUP,
                                         "%s, couldn't be unbanned. "
                                         "Check with admin how to unban him so he can join spectator group" % punished_player.name)
                    if punished_player.role == "Hitler":
                        end_game(bot, game, 2)
                    else:
                        log.info("Presidency was canceled: punishment for AFK")
                        cancel_presidency(bot, game)
                elif punish_number == 2:
                    voting_text += "Punishment: random vote.\nNext punishment: Death!"
                    bot.send_message(game.cid, voting_text)
                    force_vote(bot, game, p_uid)
                elif punish_number == 1:
                    voting_text += "Punishment: random vote.\nNext punishment: random vote."
                    bot.send_message(game.cid, voting_text)
                    force_vote(bot, game, p_uid)
            else:
                voting_text += "No punishment for %s!" % game.playerlist[p_uid].name
                bot.send_message(game.cid, voting_text)
    except Exception as e:
        log.error("count_punish_votes error: " + str(e))


def force_vote(bot, game, uid):
    try:
        update = Dummy()
        update.callback_query = Dummy()
        strcid = str(game.cid)
        rand_action = random.choice([strcid + "_Ja", strcid + "_Nein"])
        update.callback_query.data = rand_action
        update.callback_query.from_user = Dummy()
        update.callback_query.from_user.id = uid
        update.callback_query.from_user.first_name = game.playerlist[uid].name
        update.callback_query.message = Dummy()
        update.callback_query.message.message_id = game.board.state.vote_message_ids[uid]
        handle_voting(bot, update)
    except Exception as e:
        log.error("force_vote error: " + str(e))


def cancel_presidency(bot, game):
    try:
        for uid in game.board.state.vote_message_ids:
            bot.edit_message_text("Voting canceled.",
                                  uid, game.board.state.vote_message_ids[uid])
        game.board.state.nominated_president = None
        game.board.state.nominated_chancellor = None
        voting_aftermath(bot, game, False)
    except Exception as e:
        log.error("cancel_presidency error: " + str(e))


def draw_policies(bot, game):
    log.info('draw_policies called')
    strcid = str(game.cid)
    game.board.state.veto_refused = False
    # shuffle discard pile with rest if rest < 3
    shuffle_policy_pile(bot, game)
    btns = []
    policies = []
    for i in range(3):
        game.board.state.drawn_policies.append(game.board.policies.pop(0))
    for policy in game.board.state.drawn_policies:
        btns.append([InlineKeyboardButton(policy, callback_data=strcid + "_" + policy)])
        policies.append(policy)

    inform_spectators(bot, game, "%s drew %s" % (game.board.state.president.name, ', '.join(policies)))
    choosePolicyMarkup = InlineKeyboardMarkup(btns)
    bot.send_message(game.board.state.president.uid,
                     "You drew the following 3 policies. Which one do you want to discard?",
                     reply_markup=choosePolicyMarkup)


def choose_policy(bot, update):
    log.info('choose_policy called')
    callback = update.callback_query
    regex = re.search("(-[0-9]*)_(.*)", callback.data)
    cid = int(regex.group(1))
    answer = regex.group(2)
    try:
        game = GamesController.games[cid]
        strcid = str(game.cid)
        uid = callback.from_user.id
        claimid = len(game.board.state.player_claims) - 1
        if len(game.board.state.drawn_policies) == 3:
            log.info("Player %s (%d) discarded %s" % (callback.from_user.first_name, uid, answer))
            inform_spectators(bot, game, "%s discarded %s" % (callback.from_user.first_name, answer))
            bot.edit_message_text("The policy %s will be discarded!" % answer, uid,
                                  callback.message.message_id)
            # remove policy from drawn cards and add to discard pile, pass the other two policies
            for i in range(3):
                if game.board.state.drawn_policies[i] == answer:
                    game.board.discards.append(game.board.state.drawn_policies.pop(i))
                    break
            pass_two_policies(bot, game)
        elif len(game.board.state.drawn_policies) == 2:
            if answer == "veto":
                log.info("Player %s (%d) suggested a veto" % (callback.from_user.first_name, uid))
                inform_spectators(bot, game, "%s suggested a veto" % callback.from_user.first_name)
                bot.edit_message_text("You suggested a Veto to President %s" % game.board.state.president.name, uid,
                                      callback.message.message_id)
                bot.send_message(game.cid,
                                 "Chancellor %s suggested a Veto to President %s." % (
                                     game.board.state.chancellor.name, game.board.state.president.name))

                btns = [[InlineKeyboardButton("Veto! (accept suggestion)", callback_data=strcid + "_yesveto")],
                        [InlineKeyboardButton("No Veto! (refuse suggestion)", callback_data=strcid + "_noveto")]]

                vetoMarkup = InlineKeyboardMarkup(btns)
                bot.send_message(game.board.state.president.uid,
                                 "Chancellor %s suggested a Veto to you. Do you want to veto (discard) these cards?" % game.board.state.chancellor.name,
                                 reply_markup=vetoMarkup)
            else:
                log.info("Player %s (%d) chose a %s policy" % (callback.from_user.first_name, uid, answer))
                inform_spectators(bot, game, "%s chose a %s policy" % (callback.from_user.first_name, answer))
                bot.edit_message_text("The policy %s will be enacted!" % answer, uid,
                                      callback.message.message_id)
                if answer == "liberal":
                    game.board.state.player_claims[claimid][3] = "L"
                else:
                    game.board.state.player_claims[claimid][3] = "F"
                # remove policy from drawn cards and enact, discard the other card
                for i in range(2):
                    if game.board.state.drawn_policies[i] == answer:
                        game.board.state.drawn_policies.pop(i)
                        break
                game.board.discards.append(game.board.state.drawn_policies.pop(0))
                assert len(game.board.state.drawn_policies) == 0
                enact_policy(bot, game, answer, False)
        else:
            log.error("choose_policy: drawn_policies should be 3 or 2, but was " + str(
                len(game.board.state.drawn_policies)))
    except:
        log.error("choose_policy: Game or board should not be None!")


def send_claim_message(bot, game, uid, claimid, policies, message):
    btns = []
    strcid = str(game.cid)
    for p in policies:
        btns.append([InlineKeyboardButton(p, callback_data=strcid + "_claim_" + str(claimid) + '_' + p)])
    chooseClaimMarkup = InlineKeyboardMarkup(btns)
    bot.send_message(uid, message, reply_markup=chooseClaimMarkup)


def choose_claim(bot, update):
    log.info('choose_claim called')
    callback = update.callback_query
    uid = callback.from_user.id
    regex = re.search("(-[0-9]*)_claim_([0-9]*)_(.*)", callback.data)
    cid = int(regex.group(1))
    claimid = int(regex.group(2))
    answer = regex.group(3)
    try:
        game = GamesController.games[cid]
        if answer == "FFL" or answer == "FLL":
            if answer == "FFL":
                policies = ["FFL", "FLF", "LFF"]
            else:
                policies = ["FLL", "LFL", "LLF"]
            btns = []
            for p in policies:
                btns.append([InlineKeyboardButton(p, callback_data=str(cid) + "_claimorder_" + str(claimid) + '_' + p)])
            chooseClaimOrderMarkup = InlineKeyboardMarkup(btns)
            bot.edit_message_text("In what order?", uid, callback.message.message_id, reply_markup=chooseClaimOrderMarkup)
        else:
            store_claim(bot, game, callback, claimid, answer)
    except:
        log.error("choose_policy: Game or board should not be None!")


def choose_claim_order(bot, update):
    log.info('choose_claim_order called')
    callback = update.callback_query
    regex = re.search("(-[0-9]*)_claimorder_([0-9]*)_(.*)", callback.data)
    cid = int(regex.group(1))
    claimid = int(regex.group(2))
    answer = regex.group(3)
    try:
        game = GamesController.games[cid]
        store_claim(bot, game, callback, claimid, answer)
    except:
        log.error("choose_policy: Game or board should not be None!")


def store_claim(bot, game, callback, claimid, answer):
    uid = callback.from_user.id
    if len(answer) == 3:
        if len(game.board.state.player_claims[claimid]) == 0:
            if answer == "FFF" or answer == "LLL":
                game.board.state.player_claims[claimid] = ["%s saw top policies" % callback.from_user.first_name]
            else:
                game.board.state.player_claims[claimid] = ["%s saw top policies: %s (in that order)" %
                                                           (callback.from_user.first_name, answer)]
        else:
            game.board.state.player_claims[claimid][1] = answer
    elif len(answer) == 1:
        # result of inspect action
        game.board.state.player_claims[claimid][1] = answer
    else:
        game.board.state.player_claims[claimid][2] = answer

    if answer != "???" and answer != "??" and answer != "?":
        action = "got"
        if len(game.board.state.player_claims[claimid]) == 1 or len(answer) == 1:
            # only one claim from player in player_claims means he saw the top policies
            # having an answer length of 1 means he inspected someone
            action = "saw"
        bot.edit_message_text("You chose to say you %s %s." % (action, answer), uid,
                              callback.message.message_id)
        bot.send_message(game.cid,
                         "%s says he/she %s %s" % (callback.from_user.first_name, action, answer))
    else:
        bot.edit_message_text("You chose to keep it a secret.", uid,
                              callback.message.message_id)


def pass_two_policies(bot, game):
    log.info('pass_two_policies called')
    game.store_last_action(pass_two_policies)
    strcid = str(game.cid)
    btns = []
    for policy in game.board.state.drawn_policies:
        btns.append([InlineKeyboardButton(policy, callback_data=strcid + "_" + policy)])
    if game.board.state.fascist_track == 5 and not game.board.state.veto_refused:
        btns.append([InlineKeyboardButton("Veto", callback_data=strcid + "_veto")])
        choosePolicyMarkup = InlineKeyboardMarkup(btns)
        bot.send_message(game.cid,
                         "President %s gave two policies to Chancellor %s." % (
                             game.board.state.president.name, game.board.state.chancellor.name))
        bot.send_message(game.board.state.chancellor.uid,
                         "President %s gave you the following 2 policies. Which one do you want to enact? You can also use your Veto power." % game.board.state.president.name,
                         reply_markup=choosePolicyMarkup)
    elif game.board.state.veto_refused:
        choosePolicyMarkup = InlineKeyboardMarkup(btns)
        bot.send_message(game.board.state.chancellor.uid,
                         "President %s refused your Veto. Now you have to choose. Which one do you want to enact?" % game.board.state.president.name,
                         reply_markup=choosePolicyMarkup)
    elif game.board.state.fascist_track < 5:
        choosePolicyMarkup = InlineKeyboardMarkup(btns)
        bot.send_message(game.board.state.chancellor.uid,
                         "President %s gave you the following 2 policies. Which one do you want to enact?" % game.board.state.president.name,
                         reply_markup=choosePolicyMarkup)


def enact_policy(bot, game, policy, anarchy):
    log.info('enact_policy called')
    if policy == "liberal":
        game.board.state.liberal_track += 1
    elif policy == "fascist":
        game.board.state.fascist_track += 1
    game.board.state.failed_votes = 0  # reset counter
    if not anarchy:
        bot.send_message(game.cid,
                         "President %s and Chancellor %s enacted a %s policy!" % (
                             game.board.state.president.name, game.board.state.chancellor.name, policy))
    else:
        bot.send_message(game.cid,
                         "The top most policy was enacted: %s" % policy)
    sleep(3)
    bot.send_message(game.cid, game.board.print_board())
    # end of round
    if game.board.state.liberal_track == 5:
        game.board.state.game_endcode = 1
        end_game(bot, game, game.board.state.game_endcode)  # liberals win with 5 liberal policies
    if game.board.state.fascist_track == 6:
        game.board.state.game_endcode = -1
        end_game(bot, game, game.board.state.game_endcode)  # fascists win with 6 fascist policies
    sleep(3)
    # End of legislative session, shuffle if necessary
    claim_id = len(game.board.state.player_claims) - 1
    shuffle_policy_pile(bot, game)
    if not anarchy:
        send_claim_message(bot, game, game.board.state.president.uid, claim_id, ["FFF", "FFL", "FLL", "LLL"],
                           "Select what you want to say that you drew.")
        send_claim_message(bot, game, game.board.state.chancellor.uid, claim_id, ["FF", "FL", "LL"],
                           "Select what you want to say that you got from the president.")
        if policy == "fascist":
            action = game.board.fascist_track_actions[game.board.state.fascist_track - 1]
            if action is None and game.board.state.fascist_track == 6:
                pass
            elif action is None:
                start_next_round(bot, game)
            elif action == "policy":
                bot.send_message(game.cid,
                                 "Presidential Power enabled: Policy Peek " + u"\U0001F52E" + "\nPresident %s now knows the next three policies on "
                                                                                              "the pile.  The President may share "
                                                                                              "(or lie about!) the results of their "
                                                                                              "investigation at their discretion." % game.board.state.president.name)
                action_policy(bot, game)
            elif action == "kill":
                bot.send_message(game.cid,
                                 "Presidential Power enabled: Execution " + u"\U0001F5E1" + "\nPresident %s has to kill one person. You can "
                                                                                            "discuss the decision now but the "
                                                                                            "President has the final say." % game.board.state.president.name)
                action_kill(bot, game)
            elif action == "inspect":
                bot.send_message(game.cid,
                                 "Presidential Power enabled: Investigate Loyalty " + u"\U0001F50E" + "\nPresident %s may see the party membership of one "
                                                                                                      "player. The President may share "
                                                                                                      "(or lie about!) the results of their "
                                                                                                      "investigation at their discretion." % game.board.state.president.name)
                action_inspect(bot, game)
            elif action == "choose":
                bot.send_message(game.cid,
                                 "Presidential Power enabled: Call Special Election " + u"\U0001F454" + "\nPresident %s gets to choose the next presidential "
                                                                                                        "candidate. Afterwards the order resumes "
                                                                                                        "back to normal." % game.board.state.president.name)
                action_choose(bot, game)
        else:
            start_next_round(bot, game)
    else:
        start_next_round(bot, game)


def choose_veto(bot, update):
    log.info('choose_veto called')
    callback = update.callback_query
    regex = re.search("(-[0-9]*)_(.*)", callback.data)
    cid = int(regex.group(1))
    answer = regex.group(2)
    try:
        game = GamesController.games[cid]
        uid = callback.from_user.id
        if answer == "yesveto":
            log.info("Player %s (%d) accepted the veto" % (callback.from_user.first_name, uid))
            inform_spectators(bot, game, "%s accepted Veto" % callback.from_user.first_name)
            bot.edit_message_text("You accepted the Veto!", uid, callback.message.message_id)
            bot.send_message(game.cid,
                             "President %s accepted Chancellor %s's Veto. No policy was enacted but this counts as a failed election." % (
                                 game.board.state.president.name, game.board.state.chancellor.name))
            game.board.discards += game.board.state.drawn_policies
            game.board.state.drawn_policies = []
            game.board.state.failed_votes += 1
            claimid = len(game.board.state.player_claims) - 1
            game.board.state.player_claims[claimid][3] = "V"
            if game.board.state.failed_votes == 3:
                do_anarchy(bot, game)
            else:
                bot.send_message(game.cid, game.board.print_board())
                start_next_round(bot, game)
        elif answer == "noveto":
            log.info("Player %s (%d) declined the veto" % (callback.from_user.first_name, uid))
            inform_spectators(bot, game, "%s refused Veto" % callback.from_user.first_name)
            game.board.state.veto_refused = True
            bot.edit_message_text("You refused the Veto!", uid, callback.message.message_id)
            bot.send_message(game.cid,
                             "President %s refused Chancellor %s's Veto. The Chancellor now has to choose a policy!" % (
                                 game.board.state.president.name, game.board.state.chancellor.name))
            pass_two_policies(bot, game)
        else:
            log.error("choose_veto: Callback data can either be \"yesveto\" or \"noveto\", but not %s" % answer)
    except:
        log.error("choose_veto: Game or board should not be None!")


def do_anarchy(bot, game):
    log.info('do_anarchy called')
    bot.send_message(game.cid, game.board.print_board())
    bot.send_message(game.cid, "ANARCHY!!")
    game.board.state.president = None
    game.board.state.chancellor = None
    top_policy = game.board.policies.pop(0)
    game.board.state.last_votes = {}
    if top_policy == "liberal":
        game.board.state.player_claims.append(["anarchy: L"])
    else:
        game.board.state.player_claims.append(["anarchy: F"])
    enact_policy(bot, game, top_policy, True)


def action_policy(bot, game):
    log.info('action_policy called')
    topPolicies = ""
    # shuffle discard pile with rest if rest < 3
    shuffle_policy_pile(bot, game)
    for i in range(3):
        topPolicies += game.board.policies[i] + "\n"
    bot.send_message(game.board.state.president.uid,
                     "The top three polices are (top most first):\n%s\nYou may lie about this." % topPolicies)
    inform_spectators(bot, game, "%s saw the top policies:\n%s" % (game.board.state.president.name, topPolicies))
    game.board.state.player_claims.append([])
    claimid = len(game.board.state.player_claims) - 1
    send_claim_message(bot, game, game.board.state.president.uid, claimid, ["FFF", "FFL", "FLL", "LLL"],
                       "Select what you want to say you saw for top policies.")
    start_next_round(bot, game)


def action_kill(bot, game):
    log.info('action_kill called')
    game.store_last_action(action_kill)
    strcid = str(game.cid)
    btns = []
    for uid in game.playerlist:
        if uid != game.board.state.president.uid and game.playerlist[uid].is_dead == False:
            name = game.playerlist[uid].name
            btns.append([InlineKeyboardButton(name, callback_data=strcid + "_kill_" + str(uid))])

    killMarkup = InlineKeyboardMarkup(btns)
    bot.send_message(game.board.state.president.uid, game.board.print_board())
    bot.send_message(game.board.state.president.uid,
                     'You have to kill one person. You can discuss your decision with the others. Choose wisely!',
                     reply_markup=killMarkup)


def choose_kill(bot, update, player_id=None):
    log.info('choose_kill called')
    callback = update.callback_query
    if player_id is not None:
        cid = update.message.chat_id
        answer = player_id
        uid = update.message.from_user.id
        fname = update.message.from_user.first_name
    else:
        regex = re.search("(-[0-9]*)_kill_(.*)", callback.data)
        cid = int(regex.group(1))
        answer = int(regex.group(2))
        uid = callback.from_user.id
        fname = callback.from_user.first_name
    try:
        game = GamesController.games[cid]
        chosen = game.playerlist[answer]
        chosen.is_dead = True
        if game.player_sequence.index(chosen) <= game.board.state.player_counter:
            game.board.state.player_counter -= 1
        game.player_sequence.remove(chosen)
        game.board.state.dead += 1
        game.board.state.player_claims.append(["%s killed %s" % (game.board.state.president.name, chosen.name)])
        log.info("Player %s (%d) killed %s (%d)" % (
            fname, uid, chosen.name, chosen.uid))
        bot.edit_message_text("You killed %s!" % chosen.name, uid, callback.message.message_id)
        try:
            bot.unban_chat_member(SPECTATORS_GROUP, answer)
        except:
            log.error("Unable to remove ban for user " + chosen.name + ", " + sys.exc_info()[0])
            bot.send_message(SPECTATORS_GROUP,
                             "%s, couldn't be unbanned. "
                             "Check with admin how to unban him so he can join spectator group" % chosen.name)
        if chosen.role == "Hitler":
            bot.send_message(game.cid, "President " + game.board.state.president.name + " killed " + chosen.name + ". ")
            end_game(bot, game, 2)
        else:
            bot.send_message(game.cid,
                             "President %s killed %s who was not Hitler. %s, you are dead now and are not allowed to talk anymore but can /spectate!" % (
                                 game.board.state.president.name, chosen.name, chosen.name))
            bot.send_message(game.cid, game.board.print_board())
            start_next_round(bot, game)
    except:
        log.error("choose_kill: Game or board should not be None!")


def action_choose(bot, game):
    log.info('action_choose called')
    game.store_last_action(action_choose)
    strcid = str(game.cid)
    btns = []

    for uid in game.playerlist:
        if uid != game.board.state.president.uid and game.playerlist[uid].is_dead == False:
            name = game.playerlist[uid].name
            btns.append([InlineKeyboardButton(name, callback_data=strcid + "_choo_" + str(uid))])

    chooseMarkup = InlineKeyboardMarkup(btns)
    bot.send_message(game.board.state.president.uid, game.board.print_board())
    bot.send_message(game.board.state.president.uid,
                     'You get to choose the next presidential candidate. Afterwards the order resumes back to normal. Choose wisely!',
                     reply_markup=chooseMarkup)


def choose_choose(bot, update):
    log.info('choose_choose called')
    callback = update.callback_query
    log.info(bot)
    log.info(update)
    regex = re.search("(-[0-9]*)_choo_(.*)", callback.data)
    cid = int(regex.group(1))
    answer = int(regex.group(2))
    try:
        game = GamesController.games[cid]
        chosen = game.playerlist[answer]
        game.board.state.chosen_president = chosen
        log.info(
            "Player %s (%d) chose %s (%d) as next president" % (
                callback.from_user.first_name, callback.from_user.id, chosen.name, chosen.uid))
        bot.edit_message_text("You chose %s as the next president!" % chosen.name, callback.from_user.id,
                              callback.message.message_id)
        game.board.state.player_claims.append(["%s chose next president: %s" % (game.board.state.president.name, chosen.name)])
        bot.send_message(game.cid,
                         "President %s chose %s as the next president." % (
                             game.board.state.president.name, chosen.name))
        start_next_round(bot, game)
    except:
        log.error("choose_choose: Game or board should not be None!")


def action_inspect(bot, game):
    log.info('action_inspect called')
    game.store_last_action(action_inspect)
    strcid = str(game.cid)
    btns = []
    for uid in game.playerlist:
        if uid != game.board.state.president.uid and game.playerlist[uid].is_dead == False:
            name = game.playerlist[uid].name
            btns.append([InlineKeyboardButton(name, callback_data=strcid + "_insp_" + str(uid))])

    inspectMarkup = InlineKeyboardMarkup(btns)
    bot.send_message(game.board.state.president.uid, game.board.print_board())
    bot.send_message(game.board.state.president.uid,
                     'You may see the party membership of one player. Which do you want to know? Choose wisely!',
                     reply_markup=inspectMarkup)


def choose_inspect(bot, update):
    log.info('choose_inspect called')
    callback = update.callback_query
    regex = re.search("(-[0-9]*)_insp_(.*)", callback.data)
    cid = int(regex.group(1))
    answer = int(regex.group(2))
    try:
        game = GamesController.games[cid]
        chosen = game.playerlist[answer]
        log.info(
            "Player %s (%d) inspects %s (%d)'s party membership (%s)" % (
                callback.from_user.first_name, callback.from_user.id, chosen.name, chosen.uid,
                chosen.party))
        bot.edit_message_text("The party membership of %s is %s" % (chosen.name, chosen.party),
                              callback.from_user.id,
                              callback.message.message_id)
        game.board.state.player_claims.append(
            ["%s inspected %s to be" % (game.board.state.president.name, chosen.name), "?"])
        claimid = len(game.board.state.player_claims) - 1
        send_claim_message(bot, game, callback.from_user.id, claimid, ["F", "L"],
                           "Select what you want to say %s is." % chosen.name)
        bot.send_message(game.cid, "President %s inspected %s." % (game.board.state.president.name, chosen.name))
        start_next_round(bot, game)
    except:
        log.error("choose_inspect: Game or board should not be None!")


def start_next_round(bot, game):
    log.info('start_next_round called')
    # start next round if there is no winner (or /cancel)
    if game.board.state.game_endcode == 0:
        # start new round
        sleep(5)
        # if there is no special elected president in between
        if game.board.state.chosen_president is None:
            increment_player_counter(game)
        start_round(bot, game)


##
#
# End of round
#
##

def end_game(bot, game, game_endcode):
    log.info('end_game called')
    ##
    # game_endcode:
    #   -2  fascists win by electing Hitler as chancellor
    #   -1  fascists win with 6 fascist policies
    #   0   not ended
    #   1   liberals win with 5 liberal policies
    #   2   liberals win by killing Hitler
    #   99  game cancelled
    #
    with open(STATS, 'r') as f:
        stats = json.load(f)

    for uid in game.playerlist:

        try:
            bot.unban_chat_member(SPECTATORS_GROUP, uid)
        except:
            unban_player = game.playerlist[uid].name
            log.error("Unable to remove ban for user " + unban_player + ", " + sys.exc_info()[0])
            bot.send_message(SPECTATORS_GROUP,
                             "%s, couldn't be unbanned. "
                             "Check with admin how to unban him so he can join spectator group" % unban_player)
    if game_endcode == 99:
        if GamesController.games[game.cid].board is not None:
            bot.send_message(game.cid,
                             "Game cancelled!\n\n%s" % game.print_roles())
            # bot.send_message(ADMIN, "Game of Secret Hitler canceled in group %d" % game.cid)
            stats['cancelled'] = stats['cancelled'] + 1
        else:
            bot.send_message(game.cid, "Game cancelled!")
    else:
        ranking = Ranking()
        # ranking.decay_non_active(game.cid)
        for uid in game.playerlist:
            player = game.playerlist[uid]
            ranking.increment_game(game.cid, player)
            log.info("Incrementing quantity of games for %s" % player.name)
        fascists_players = game.get_fascists() + [game.get_hitler()]
        if game_endcode == -2:
            bot.send_message(game.cid,
                             "Game over! The fascists win by electing Hitler as Chancellor!\n\n%s" % game.print_roles())
            stats['fascwin_hitler'] = stats['fascwin_hitler'] + 1
            ranking.update_ranking(game.cid, fascists_players, False)
        if game_endcode == -1:
            bot.send_message(game.cid,
                             "Game over! The fascists win by enacting 6 fascist policies!\n\n%s" % game.print_roles())
            stats['fascwin_policies'] = stats['fascwin_policies'] + 1
            ranking.update_ranking(game.cid, fascists_players, False)
        if game_endcode == 1:
            bot.send_message(game.cid,
                             "Game over! The liberals win by enacting 5 liberal policies!\n\n%s" % game.print_roles())
            stats['libwin_policies'] = stats['libwin_policies'] + 1
            ranking.update_ranking(game.cid, game.get_liberals(), True)
        if game_endcode == 2:
            bot.send_message(game.cid,
                             "Game over! The liberals win by killing Hitler!\n\n%s" % game.print_roles())
            stats['libwin_kill'] = stats['libwin_kill'] + 1
            ranking.update_ranking(game.cid, game.get_liberals(), True)

            # bot.send_message(ADMIN, "Game of Secret Hitler ended in group %d" % game.cid)

    with open(STATS, 'w') as f:
        json.dump(stats, f)
    del GamesController.games[game.cid]


def inform_players(bot, game, cid, player_number):
    log.info('inform_players called')
    bot.send_message(cid,
                     "Let's start the game with %d players!\n%s\nGo to your private chat and look at your secret role!" % (
                         player_number, print_player_info(player_number)))
    available_roles = list(playerSets[player_number]["roles"])  # copy not reference because we need it again later
    for uid in game.playerlist:
        random_index = randrange(len(available_roles))
        role = available_roles.pop(random_index)
        party = get_membership(role)
        game.playerlist[uid].role = role
        game.playerlist[uid].party = party
        bot.send_message(uid, "Your secret role is: %s\nYour party membership is: %s" % (role, party))


def print_player_info(player_number):
    if player_number == 5:
        return "There are 3 Liberals, 1 Fascist and Hitler. Hitler knows who the Fascist is."
    elif player_number == 6:
        return "There are 4 Liberals, 1 Fascist and Hitler. Hitler knows who the Fascist is."
    elif player_number == 7:
        return "There are 4 Liberals, 2 Fascist and Hitler. Hitler doesn't know who the Fascists are."
    elif player_number == 8:
        return "There are 5 Liberals, 2 Fascist and Hitler. Hitler doesn't know who the Fascists are."
    elif player_number == 9:
        return "There are 5 Liberals, 3 Fascist and Hitler. Hitler doesn't know who the Fascists are."
    elif player_number == 10:
        return "There are 6 Liberals, 3 Fascist and Hitler. Hitler doesn't know who the Fascists are."


def inform_spectators(bot, game, message):
    game.secret_actions.append(message)
    bot.send_message(SPECTATORS_GROUP, message)
    for uid in game.spectators:
        bot.send_message(uid, message)


def join_spectate(game, uid):
    game.spectators.append(uid)
    return ("Here are the true events, keep them a secret!\n" + game.print_roles() + "\n"
            "What each player did so far:\n" + "\n".join(game.secret_actions) + "\n"
            "You'll get more updates as the game continues.\n"
            "If you'd like to, you can join game discussions for this game at " + SPECTATORS_JOIN_URL
            )


def inform_fascists(bot, game, player_number):
    log.info('inform_fascists called')

    for uid in game.playerlist:
        role = game.playerlist[uid].role
        if role == "Fascist":
            fascists = game.get_fascists()
            if player_number > 6:
                fstring = ""
                for f in fascists:
                    if f.uid != uid:
                        fstring += f.name + ", "
                fstring = fstring[:-2]
                bot.send_message(uid, "Your fellow fascists are: %s" % fstring)
            hitler = game.get_hitler()
            bot.send_message(uid, "Hitler is: %s" % hitler.name)
        elif role == "Hitler":
            if player_number <= 6:
                fascists = game.get_fascists()
                bot.send_message(uid, "Your fellow fascist is: %s" % fascists[0].name)
        elif role == "Liberal":
            pass
        else:
            log.error("inform_fascists: can\'t handle the role %s" % role)


def get_membership(role):
    log.info('get_membership called')
    if role == "Fascist" or role == "Hitler":
        return "fascist"
    elif role == "Liberal":
        return "liberal"
    else:
        return None


def increment_player_counter(game):
    log.info('increment_player_counter called')
    if game.board.state.player_counter < len(game.player_sequence) - 1:
        game.board.state.player_counter += 1
    else:
        game.board.state.player_counter = 0


def shuffle_policy_pile(bot, game):
    log.info('shuffle_policy_pile called')
    if len(game.board.policies) < 3:
        game.board.discards += game.board.policies
        game.board.policies = random.sample(game.board.discards, len(game.board.discards))
        game.board.discards = []
        game.board.state.player_claims.append(['pile shuffled'])
        bot.send_message(game.cid,
                         "There were not enough cards left on the policy pile so I shuffled the rest with the discard pile!")


def choose_retry(bot, update):
    log.info('choose_retry called')
    callback = update.callback_query
    regex = re.search("(-[0-9]*)_retry_(.*)", callback.data)
    cid = int(regex.group(1))
    action_id = int(regex.group(2))
    try:
        game = GamesController.games[cid]
        action = game.get_last_action(action_id)
        if action is None:
            bot.edit_message_text("Tried to execute selected last action, but it was missing.\nPossibly someone "
                                  "executed another action, causing the selected one to be deleted from history",
                                  callback.from_user.id, callback.message.message_id)
            bot.send_message(game.cid, "Retry failed, action was missing.")
        else:
            bot.edit_message_text("The action %s will executed again!" % action['function'].__name__,
                                  callback.from_user.id, callback.message.message_id)
            bot.send_message(game.cid,
                             'Executing last action "%s" with the previous game state' %
                             action['function'].__name__)
            GamesController.games[cid] = action['state']
            action['function'](bot, action['state'])
    except:
        log.error("choose_retry: Game or board should not be None!")


def retry_last_command(bot, game, uid):
    log.info('retry_last_command called')
    btns = []
    strcid = str(game.cid)
    while game.last_action['depth'] > 0:
        btns.append([InlineKeyboardButton(game.last_action['function'].__name__,
                                          callback_data=strcid + "_retry_" + str(game.last_action['id']))])
        game = game.last_action['state']

    retryMarkup = InlineKeyboardMarkup(btns)
    bot.send_message(uid, "Please choose an action to be executed again.",
                     reply_markup=retryMarkup)


def error(bot, update, error):
    logger.warning('Update "%s" caused error "%s"' % (update, error))


def main():
    GamesController.init()  # Call only once
    # initialize_testdata()

    updater = Updater(TOKEN)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", Commands.command_start))
    dp.add_handler(CommandHandler("help", Commands.command_help))
    dp.add_handler(CommandHandler("board", Commands.command_board))
    dp.add_handler(CommandHandler("rules", Commands.command_rules))
    dp.add_handler(CommandHandler("ping", Commands.command_ping))
    dp.add_handler(CommandHandler("symbols", Commands.command_symbols))
    dp.add_handler(CommandHandler("adminstats", Commands.command_admin_stats))
    dp.add_handler(CommandHandler("newgame", Commands.command_newgame))
    dp.add_handler(CommandHandler("startgame", Commands.command_startgame))
    dp.add_handler(CommandHandler("startrebalanced", Commands.command_startgame_rebalanced))
    dp.add_handler(CommandHandler("spectate", Commands.command_spectate))
    dp.add_handler(CommandHandler("heudon", Commands.command_heudon))
    dp.add_handler(CommandHandler("cancelgame", Commands.command_cancelgame))
    dp.add_handler(CommandHandler("join", Commands.command_join))
    dp.add_handler(CommandHandler("votes", Commands.command_votes))
    dp.add_handler(CommandHandler("calltovote", Commands.command_calltovote))
    # dp.add_handler(CommandHandler("calltokill", Commands.command_calltokill))
    dp.add_handler(CommandHandler("calltopunish", Commands.command_calltopunish))
    dp.add_handler(CommandHandler("retry", Commands.command_retry))
    dp.add_handler(CommandHandler("stats", Commands.command_stats))
    dp.add_handler(CommandHandler("ranking", Commands.command_ranking))

    dp.add_handler(CallbackQueryHandler(pattern="(-[0-9]*)_chan_(.*)", callback=nominate_chosen_chancellor))
    dp.add_handler(CallbackQueryHandler(pattern="(-[0-9]*)_insp_(.*)", callback=choose_inspect))
    dp.add_handler(CallbackQueryHandler(pattern="(-[0-9]*)_choo_(.*)", callback=choose_choose))
    dp.add_handler(CallbackQueryHandler(pattern="(-[0-9]*)_kill_(.*)", callback=choose_kill))
    dp.add_handler(CallbackQueryHandler(pattern="(-[0-9]*)_(yesveto|noveto)", callback=choose_veto))
    dp.add_handler(CallbackQueryHandler(pattern="(-[0-9]*)_(liberal|fascist|veto)", callback=choose_policy))
    dp.add_handler(CallbackQueryHandler(pattern="(-[0-9]*)_(Ja|Nein)", callback=handle_voting))
    dp.add_handler(CallbackQueryHandler(pattern="(-[0-9]*)_(.*)_(Ja|Nein)", callback=handle_vote_punish))
    dp.add_handler(CallbackQueryHandler(pattern="(-[0-9]*)_retry_(.*)", callback=choose_retry))
    dp.add_handler(CallbackQueryHandler(pattern="(-[0-9]*)_claim_(.*)", callback=choose_claim))
    dp.add_handler(CallbackQueryHandler(pattern="(-[0-9]*)_claimorder_(.*)", callback=choose_claim_order))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until the you presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
