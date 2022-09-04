import os
import re
import numpy
import random
import time
import threading
import discord

# Make intervals
class setInterval :
    def __init__(self,interval,action) :
        self.interval=interval
        self.action=action
        self.stopEvent=threading.Event()
        thread=threading.Thread(target=self.__setInterval)
        thread.start()

    def __setInterval(self) :
        nextTime=time.time()+self.interval
        while not self.stopEvent.wait(nextTime-time.time()) :
            nextTime+=self.interval
            self.action()

    def cancel(self) :
        self.stopEvent.set()

pass
# Define funcs
def processWritingSubmission(game, player_index, receivedMessage):
	response = parseSubmittedWord(game, player_index, receivedMessage, game["allow_hard_words"])
	word = response[0]
	_alert = response[1]
	if len(word) == 5:
		game["words"][player_index].append(word)
	game["player_list"][player_index].send(_alert)

async def processGuessingSubmission(game, player_index, receivedMessage):
	response = parseSubmittedWord(game, player_index, receivedMessage, True)
	word = response[0]
	_alert = response[1]
	if len(word) == 5:
		game["guesses"][player_index].append(word)
		if not hasEveryoneFinishedGuessing(game):
			v = await game["player_list"][player_index].send(_alert)
			await game["waiting_messages_to_delete"].append(v)
	else:
		game["player_list"][player_index].send(_alert)

def processEditingSubmission(game, player_index, receivedMessage):
	parts = receivedMessage.split(" ")
	nextI = (player_index+1)%len(game["player_list"])
	wordOn = game["word_on"][nextI]
	origWord = game["words"][player_index][wordOn]
	if parts[0].lower() != origWord:
		game["player_list"][player_index].send("If you're trying to initiate an edit, the first word must be the word your opponent is trying to guess. Right now, that's "+formatWord(origWord,True,False)+".")
		return

	response = parseSubmittedWord(game, player_index, parts[1], game["allow_hard_words"])
	newWord = response[0]
	_alert = response[1]
	if len(newWord) == 5:
		editCost = getEditCost(origWord,newWord)
		if editCost > game["edits"][player_index]:
			game["player_list"][player_index].send("TOO POOR. You only have "+pluralize(game["edits"][player_index],"edit")+" in the bank, but editing your "+rankify(wordOn)+" word from "+formatWord(origWord, True, False)+" to "+formatWord(newWord, True, False)+" would cost you "+pluralize(editCost,"edit")+".")
		else:
			game["words"][player_index][wordOn] = newWord
			game["most_recent_edit"][player_index] = game["round_count"]
			game["edits"][player_index] -= editCost

			appendix = ""
			if game["guesses"][player_index].length < game["round_count"]:
				appendix = "\nDon't forget to write a guess for YOUR word, though!"
			game["player_list"][player_index].send("SUCCESS! Your "+rankify(wordOn)+" word was successfully edited from "+formatWord(origWord, True, False)+" to "+formatWord(newWord, True, False)+"! That cost you "+pluralize(editCost,"edit")+", leaving you with "+pluralize(game["edits"][player_index],"edit")+" left."+appendix)
	else:
		game["player_list"][player_index].send(_alert)

def getEditCost(a, b):
	count = 0
	for i in range(5):
		if a[i] == b[i]:
			count += 1
	return count

def pluralize(n, stri):
	if n == 1:
		return str(n)+" "+stri
	return str(n)+" "+stri+"s"

def hasEveryoneFinishedWriting(game):
	LEN = len(game["player_list"])
	for i in range(LEN):
		if game["words"][i].length < game["round_count"]:
			return False
	return True

def hasEveryoneFinishedGuessing(game):
	LEN = len(game["player_list"])
	for i in range(LEN):
		if game["guesses"][i].length < game["round_count"]:
			return False
	return True

def getPlayerIndex(author):
	LEN = len(game["player_list"])
	for i in range(LEN):
		if game["player_list"][i] == author:
			return i
	return -1

def parseSubmittedWord(game, player_index, message, allow_hard_words):
	word = re.sub(r'[^a-z]', '', message.lower())
	if word.length < 5:
		return ["", "That word isn't long enough"]
	else:
		word = word[0:5]
		thisWordList = wordList if allow_hard_words else wordListEasy
		if word in thisWordList:
			_alert = ""
			if game["stage"] == 2:
				wordCountSoFar = len(game["words"][player_index])
				_alert = "Word #"+str(wordCountSoFar+1)+" of "+str(game["word_count"])+" succesfuly received as "+formatWord(word, True, False)
				if wordCountSoFar == game["word_count"]-1:
					_alert += ". You submitted all your words."
			elif game["stage"] == 3:
				guessCount = len(game["guesses"][player_index])
				_alert = "Guess # "+str(guessCount+1)+" successfully received as "+formatWord(word, True, False)+". Waiting for the round to finish."
			return [word, _alert]
		else:
			return ["","That word isn't in Wordle's dictionary, try again."]

def getCode(guess, answer):
	LEN = 5

	guessArr = [None, None, None, None, None]
	answerArr = [None, None, None, None, None]
	result = [None, None, None, None, None]
	for pos in range(LEN):
		guessArr[pos] = ord(guess[pos])-CHAR_CODE_A
		answerArr[pos] = ord(answer[pos])-CHAR_CODE_A
		result = 0

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

def handleGameMessage(message):
	mc = message.channel
	args = message.content[len(PREFIX):].split(" ")
	command = args[0].lower()
	author = message.author
	if command == 'join':
		if game["stage"] == 1:
			if author in game["player_list"]:
				mc.send(author.username+", you're already in this game. Don't try to join twice.")
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

				mc.send(author.username+" just joined the game. "+
					"\nPlayer count: "+str((lengame["player_list"])))
		else:
			mc.send("It's the wrong stage of game for that.")
	elif command == 'start':
		if game["stage"] == 1:
			PLAYER_COUNT = len(game["player_list"])
			if PLAYER_COUNT < 1:
				mc.send("There are only "+str(PLAYER_COUNT)+" players. Not enough.")
			else:
				startGame(game, args)
		else:
			mc.send("It's the wrong stage of game for that.")
	elif command == 'create':
		mc.send("It's the wrong stage of game for that.")
	elif command == 'abort':
		abort(game, "This WordleEdit game has been aborted.")
		game["stage"] = 0

def abort(game, message):
	if intervalFunc != None:
		deleteMessages(game, "timer_messages_to_edit")
		intervalFunc.cancel()
		intervalFunc = None
	alertChannelAndPlayers(game, message)

def alertChannelAndPlayers(game, stri):
	game["channel"].send(stri)
	LEN = len(game["player_list"])
	for i in range(LEN):
		game["player_list"][i].send(stri)

def startGame(game, args):
	mc = game["channel"]
	game["stage"] = 2
	mc.send(frill+" **STARTING THE WORDLEEDIT GAME NOW!** "+frill)
	mc.send(announceStringOf(game,2)+"\nPlayers, go into your DMs with this bot to play the remainder of this game.")

	game["timer"] = game["writing_stage_time"]
	game["timer_messages_to_edit"] = []

	setTimersAndMessagePlayerList(game)

	def setUpInterval():
		updateAllTimers(game)
		if game["timer"] <= 0:
			wrapUpWritingStageBecauseTimeRanOut(game)
			startGuessingStage(game)
	
	intervalFunc = setInterval(setUpInterval, 2000)

def wrapUpWritingStageBecauseTimeRanOut(game):
	LEN = len(game["player_list"])
	wc = game["word_count"]

	for p_i in range(LEN):
		swc = len(game["words"][p_i])
		pc = game["player_list"][p_i]

		if swc == wc:
			pc.send("Congrats! You submitted all your words on time.")
		else:
			rwc = wc-swc
			messageString = "You only submitted "+pluralize(swc,"word")+" on time. So, the final "+pluralize(rwc,"word")+" have been randomly chosen by the bot (me) to be:"
			for w_i in range(rwc):
				word = getRandomWord(game)
				messageString += "\n"+formatWord(word, True, False)
				game["words"][p_i].append(word)
			pc.send(messageString)

def deleteMessages(game, list):
	LEN = len(game[list])
	for i in range(LEN):
		m = game[list][i]
		if m != None:
			game[list].remove(m)
	game[list] = []

def startGuessingStage(game):
	deleteMessages(game, "timer_messages_to_edit")
	intervalFunc.cancel()
	intervalFunc = None

	game["stage"] = 3
	game["round_count"] = 1
	alertChannelAndPlayers(game, "All players have submitted their words. Time for the guessing stage to begin.")

	startGuessingTurn(game)

def startGuessingTurn(game):
	game["timer"] = game["guessing_stage_time"]
	game["timer_messages_to_edit"] = []

	setTimersAndMessagePlayerList(game)

	def setUpInterval():
		updateAllTimers(game)
		if game["timer"] <= 0:
			finishGuessingTurn(game)
	intervalFunc = setInterval(setUpInterval, 2000)

def getRandomWord(game):
	thisGamesWordList = wordList if game["allow_hard_words"] else wordListEasy
	choice = numpy.floor(random.random()*thisGamesWordList.length)
	return thisGamesWordList[choice]

def countGreens(code):
	count = 0
	for i in range(len(code)):
		if chr(code[i]) == 2 + CHAR_CODE_A:
			count += 1
	return count

def calculatePlayersRoundPerformance(game, p_i, r, LEN):
	pgc = len(game["guesses"][p_i])
	pc = game["player_list"][p_i]
	if pgc < game["round_count"]:
		if game["auto_guess"]:
			word = getRandomWord(game)
			game["guesses"][p_i].append(word)
			pc.send("You didn't guess in time. So, your guess will be randomly chosen by the bot (me) to be:\n"+formatWord(word, True, False))
		else:
			word = "*****"
			game["guesses"][p_i].append(word)
			pc.send("You didn't guess in time, so we're going to skip your turn! Better luck next time.")
			
	prevI = (p_i+LEN-1)%LEN
	wordOn = game["word_on"][p_i]
	guess = game["guesses"][p_i][r]
	answer = game["words"][prevI][wordOn]
	code = getCode(guess, answer)
	game["codes"][p_i].append(code)

	greenCount = countGreens(code)
	diff = greenCount-game["max_greens"][p_i]

	if diff > 0:
		if diff >= game["greens_needed_for_an_edit"]:
			game["edits"][p_i] = numpy.min(game["edits"][p_i]+1,game["max_edits"])
		game["max_greens"][p_i] = greenCount

	if countLetters(code, 'a') >= game["grays_needed_for_an_edit"]:
		prevI = (p_i+LEN-1)%LEN
		game["edits"][prevI] = numpy.min(game["edits"][prevI]+1,game["max_edits"])

def countLetters(stri, ch):
	count = 0
	for i in len(stri):
		if stri[i] == ch:
			count += 1
	return count

def finishGuessingTurn(game):
	r = game["round_count"]-1
	LEN = len(game["player_list"])
	for p_i in range(LEN):
		calculatePlayersRoundPerformance(game, p_i, r, LEN)
	deleteMessages(game, "timer_messages_to_edit")
	deleteMessages(game, "waiting_messages_to_delete")

	game["channel"].send(formatRoundResult(game, r, -1))
	for p_i in range(LEN):
		game["player_list"][p_i].send(formatRoundResult(game, r, p_i))

	finishers = []
	for p_i in range(LEN):
		if game["codes"][p_i][r] == "ccccc":
			prevI = (p_i+LEN-1)%LEN
			prevP = game["player_list"][prevI]
			wordOn = game["word_on"][p_i]
			if wordOn >= game["word_count"]-1:
				finishers.append(p_i)
			if game["word_on"][p_i] < game["word_count"]-1:
				game["player_list"][p_i].send("Congrats, you solved "+prevP.username+"'s "+rankify(wordOn)+" word! Guess their "+	rankify(wordOn+1)+" one.")

	game["word_on"][p_i] += 1
	game["max_greens"][p_i] = 0
	game["most_recent_new_word"][p_i] = r+1

def getTiedString(game, finishers, exclude):
	tiedString = ""
	for f_j in range(len(finishers)):
		if f_j != exclude:
			tiedString += game["player_list"][finishers[f_j]].username+" and "
	return tiedString.substring(0,tiedString.length-5)

def formatRoundResult(game, round_i, player_i):
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
		p_i = pseudo_i
		if player_i >= 0:
			p_i = (pseudo_i+player_i)%LEN
		prevI = (p_i+LEN-1)%LEN
		tile = black
		if game["most_recent_edit"][prevI] == game["round_count"]:
			tile = boom
		wordOn = game["word_on"][p_i]

		guesses_string += tile+puzzle+formatWord(game["guesses"][p_i][round_i], True, True)+pencil+tile
		w = (game["word_on"][p_i]+1)%10
		e = game["edits"][p_i]%10
		codes_string += tile+formatNumber(w)+formatCode(game["codes"][p_i][round_i], True, True)+formatNumber(e)+tile

		truth_piece = questWord
		if player_i == prevI or game["codes"][p_i][round_i] == "ccccc":
			truth_piece = formatWord(game["words"][prevI][wordOn], True, True)
		truth_string += tile+tile+truth_piece+tile+tile

	if player_i >= 0 and game["show_keyboard"]:
		remainingCharacters = getRemainingCharacters(game, player_i)
		
		rows = [None] * 3
		for i in range(3):
			rows[r] = black+black+black+thought
		perRow = python.ceil(len(remainingCharacters)/3)

		for ch_i in range(len(remainingCharacters)):
			ch = remainingCharacters[ch_i]
			character_block = formatLetter(ch)
			row = numpy.floor(ch_i/perRow)
			rows[row] += character_block
		guesses_string += rows[0]
		codes_string += rows[1]
		truth_string += rows[2]

	result = ""
	if player_i >= 0:
		result += playerListToString(game, player_i)+"\n"
	elif round_i == 0:
		result += playerListToString(game, 0)+"\n"
	result += guesses_string+"\n"+codes_string
	if player_i >= 0:
		result += "\n"+truth_string
	return result

def getRemainingCharacters(game, player_i):
	LEN = len(game["player_list"])
	remainingCharacterIndices = [True] * 26
	prevI = (player_i+LEN-1)%LEN

	firstUsefulRound = numpy.max(game["most_recent_edit"][prevI],game["most_recent_new_word"][player_i],0)

	for round in range(firstUsefulRound, round < game["round_count"]):
		guess = game["guesses"][player_i][round]
		code = game["codes"][player_i][round]
		for i in range(5):
			if code[i] == 'a':
				DQedLetter = guess[i]-CHAR_CODE_A
				remainingCharacterIndices[DQedLetter] = False
		for i in range(5):
			if code[i] != 'a':
				approvedLetter = guess[i]-CHAR_CODE_A
				remainingCharacterIndices[approvedLetter] = True

	remainingCharacters = []
	for i in range(26):
		if remainingCharacterIndices[i]:
			remainingCharacters.append(chr(i + CHAR_CODE_A))
	return remainingCharacters

def updateAllTimers(game):
	game["timer"] -= 2
	if game["timer"] >= 2:
		editedStri = formatTime(game["timer"])
		LEN = len(game["timer_messages_to_edit"])
		for i in range(LEN):
			mess = game["timer_messages_to_edit"][i]
			if mess != None:
				mess.edit(editedStri)

async def setTimersAndMessagePlayerList(game):
	v = await game["channel"].send(formatTime(game["timer"]))
	await game["timer_messages_to_edit"].append(v)

	LEN = len(game["player_list"])
	for i in range(LEN):
		prevI = (i+LEN-1)%LEN
		nextI = (i+1)%LEN
		p = game["player_list"][i]
		nextP = game["player_list"][nextI]
		prevP = game["player_list"][prevI]

		if game["stage"] == 2:
			game["player_list"][i].send("Hello, "+p.username+"! In this WordleEdit game, you are Player #"+(i+1)+" of "+LEN+". Please type "+pluralize(game["word_count"], "word")+" for Player #"+(nextI+1)+" ("+nextP.username+") to guess.")
		elif game["stage"] == 3 and game["round_count"] == 1:
			wordOn = game["word_on"][i]
			game["player_list"][i].send("Please guess "+prevP.username+"'s "+rankify(wordOn)+" word.")

		w = await game["player_list"][i].send(formatTime(game["timer"]))
		await game["timer_messages_to_edit"].append(w)

def rankify(n):
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

def playerListToString(game, indexShift):
	RESULT_STR = ""
	LEN = len(game["player_list"])
	for i in range(LEN):
		if i == 1 and LEN == 2:
			RESULT_STR += "   <--->   "
		else:
			if i >= 1:
				RESULT_STR += "   ---->   "
		if i == game["position"]:
			RESULT_STR += ":arrow_right:"
		RESULT_STR += game["player_list"][(i-indexShift+LEN)%LEN].username
		return RESULT_STR

def formatWord(word, emojify, finalSpace):
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

def formatLetter(ch):
	return ":regional_indicator_"+ch+": "

def formatCode(code, emojify, finalSpace):
	if emojify:
		emojis = [":white_large_square:",":yellow_square:",":green_square:",":green_heart:"]
		result = ""
		for i in range(5):
			if code == "ccccc":
				result += emojis[3]
			else:
				result += emojis[chr(code[i])-CHAR_CODE_A]
			if finalSpace or i < 4:
				result += " "
		return result
	else:
		return code.upper()

def formatTime(timer):
	return "Time left: "+formatNumber(timer)

def formatNumber(number):
	sNumber = str(number)+""
	numberNames = ["zero","one","two","three","four","five","six","seven","eight","nine"]
	LEN = len(sNumber)
	result = ""
	for i in range(LEN):
		result += ":"+numberNames[chr(sNumber[i])-ZERO]+": "
	return result

def announceStringOf(game,stage):
	ANNOUNCE_STR = "We're creating a brand new game of WordleEdit!"
	if stage == 1:
		ANNOUNCE_STR += "\nType \"!join\" to join this game."
	elif stage == 2:
		ANNOUNCE_STR += "\n\nPlayer list: "
		for p in game["player_list"]:
			ANNOUNCE_STR += "\n"+p.username
	return ANNOUNCE_STR

def newCleanGame(mc, args):
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

	thisGame["word_count"] = defaultValue(args,0,3)
	thisGame["greens_needed_for_an_edit"] = defaultValue(args,1,2)
	thisGame["grays_needed_for_an_edit"] = defaultValue(args,2,5)
	thisGame["writing_stage_time"] = defaultValue(args,3,180)
	thisGame["guessing_stage_time"] = defaultValue(args,4,60)
	thisGame["allow_hard_words"] = yesNoValue(args,5,False)
	thisGame["auto_guess"] = yesNoValue(args,6,True)
	thisGame["show_keyboard"] = yesNoValue(args,7,True)
	
	thisGame["channel"] = mc
	thisGame["stage"] = 0
	thisGame["timer"] = 0
	thisGame["round_count"] = 0
	thisGame["waiting_messages_to_delete"] = []
	
	thisGame["max_edits"] = 9

	return thisGame

def defaultValue(arr, index, defi):
	if index >= len(arr):
		return defi
	else:
		return arr[index]

def yesNoValue(arr, index, defi):
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
TOKEN = os.environ['token']

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

f = open('wordlist_1.txt', 'rt')
wordList = f.read().split("\r\n")
f.close()

f = open('wordlist_0.txt', 'rt')
wordListEasy = f.read().split("\r\n")
f.close()

intervalFunc = None

game = newCleanGame("", [])

# Bot code
@client.event
async def on_ready():
	print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
	print(game)
	if message.author.bot:
		return
	if type(message.channel) == discord.DMChannel:
		player_index = getPlayerIndex(message.author)
		if player_index < 0:
			message.author.send("Sorry! You aren't in the current game.")
		else:
			if game["stage"] == 2:
				wc = game["word_count"]
				if len(game["words"][player_index]) == wc:
					message.author.send("You submitted enough words already!")
				else:
					processWritingSubmission(game, player_index, message.content)
					if hasEveryoneFinishedWriting(game):
						startGuessingStage(game)
			elif game["stage"] == 3:
				if message.content.length >= 10 and message.content.includes(' '):
					processEditingSubmission(game, player_index, message.content)
				else:
					gc = game["guesses"][player_index].length
					if gc == game["round_count"]:
						message.author.send("You've already submitted a guess for this turn! Wait for the turn to finish.")
					else:
						processGuessingSubmission(game, player_index, message.content)
						if hasEveryoneFinishedGuessing(game):
							finishGuessingTurn(game)
		return
	elif not message.content.startswith(PREFIX):
		return

	args = message.content[len(PREFIX):].split(" ")
	command = args[0].lower()
	if command == 'ping':
		await message.channel.send("PONG!!! ")
	elif command == 'getreply':
		await message.author.send("Here is your reply")
	elif game["stage"] >= 1:
		if message.channel == game["channel"]:
			handleGameMessage(message)
		else:
			message.channel.send("There's a WordleEdit game going on in a different channel right now. Please wait for that to finish first.")
	elif command == 'create':
		game = newClearGame(message.channel, args)
		game["stage"] = 1
		message.channel.send(announceStringOf(game,1))

client.run(TOKEN)
