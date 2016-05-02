import os
import SimpleAudio as SA
import argparse
import nltk
import wave
from nltk.corpus import cmudict
import re
import time
from contextlib import closing

# default output file (if temporary)
OUTFILE = "output.wav"

# For logging, since it's not allowed to import logging
class color:
   PURPLE = '\033[95m'
   CYAN = '\033[96m'
   DARKCYAN = '\033[36m'
   BLUE = '\033[94m'
   GREEN = '\033[92m'
   YELLOW = '\033[93m'
   RED = '\033[91m'
   BOLD = '\033[1m'
   UNDERLINE = '\033[4m'
   END = '\033[0m'

### NOTE: DO NOT CHANGE ANY OF THE EXISITING ARGUMENTS
parser = argparse.ArgumentParser( description='A basic text-to-speech app that synthesises an input phrase using monophone unit selection.')

parser.add_argument('--monophones', default="monophones", help="Folder containing monophone wavs")

parser.add_argument('--play', '-p', action="store_true", default=False, help="Play the output audio")

parser.add_argument('--outfile', '-o', default = None, action="store", dest="outfile", type=str,
					 help="Save the output audio to a file",)

parser.add_argument('phrase', nargs='+', help="The phrase to be synthesised")

# Arguments for extensions
parser.add_argument('--spell', '-s', action="store_true", default=False,
					help="Spell the phrase instead of pronouncing it")

parser.add_argument('--volume', '-v', default=0.5, type=float,
					help="A float between 0.0 and 1.0 representing the desired volume")

parser.add_argument('--encoding', '-e', default=16000, type=int,
					help="A integer representing the desired output encoding rate")

args = parser.parse_args()

	
class Synth(object):
	def __init__(self, wav_folder):
		print "Synth:__init: Loading wavs..."
		self.phones = self.get_wavs(wav_folder)
		print "Synth:__init__: Initializing cmudict..."
		self.transcr = nltk.corpus.cmudict.dict()
		print "Synth:__init__: Finished initialization."
		
	def get_wavs(self, wav_folder):
		print "Synth:get_wavs: Initializing"
		shpfile = []
		ret = {}
		print "Synth:get_wavs: Iterating wav folder " + wav_folder
		try:
			for root, dirs, files in os.walk(wav_folder, topdown=False):
				shpfile.extend(x for x in files if os.path.splitext(os.path.basename(x))[1] == ".wav" )
			print "Synth:get_wavs: Done. Found " + str(len(files)) + " wav files."
			print "Synth:get_wavs: Added files to index... ", 
			for item in	 shpfile:
				ret[item.split('.')[0]] = os.path.join( wav_folder, item)
			print "done."
			return ret
		except UnboundLocalError as e:
			# Create directory?
			if not os.path.exists(wav_folder):
				raise Exception("Specified monophones %s directory doesn't exist. [Exception - %s ]" % (wav_folder, str(e)))
			raise
		finally:
			pass

	#@staticmethod
	def get_phone_seq(self, text):
		print "Synth:get_phone_seq: Seeing if everything matches:"
		try:
			get_pron =[self.transcr[w][0] for w in self.normalize(text)] #list of lists of pronunciations
		except Exception as e:
			raise Exception("CRITICAL: The word %s hasn't a match in cmudict. You can use -s to have it spelled" % text)

		phone_seq = [str(phone).lower() for phone in sum(get_pron,[])] #list of lowercase phones in sequence
		clear_phones = []
		for entry in phone_seq:
			clear_phones.append(''.join([i for i in entry if not i.isdigit()]))
		print "Synth:get_phone_seq: Done. Cleared list of candidates:", clear_phones
		return clear_phones

	def normalize(self, text):
		print "Synth:normalize: Tokenizing text "
		normalized_phrase = []
		tokenizer = nltk.tokenize.RegexpTokenizer(r'\w+')
		tokenized_text = tokenizer.tokenize(text)
		normalized_txt = [w.lower() for w in tokenized_text]
		print "Synth:normalize: Done tokenizing text. Tokens: ", normalized_txt
		return normalized_txt

	def clean_phrase(self, phrase):
		print "Synth:speak: Cleaning phrase "
		normalized_phrase = []
		pattern = "(.*)" 
		regex = re.compile(pattern)
		# This regex took two hours. Here we allow through:
		# - alphanumeric
		# - trailing dots and commas, after numbers and dates too
		# - dots inside numbers
		# - slashes inside numbers
		sanitized_phrase = [y.groups()[0] for y in [re.match(r"^((\w+|(\d+([./]\d+)*))[,.]?)\.*$", x) for x in phrase] if y]
		print "Synth:speak: Cleaned phrase :", sanitized_phrase
		for n in sanitized_phrase:
			print "Synth:clean:phrase: ", n
			if regex.match(n):
				print "Synth:clean:phrase: Yes it is!", n
				print "Synth:clean:phrase: Now, is it a number? ", n
				if re.compile("^\d+(.\d+)?[,.]?$").match(n):
					print "Synth:clean:phrase: Yes, %s it is a number " %n
					# This needs to be fixed not to allow for /
					if re.compile("\d+([.]\d+)*").match(n):
						print "Synth:clean:phrase: Looks like it matches the format for a number (Decimal or not)"
						if not n.endswith('.') and not n.endswith(','):
							print "Synth:clean:phrase: Oh, and this one is a natural!", n
							result = self.normalize_number(n)
							print "Synth:clean:phrase: Allrighty, got it as ", result
							for item in result:
								normalized_phrase.append(item)
						else:
							print "Synth:clean:phrase: Allright, you got a point (or a comma). Dealing with that...", n
							number = n[:-1]
							result = self.normalize_number(number)
							result[-1] += n[-1:]
							for item in result:
								normalized_phrase.append(item)
							print "Synth:clean:phrase: Okay, dealt with that and preserved the %s at the end of %s" % (n[-1:], result[-1])
				# This needs to be adjusted to ONLY let one or two / in between numbers, with an optional traling comma or dot
				elif re.compile(r"\d+[/]?").match(n):
					print n, " matches a date!"
					# you gotta do this
					processed_date = self.normalize_date(n)
					normalized_phrase.append(processed_date)
				# In any other case the token is valid, but just a word. So let's go ahead and add it.
				else:
					print "Synth:clean:phrase: No, it is not a number. Adding '", n, "'"
					normalized_phrase.append(n)
			else:
				"Synth:clean:phrase: %s is not a valid value. Next!" % n
				pass
		return normalized_phrase


	def normalize_date(self, text):
		# TODO: This probably needs some adjustment
		t = time.strptime(text, "%d %b %y")
		tt = t.strftime('%A %d %B %Y')
		# Chiamata ricorsiva
		return clean_phrase(tt)


	def get_spelling(self, text):
		characters = []
		for char in text:
			characters.append(char.split())
		spell = " ".join(sum(characters,[]))
		letters_as_phones = self.get_phone_seq(spell)
		return letters_as_phones

	def get_silence(self, encoding, duration = 1):
		x = '\x00' * int(encoding * duration) 
		print "Synth:get_silence: Silence length in frames: ", len(x)
		print "Synth:get_silence: ", duration, " seconds at ", encoding, " encoding "
		return x

	def speak(self, phrase, encoding, outfile_name, spelling = False):
		print "Synth:speak: Checking that i got something... "
		if not phrase or phrase == [""]: # TODO (less important): add regex to cover spaces too when you invoke with synth.py " " 
			print "Synth: Looks like I got nothing"
			return None

		print "Synth:speak: Allright, I have been invoked with these parameters: ", phrase
		ret = []
		outdir = ""
		tmpdir = "tmp"
		outfile = os.path.join(outdir, outfile_name)
		print "Synth:speak: Outfile located at: ", outfile
		print "Synth:speak: Preprocessing..."
		phrase = self.clean_phrase(phrase)
		print "Synth:speak: Preprocessed phrase: " , phrase
		print "Synth:speak: Constructing waveforms"
		for i, word in enumerate(phrase):
			print color.BLUE, "Synth:speak: Processing word: ", word, color.END
			print "Synth:speak: Getting phonems sequence. Did you ask to spell or not?"
			if spelling is True:
				print "Synth:speak: You did. Getting spelling..."
				seq = self.get_spelling(word)
			else:
				print "Synth:speak: You did not. Tokenizing..."
				seq = self.get_phone_seq(word)

			print "Synth:speak: Got sequence as ", seq
			list_waves = [self.phones[monophone] for monophone in seq]
			print "Synth:speak: Getting source waves of sequence and contructing word waveform for word", color.BLUE, word, color.END
			with closing(wave.open(os.path.join(tmpdir, word + '.wav'), 'wb')) as output:
				# find sample rate from first file
				with closing(wave.open(list_waves[0])) as w:
					output.setparams(w.getparams())
				# write each file to output
				for infile in list_waves:
					with closing(wave.open(infile)) as w:
						output.writeframes(w.readframes(w.getnframes()))
				if word.endswith('.'): 
					print "Synth:speak: Word ends with dot, adding 500ms of silence"
					silence = self.get_silence(encoding, .5)
					output.writeframes(silence)
				elif word.endswith(','): 
					print "Synth:speak: Word ends with comma, adding 250ms of silence"
					silence = self.get_silence(encoding, .25)
					output.writeframes(silence)
			ret.append(os.path.join(tmpdir, word + '.wav'))

		print "Synth: now assembling..."	
		with closing(wave.open(outfile, 'wb')) as output:
			# find sample rate from first file
			with closing(wave.open(ret[0])) as w:
				print "Synth: Setting parameters from the first outfile"
				output.setparams(w.getparams())
				print "Found and set these : ", output.getparams()
			# write each file to output
			for infile in ret:
				with closing(wave.open(infile)) as w:
					output.writeframes(w.readframes(w.getnframes()))
					#silence = self.get_silence(encoding, 1 - speed )
					#output.writeframes(silence)

		print "Synth: Written " + str(len(ret)) + " files to " + outfile

		print "Synth: Cleaning up temp files... ",
		for tmpfile in ret:
			try:
				os.remove(tmpfile)
			except:
				# This exception is raised every time a word is repeated (tries to )
				# delete the file twice. Also gotta handle a IO error. Pass for now.
				pass
		print "done."
		print "Synth: RECAP, this file says ->> " + color.BOLD + ' '.join(r for r in phrase) + color.END
		return outfile

	def normalize_number(self, num):
		units = ["", "one", "two", "three", "four",	 "five", 
			"six", "seven", "eight", "nine "]

		teens = ["", "eleven", "twelve", "thirteen",  "fourteen", 
			"fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]

		tens = ["", "ten", "twenty", "thirty", "forty",
			"fifty", "sixty", "seventy", "eighty", "ninety"]

		thousands = ["","thousand", "million",	"billion",	"trillion", ]
		words = []
		if num == 0:
			words.append("zero")
			
		elif re.compile("^\d*[.,]?\d*$").match(num):
			dot = num.index(".")
			number_dec = num[dot+1:]
			integers = num[:dot]
			norm_dec = [normalize_number(i) for i in number_dec]
			norm_int = [normalize_number(i) for i in integers]
			words.append(" ".join(norm_int) +" dot "+ " ".join(norm_dec))
		
		else:
			# %d significa un numero, perche' a questo punto abbiamo un non-decimale
			# e procediamo senza esitazione
			numStr = "%d" % float(num)
			numStrLen = len(numStr)
			groups = (numStrLen + 2) / 3
			numStr = numStr.zfill(groups * 3)
			for i in range(0, groups*3, 3):
				h = int(numStr[i])
				t = int(numStr[i+1])
				u = int(numStr[i+2])
				g = groups - (i / 3 + 1)
				
				if h >= 1:
					words.append(units[h])
					words.append("hundred")
					
				if t > 1:
					words.append(tens[t])
					if u >= 1:
						words.append(units[u])
				elif t == 1:
					if u >= 1:
						words.append(teens[u])
					else:
						words.append(tens[t])
				else:
					if u >= 1:
						words.append(units[u])
				if g >= 1 and (h + t + u) > 0:
					words.append(thousands[g])
		return words

		
if __name__ == "__main__": 
	print "Main:" +	 color.RED + "Speech processor welcomes you." + color.END
	S = Synth(wav_folder=args.monophones)
	out = SA.Audio(rate=args.encoding)
	f = S.speak(args.phrase, args.encoding, args.outfile or OUTFILE, args.spell)
	print color.RED + "Main: File is " + color.END, f
	try:
		if args.play:
			out.load(f)
			out.rescale(args.volume)
			print color.RED, "Main: About to play (Interrupt with ctrl + c)", color.END
			out.play()
	except: 
		print "Main: playback exception."
	finally:
		if not args.outfile:
			print "Main: Removing temporary file... ",
			os.remove(OUTFILE)
			print "done."
	print "Main: Bye!"
