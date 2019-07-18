
import tensorflow as tf
import numpy as np
from collections import Counter
from colored import fg, bg, stylize
import math
import argparse
import yaml
import os.path

from .input.text_util import UNK_ID
from .estimator import get_estimator
from .input import *
from .util import *

import logging
logger = logging.getLogger(__name__)


DARK_GREY = 242
WHITE = 255

BG_BLACK = 232
BG_DARK_GREY = 237

ATTN_THRESHOLD = 0.3


def color_text(text_array, levels, color_fg=True):
	out = []
	for l, s in zip(levels, text_array):
		if color_fg:
			color = fg(int(math.floor(DARK_GREY + l*(WHITE-DARK_GREY))))
		else:
			color = bg(int(math.floor(BG_BLACK + l*(BG_DARK_GREY-BG_BLACK))))
		out.append(stylize(s, color))
	return out



def predict(args, cmd_args):
	estimator = get_estimator(args)

	# Logging setup
	logging.basicConfig()
	tf.logging.set_verbosity(args["log_level"])
	logger.setLevel(args["log_level"])
	logging.getLogger("mac-graph").setLevel(args["log_level"])

	# Info about the experiment, for the record
	tfr_size = sum(1 for _ in tf.python_io.tf_record_iterator(args["predict_input_path"]))
	logger.info(f"Predicting on {tfr_size} input records")

	# Actually do some work
	predictions = estimator.predict(input_fn=gen_input_fn(args, "predict"))
	vocab = Vocab.load(args)

	def print_row(row):
		if p["actual_label"] == p["predicted_label"]:
			emoji = "✅"
			answer_part = f"{stylize(row['predicted_label'], bg(22))}"
		else:
			emoji = "❌"
			answer_part = f"{stylize(row['predicted_label'], bg(1))}, expected {row['actual_label']}"

		
		print(emoji, " ", answer_part)

		for control_head in row["question_word_attn"]:
			print("Question: ", ' '.join(color_text(row["src"], control_head)))

		noun = "kb_node"
		db = [vocab.prediction_value_to_string(kb_row) for kb_row in row[f"{noun}s"]]
		print("node extract: ",', '.join(color_text(db, row[f"{noun}_attn"])))

		for idx, attn in enumerate(row[f"{noun}_attn"]):
			if attn > ATTN_THRESHOLD:
				print("property extract: ",', '.join(color_text(
					vocab.prediction_value_to_string(row[f"{noun}s"][idx], True),
					row[f"{noun}_word_attn"],
					)
				))
		


	def decode_row(row):
		for i in ["type_string", "actual_label", "predicted_label", "src"]:
			row[i] = vocab.prediction_value_to_string(row[i], True)

	stats = Counter()
	output_classes = Counter()
	predicted_classes = Counter()
	confusion = Counter()

	for count, p in enumerate(predictions):
		if count > cmd_args["n_rows"]:
			break

		decode_row(p)
		if cmd_args["type_string_prefix"] is None or p["type_string"].startswith(cmd_args["type_string_prefix"]):

			output_classes[p["actual_label"]] += 1
			predicted_classes[p["predicted_label"]] += 1

			correct = p["actual_label"] == p["predicted_label"]

			if correct:
				emoji = "✅"
			else:
				emoji = "❌"

			confusion[emoji + " \texp:" + p["actual_label"] +" \tact:" + p["predicted_label"] + " \t" + p["type_string"]] += 1

			should_print = (cmd_args["correct_only"] and correct) or (cmd_args["wrong_only"] and not correct) or (not cmd_args["correct_only"] and not cmd_args["wrong_only"])

			if should_print:
				print_row(p)
			


if __name__ == "__main__":
	tf.logging.set_verbosity(tf.logging.WARN)

	parser = argparse.ArgumentParser()
	parser.add_argument("--n-rows",type=int,default=20)
	parser.add_argument("--type-string-prefix",type=str,default=None)
	parser.add_argument("--model-dir",type=str,required=True)
	parser.add_argument("--correct-only",action='store_true')
	parser.add_argument("--wrong-only",action='store_true')

	cmd_args = vars(parser.parse_args())

	with tf.gfile.GFile(os.path.join(cmd_args["model_dir"], "config.yaml"), "r") as file:
		frozen_args = yaml.load(file)



	predict(frozen_args, cmd_args)



