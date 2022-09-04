#!/bin/python

import os
import re
import numpy
import random
import time
import threading
import discord

# Define funcs
async def processWritingSubmission(game, player_index, receivedMessage):
	response = await parseSubmittedWord(game, player_index, receivedMessage, game["allow_hard_words"])
	word = response[0]
	_alert = response[1]
	if len(word) == 5:
		game["words"][player_index].append(word)
	await game["player_list"][player_index].send(_alert)

async def processGuessingSubmission(game, player_index, receivedMessage):
	response = await parseSubmittedWord(game, player_index, receivedMessage, True)
	word = response[0]
	_alert = response[1]
	if len(word) == 5:
		game["guesses"][player_index].append(word)
		if not await hasEveryoneFinishedGuessing(game):
			await game["player_list"][player_index].send(_alert)
			# v = await game["player_list"][player_index].send(_alert)
			# await game["waiting_messages_to_delete"].append(v)
	else:
		await game["player_list"][player_index].send(_alert)

async def processEditingSubmission(game, player_index, receivedMessage):
	parts = receivedMessage.split(" ")
	nextI = (player_index+1)%len(game["player_list"])
	wordOn = game["word_on"][nextI]
	origWord = game["words"][player_index][wordOn]
	if parts[0].lower() != origWord:
		await game["player_list"][player_index].send("If you're trying to initiate an edit, the first word must be the word your opponent is trying to guess. Right now, that's "+(await formatWord(origWord,True,False))+".")
		return

	response = await parseSubmittedWord(game, player_index, parts[1], game["allow_hard_words"])
	newWord = response[0]
	_alert = response[1]
	if len(newWord) == 5:
		editCost = await getEditCost(origWord,newWord)
		if editCost > game["edits"][player_index]:
			await game["player_list"][player_index].send("TOO POOR. You only have "+(await pluralize(game["edits"][player_index], "edit"))+" in the bank, but editing your "+(await rankify(wordOn))+" word from "+(await formatWord(origWord, True, False))+" to "+(await formatWord(newWord, True, False))+" would cost you "+(await pluralize(editCost, "edit"))+".")
		else:
			game["words"][player_index][wordOn] = newWord
			game["most_recent_edit"][player_index] = game["round_count"]
			game["edits"][player_index] -= editCost

			appendix = ""
			if len(game["guesses"][player_index]) < game["round_count"]:
				appendix = "\nDon't forget to write a guess for YOUR word, though!"
			await game["player_list"][player_index].send("SUCCESS! Your "+(await rankify(wordOn))+" word was successfully edited from "+(await formatWord(origWord, True, False))+" to "+(await formatWord(newWord, True, False))+"! That cost you "+(await pluralize(editCost,"edit"))+", leaving you with "+(await pluralize(game["edits"][player_index],"edit"))+" left."+appendix)
	else:
		await game["player_list"][player_index].send(_alert)

async def getEditCost(a, b):
	count = 0
	for i in range(5):
		if a[i] != b[i]:
			count += 1
	return count

async def pluralize(n, stri):
	if n == 1:
		return str(n)+" "+stri
	return str(n)+" "+stri+"s"

async def hasEveryoneFinishedWriting(game):
	LEN = len(game["player_list"])
	for i in range(LEN):
		if len(game["words"][i]) < game["word_count"]:
			return False
	return True

async def hasEveryoneFinishedGuessing(game):
	LEN = len(game["player_list"])
	for i in range(LEN):
		if len(game["guesses"][i]) < game["round_count"]:
			return False
	return True

async def getPlayerIndex(author):
	LEN = len(game["player_list"])
	for i in range(LEN):
		if game["player_list"][i] == author:
			return i
	return -1

async def parseSubmittedWord(game, player_index, message, allow_hard_words):
	global wordList
	global wordListEasy
	word = re.sub(r'[^a-z]', '', message.lower())
	if len(word) < 5:
		return ["", "That word isn't long enough"]
	else:
		word = word[0:5]
		thisWordList = wordList if allow_hard_words else wordListEasy
		if word in thisWordList:
			_alert = ""
			if game["stage"] == 2:
				wordCountSoFar = len(game["words"][player_index])
				_alert = "Word #"+str(wordCountSoFar+1)+" of "+str(game["word_count"])+" succesfuly received as "+(await formatWord(word, True, False))
				if wordCountSoFar == game["word_count"]-1:
					_alert += ". You submitted all your words."
			elif game["stage"] == 3:
				guessCount = len(game["guesses"][player_index])
				_alert = "Guess # "+str(guessCount+1)+" successfully received as "+(await formatWord(word, True, False))+". Waiting for the round to finish."
			return [word, _alert]
		else:
			return ["","That word isn't in Wordle's dictionary, try again."]

async def getCode(guess, answer):
	LEN = 5

	guessArr = [None, None, None, None, None]
	answerArr = [None, None, None, None, None]
	result = [None, None, None, None, None]
	for pos in range(LEN):
		guessArr[pos] = ord(guess[pos])-CHAR_CODE_A
		answerArr[pos] = ord(answer[pos])-CHAR_CODE_A
		result[pos] = 0

	for pos in range(LEN):
		g = guessArr[pos]
		if answerArr[pos] == g:
			result[pos] = 2
			guessArr[pos] = -1
			answerArr[pos] = -1

	resultString = ""
	for pos in range(LEN):
		if result[pos] == 0:
			for apos in range(LEN):
				if answerArr[apos] == guessArr[pos]:
					result[pos] = 1
					guessArr[pos] = -1
					answerArr[apos] = -1
		resultString += chr(result[pos] + CHAR_CODE_A)
	return resultString

async def handleGameMessage(message):
	mc = message.channel
	args = message.content[len(PREFIX):].split(" ")
	command = args[0].lower()
	author = message.author
	if command == 'join':
		if game["stage"] == 1:
			if author in game["player_list"]:
				await mc.send(author.name+", you're already in this game. Don't try to join twice.")
			else:
				game["player_list"].append(author)

				game["words"].append([])
				game["guesses"].append([])
				game["codes"].append([])

				game["word_on"].append(0)
				game["edits"].append(0)
				game["max_greens"].append(0)
				game["most_recent_edit"].append(-1)
				game["most_recent_new_word"].append(-1)

				game["won"].append(False)

				await mc.send(author.name+" just joined the game. "+
					"\nPlayer count: "+str((len(game["player_list"]))))
		else:
			await mc.send("It's the wrong stage of game for that.")
	elif command == 'start':
		if game["stage"] == 1:
			PLAYER_COUNT = len(game["player_list"])
			if PLAYER_COUNT < 1:
				await mc.send("There are only "+str(PLAYER_COUNT)+" players. Not enough.")
			else:
				await startGame(game, args)
		else:
			await mc.send("It's the wrong stage of game for that.")
	elif command == 'create':
		await mc.send("It's the wrong stage of game for that.")
	elif command == 'abort':
		await abort(game, "This WordleEdit game has been aborted.")

async def abort(game, message):
	global intervalFunc
	global stopFlag
	if intervalFunc != None:
		await deleteMessages(game, "timer_messages_to_edit")
		stopFlag = True
		intervalFunc = None
	await alertChannelAndPlayers(game, message)
	game["stage"] = 0

	global client
	await client.change_presence(status=discord.Status.idle, activity=None)

async def alertChannelAndPlayers(game, stri):
	await game["channel"].send(stri)
	LEN = len(game["player_list"])
	for i in  range(LEN):
		await game["player_list"][i].send(stri)

async def startGame(game, args):
	global intervalFunc
	global stopFlag
	mc = game["channel"]
	game["stage"] = 2
	await mc.send(frill+" **STARTING THE WORDLEEDIT GAME NOW!** "+frill)
	await mc.send((await announceStringOf(game,2))+"\nPlayers, go into your DMs with this bot to play the remainder of this game.")

	game["timer"] = game["writing_stage_time"]
	game["timer_messages_to_edit"] = []

	await setTimersAndMessagePlayerList(game)

	async def setUpInterval():
		global stopFlag
		while not stopFlag:
			await updateAllTimers(game)
			if game["timer"] <= 0:
				await wrapUpWritingStageBecauseTimeRanOut(game)
				await startGuessingStage(game)
			time.sleep(2)
	stopFlag = False
	intervalFunc = threading.Thread(target=setUpInterval)

	global client
	await client.change_presence(status=discord.Status.online, activity=discord.Game("WordleEditPy!"))

async def wrapUpWritingStageBecauseTimeRanOut(game):
	LEN = len(game["player_list"])
	wc = game["word_count"]

	for p_i in range(LEN):
		swc = len(game["words"][p_i])
		pc = game["player_list"][p_i]

		if swc == wc:
			await pc.send("Congrats! You submitted all your words on time.")
		else:
			rwc = wc-swc
			messageString = "You only submitted "+(await pluralize(swc,"word"))+" on time. So, the final "+(await pluralize(rwc,"word"))+" have been randomly chosen by the bot (me) to be:"
			for w_i in range(rwc):
				word = await getRandomWord(game)
				messageString += "\n"+(await formatWord(word, True, False))
				game["words"][p_i].append(word)
			await pc.send(messageString)

async def deleteMessages(game, list):
	for i in game[list]:
		m = i
		if m != None:
			game[list].remove(m)
	game[list] = []

async def startGuessingStage(game):
	global intervalFunc
	global stopFlag
	await deleteMessages(game, "timer_messages_to_edit")
	stopFlag = True
	intervalFunc = None

	game["stage"] = 3
	game["round_count"] = 1
	await alertChannelAndPlayers(game, "All players have submitted their words. Time for the guessing stage to begin.")

	for i in range(len(game["player_list"])):
		game["words"][i].append('*****')

	await startGuessingTurn(game)

async def startGuessingTurn(game):
	global intervalFunc
	global stopFlag
	game["timer"] = game["guessing_stage_time"]
	game["timer_messages_to_edit"] = []

	await setTimersAndMessagePlayerList(game)

	async def setUpInterval():
		global stopFlag
		while not stopFlag:
			await updateAllTimers(game)
			if game["timer"] <= 0:
				await finishGuessingTurn(game)
			time.sleep(2)
	stopFlag = False
	intervalFunc = threading.Thread(target=setUpInterval)

async def getRandomWord(game):
	global wordList
	global wordListEasy
	thisGamesWordList = wordList if game["allow_hard_words"] else wordListEasy
	choice = numpy.floor(random.random()*len(thisGamesWordList))
	return thisGamesWordList[choice]

async def countGreens(code):
	count = 0
	for i in range(len(code)):
		if ord(code[i]) == 2 + CHAR_CODE_A:
			count += 1
	return count

async def calculatePlayersRoundPerformance(game, p_i, r, LEN):
	if game["won"][p_i]:
		return
	pgc = len(game["guesses"][p_i])
	pc = game["player_list"][p_i]
	if pgc < game["round_count"]:
		if game["auto_guess"]:
			word = await getRandomWord(game)
			game["guesses"][p_i].append(word)
			await pc.send("You didn't guess in time. So, your guess will be randomly chosen by the bot (me) to be:\n"+formatWord(word, True, False))
		else:
			word = "*****"
			game["guesses"][p_i].append(word)
			await pc.send("You didn't guess in time, so we're going to skip your turn! Better luck next time.")
			
	prevI = (p_i+LEN-1)%LEN
	wordOn = game["word_on"][p_i]
	guess = game["guesses"][p_i][r]
	answer = game["words"][prevI][wordOn]
	code = await getCode(guess, answer)
	game["codes"][p_i].append(code)

	greenCount = await countGreens(code)
	diff = greenCount-game["max_greens"][p_i]

	if diff > 0:
		if diff >= game["greens_needed_for_an_edit"]:
			game["edits"][p_i] = numpy.min([game["edits"][p_i]+1,game["max_edits"]])
		game["max_greens"][p_i] = greenCount

	if (await countLetters(code, 'a')) >= game["grays_needed_for_an_edit"]:
		prevI = (p_i+LEN-1)%LEN
		game["edits"][prevI] = numpy.min([game["edits"][prevI]+1,game["max_edits"]])

async def countLetters(stri, ch):
	count = 0
	for i in range(len(stri)):
		if stri[i] == ch:
			count += 1
	return count

async def finishGuessingTurn(game):
	r = game["round_count"]-1
	LEN = len(game["player_list"])
	for p_i in range(LEN):
		await calculatePlayersRoundPerformance(game, p_i, r, LEN)
	await deleteMessages(game, "timer_messages_to_edit")
	await deleteMessages(game, "waiting_messages_to_delete")

	await game["channel"].send(await formatRoundResult(game, r, -1))
	for p_i in range(LEN):
		await game["player_list"][p_i].send(await formatRoundResult(game, r, p_i))

	finished = game["won"]
	for p_i in range(LEN):
		if game["codes"][p_i][r] == "ccccc":
			prevI = (p_i+LEN-1)%LEN
			prevP = game["player_list"][prevI]
			wordOn = game["word_on"][p_i]
			if wordOn == game["word_count"]-1:
				finished[p_i] = True
				game["won"][p_i] = True
				await game["player_list"][p_i].send("You're done!")
				game["word_on"][p_i] += 1
				game["codes"][p_i].append("ddddd")
				game["guesses"][p_i].append(game["guesses"][p_i][-1])
			elif wordOn > game["word_count"]-1:
				finished[p_i] = True
				game["codes"][p_i].append("ddddd")
				game["guesses"][p_i].append(game["guesses"][p_i][-1])
			elif wordOn < game["word_count"]-1:
				await game["player_list"][p_i].send("Congrats, you solved "+prevP.name+"'s "+(await rankify(wordOn))+" word! Guess their "+(await rankify(wordOn+1))+" one.")

				game["word_on"][p_i] += 1
				game["max_greens"][p_i] = 0
				game["most_recent_new_word"][p_i] = r+1
	
	game["round_count"] += 1
	if not (False in finished):
		await abort(game, "All players done!")

async def getTiedString(game, finishers, exclude):
	tiedString = ""
	for f_j in range(len(finishers)):
		if f_j != exclude:
			tiedString += game["player_list"][finishers[f_j]].name+" and "
	return tiedString[0:-5]

async def formatRoundResult(game, round_i, player_i):
	black = ":black_large_square: "
	boom = ":boom: "
	pencil = ":pencil: "
	puzzle = ":jigsaw: "
	questWord = ""
	for i in range(5):
		questWord += ":question: "

	LEN = len(game["player_list"])

	guesses_string = ". "
	codes_string = ". "
	truth_string = ". "
	for psuedo_i in range(LEN):
		p_i = psuedo_i
		if player_i >= 0:
			p_i = (psuedo_i+player_i)%LEN
		prevI = (p_i+LEN-1)%LEN
		tile = black
		if game["most_recent_edit"][prevI] == game["round_count"]:
			tile = boom
		wordOn = game["word_on"][p_i]

		guesses_string += tile+puzzle+(await formatWord(game["guesses"][p_i][round_i], True, True))+pencil+tile
		w = (game["word_on"][p_i]+1)%10
		e = game["edits"][p_i]%10
		codes_string += tile+(await formatNumber(w))+(await formatCode(game["codes"][p_i][round_i], True, True))+(await formatNumber(e))+tile

		truth_piece = questWord
		if player_i == prevI or game["codes"][p_i][round_i] == "ccccc":
			truth_piece = await formatWord(game["words"][prevI][wordOn], True, True)
		truth_string += tile+tile+truth_piece+tile+tile

	if player_i >= 0 and game["show_keyboard"]:
		remainingCharacters = await getRemainingCharacters(game, player_i)
		
		rows = [None] * 3
		for r in range(3):
			rows[r] = black+black+black+thought
		perRow = numpy.ceil(len(remainingCharacters)/3)

		for ch_i in range(len(remainingCharacters)):
			ch = remainingCharacters[ch_i]
			character_block = await formatLetter(ch)
			row = int(numpy.floor(ch_i/perRow))
			rows[row] += character_block
		guesses_string += rows[0]
		codes_string += rows[1]
		truth_string += rows[2]

	result = ""
	if player_i >= 0:
		result += await playerListToString(game, player_i)+"\n"
	elif round_i == 0:
		result += await playerListToString(game, 0)+"\n"
	result += guesses_string+"\n"+codes_string
	if player_i >= 0:
		result += "\n"+truth_string
	return result

async def getRemainingCharacters(game, player_i):
	LEN = len(game["player_list"])
	remainingCharacterIndices = [True] * 26
	prevI = (player_i+LEN-1)%LEN

	firstUsefulRound = numpy.max([game["most_recent_edit"][prevI],game["most_recent_new_word"][player_i],0])

	for round in range(firstUsefulRound, game["round_count"]):
		guess = game["guesses"][player_i][round]
		code = game["codes"][player_i][round]
		for i in range(5):
			if code[i] == '*':
				continue
			if code[i] == 'a':
				DQedLetter = ord(guess[i])-CHAR_CODE_A
				remainingCharacterIndices[DQedLetter] = False
		for i in range(5):
			if code[i] == '*':
				continue
			if code[i] != 'a':
				approvedLetter = ord(guess[i])-CHAR_CODE_A
				remainingCharacterIndices[approvedLetter] = True

	remainingCharacters = []
	for i in range(26):
		if remainingCharacterIndices[i]:
			remainingCharacters.append(chr(i + CHAR_CODE_A))
	return remainingCharacters

async def updateAllTimers(game):
	game["timer"] -= 2
	if game["timer"] >= 2:
		editedStri = await formatTime(game["timer"])
		LEN = len(game["timer_messages_to_edit"])
		for i in range(LEN):
			mess = game["timer_messages_to_edit"][i]
			if mess != None:
				mess.edit(editedStri)
	print("TICK!")

async def setTimersAndMessagePlayerList(game):
	# v = await game["channel"].send(await formatTime(game["timer"]))
	# game["timer_messages_to_edit"].append(v)

	LEN = len(game["player_list"])
	for i in range(LEN):
		prevI = (i+LEN-1)%LEN
		nextI = (i+1)%LEN
		p = game["player_list"][i]
		nextP = game["player_list"][nextI]
		prevP = game["player_list"][prevI]

		if game["stage"] == 2:
			await game["player_list"][i].send("Hello, "+p.name+"! In this WordleEdit game, you are Player #"+str(i+1)+" of "+str(LEN)+". Please type "+(await pluralize(game["word_count"], "word"))+" for Player #"+str(nextI+1)+" ("+nextP.name+") to guess.")
		elif game["stage"] == 3 and game["round_count"] == 1:
			wordOn = game["word_on"][i]
			await game["player_list"][i].send("Please guess "+prevP.name+"'s "+(await rankify(wordOn))+" word.")

		# w = await game["player_list"][i].send(await # formatTime(game["timer"]))
		# game["timer_messages_to_edit"].append(w)

async def rankify(n):
	modN = (n%100)+1
	suffix = ""
	if modN >= 10 and modN < 20:
		suffix = 'th'
	else:
		if modN%10 == 1:
			suffix = 'st'
		elif modN%10 == 2:
			suffix = 'nd'
		elif modN%10 == 3:
			suffix = 'rd'
		else:
			suffix = 'th'
	return str(n+1)+suffix

async def playerListToString(game, indexShift):
	LEN = len(game["player_list"])
	RESULT_STR = ":arrow_right:   " if LEN > 2 else ""
	for i in range(LEN):
		if i == 1 and LEN == 2:
			RESULT_STR += "   ←---→   "
		else:
			if i >= 1:
				RESULT_STR += "   ----→   "
		RESULT_STR += game["player_list"][(i-indexShift+LEN)%LEN].name
	if LEN > 2:
		RESULT_STR += ":arrow_right"
	return RESULT_STR

async def formatWord(word, emojify, finalSpace):
	if emojify:
		result = ""
		for i in range(5):
			toAdd = ":question:" if word[i] == '*' else ":regional_indicator_"+word[i]+":"
			result += toAdd
			if finalSpace or i < 4:
				result += " "
		return result
	else:
		return word.upper()

async def formatLetter(ch):
	return ":regional_indicator_"+ch+": "

async def formatCode(code, emojify, finalSpace):
	if emojify:
		emojis = [":white_large_square:",":yellow_square:",":green_square:",":green_heart:"]
		result = ""
		for i in range(5):
			if code == "ccccc":
				result += emojis[3]
			else:
				result += emojis[ord(code[i])-CHAR_CODE_A]
			if finalSpace or i < 4:
				result += " "
		return result
	else:
		return code.upper()

async def formatTime(timer):
	return "Time left: "+(await formatNumber(timer))

async def formatNumber(number):
	sNumber = str(number)+""
	numberNames = ["zero","one","two","three","four","five","six","seven","eight","nine"]
	LEN = len(sNumber)
	result = ""
	for i in range(LEN):
		result += ":"+numberNames[ord(sNumber[i])-ZERO]+": "
	return result

async def announceStringOf(game,stage):
	ANNOUNCE_STR = "We're creating a brand new game of WordleEdit!"
	if stage == 1:
		ANNOUNCE_STR += "\nType \""+PREFIX+"join\" to join this game."
	elif stage == 2:
		ANNOUNCE_STR += "\n\nPlayer list: "
		for p in game["player_list"]:
			ANNOUNCE_STR += "\n"+p.name
	return ANNOUNCE_STR

async def newCleanGame(mc, args):
	thisGame = {}
	thisGame["player_list"] = []

	thisGame["words"] = []
	thisGame["guesses"] = []
	thisGame["codes"] = []
	thisGame["word_on"] = []
	thisGame["timer_messages_to_edit"] = []
	thisGame["max_greens"] = []
	thisGame["edits"] = []
	thisGame["most_recent_edit"] = []
	thisGame["most_recent_new_word"] = []

	thisGame["word_count"] = await defaultValue(args,0,3)
	thisGame["greens_needed_for_an_edit"] = await defaultValue(args,1,2)
	thisGame["grays_needed_for_an_edit"] = await defaultValue(args,2,5)
	thisGame["writing_stage_time"] = await defaultValue(args,3,180)
	thisGame["guessing_stage_time"] = await defaultValue(args,4,60)
	thisGame["allow_hard_words"] = await yesNoValue(args,5,False)
	thisGame["auto_guess"] = await yesNoValue(args,6,True)
	thisGame["show_keyboard"] = await yesNoValue(args,7,True)
	
	thisGame["channel"] = mc
	thisGame["stage"] = 0
	thisGame["timer"] = 0
	thisGame["round_count"] = 0
	thisGame["waiting_messages_to_delete"] = []
	
	thisGame["max_edits"] = 9

	thisGame["won"] = []

	return thisGame

async def defaultValue(arr, index, defi):
	if index >= len(arr):
		return defi
	else:
		return int(arr[index])

async def yesNoValue(arr, index, defi):
	if index >= len(arr):
		return defi
	else:
		return (arr[index] == "y")

pass
# Var definitions
PREFIX = '+'
MILLI = 1000
ZERO = 48
CHAR_CODE_A = 97
frillPiece = ":blue_heart: :purple_heart: :orange_heart: "
frill = frillPiece+frillPiece
skullPiece = ":skull: "
skulls = skullPiece+skullPiece+skullPiece
thought = ":thought_balloon: "
TOKEN = os.environ['TOKEN']

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

f = open('wordlist_1.txt', 'rt')
wordList = f.read().split("\n")
f.close()

f = open('wordlist_0.txt', 'rt')
wordListEasy = f.read().split("\n")
f.close()

intervalFunc = None
stopFlag = False

game = None

# Bot code
@client.event
async def on_ready():
	print(f'We have logged in as {client.user}')
	global game
	game = await newCleanGame("", [])
	
	await client.change_presence(status=discord.Status.idle, activity=None)

@client.event
async def on_message(message):
	global game
	if message.author.bot:
		return
	if type(message.channel) == discord.DMChannel:
		player_index = await getPlayerIndex(message.author)
		if player_index < 0:
			await message.author.send("Sorry! You aren't in the current game.")
		else:
			if game["stage"] == 2:
				wc = game["word_count"]
				if len(game["words"][player_index]) == wc:
					await message.author.send("You submitted enough words already!")
				else:
					await processWritingSubmission(game, player_index, message.content)
					if (await hasEveryoneFinishedWriting(game)):
						await startGuessingStage(game)
			elif game["stage"] == 3:
				if len(message.content) >= 10 and (' ' in message.content):
					await processEditingSubmission(game, player_index, message.content)
				else:
					gc = len(game["guesses"][player_index])
					if gc == game["round_count"]:
						await message.author.send("You've already submitted a guess for this turn! Wait for the turn to finish.")
					else:
						await processGuessingSubmission(game, player_index, message.content)
				if (await hasEveryoneFinishedGuessing(game)):
					await finishGuessingTurn(game)
		return
	if (not message.content.startswith(PREFIX)) or (message.channel.id == 1015969392565170268):
		return

	args = message.content[len(PREFIX):].split(" ")
	command = args[0].lower()
	args = args[1:]
	if command == 'ping':
		await message.channel.send("PONG!!! ")
	elif command == 'getreply':
		await message.author.send("Here is your reply")
	elif command == 'help':
		await message.channel.send(
f"""Commands:```
{PREFIX}help
	Show this help text
{PREFIX}instructions
	Show the instructions
{PREFIX}create [word count] [greens for edit] [grays for edit] [write time] [guess time] [hard words] [auto guess] [keyboard]
	Create a new game
{PREFIX}join
	Join a starting game
{PREFIX}start
	Start the game
{PREFIX}abort
	Abort the current game```
"""
		)
	elif command == 'instructions':
		await message.channel.send(files=[
			discord.File('instructionsA.png'),
			discord.File('instructionsB.png'),
			discord.File('instructionsC.png'),
			discord.File('instructionsD.png')
		])
	elif game["stage"] >= 1:
		if message.channel == game["channel"]:
			await handleGameMessage(message)
		else:
			await message.channel.send("There's a WordleEdit game going on in a different channel right now. Please wait for that to finish first.")
	elif command == 'create':
		game = await newCleanGame(message.channel, args)
		game["stage"] = 1
		await message.channel.send(await announceStringOf(game,1))

client.run(TOKEN)
