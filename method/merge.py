# Merge the adjudicated documents into trials.csv, dataset.csv and qa/decisions.csv, and print the round numbers for RODADA.md
# Usage: python -X utf8 method/merge.py   (paths are relative to the brusone-arroz folder)
# Copied from doencas-feijao/method/merge.py. Changed for schema v4: field names, table-level labels inherited into the
# dataset (inherited_from_table says which), errors split into trial context, table labels, inventory, checklist and records,
# optional one-sided records and tables read from the decision (both_acceptable), and records both sides missed
# Copied from mandioca/method/merge.py for the rice blast round (schema v5). Changed: crop_stage and crop_stage_refers_to
# inherited from the table too, compared field counts read from compare.py, rows checklist, trial fields of v5
# (crop_system, sowing_date, biotic_target), and the cascade comparison is now against the cassava round
import csv
import glob
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "method"))
import compare  # noqa: E402  only for the compared field lists
MAX_QUOTE_WORDS = 15
COMPARED_RECORD_FIELD_COUNT = len(compare.COMPARED_FIELDS)  # value also covers value_as_printed
COMPARED_TRIAL_FIELD_COUNT = len(compare.TRIAL_FIELDS)
COMPARED_TABLE_FIELD_COUNT = len(compare.TABLE_FIELDS) + len(compare.LABEL_FIELDS)
LICENSE_REPOSITORY = "CC BY-NC-ND 4.0 (aviso geral do repositório {repo}, não é licença do item)"

# Free-text fields that may carry copied source text
TRIAL_TEXT_FIELDS = ["trial_label", "location", "inoculation_or_infestation", "application_method", "application_stages",
	"spacing_or_density", "design_notes", "source_inconsistency", "notes"]
RECORD_TEXT_FIELDS = ["notes", "source_inconsistency", "transformation_stated", "crop_stage", "application_stages", "dose_and_unit"]
LABEL_TEXT_FIELDS = ["letters_meaning", "scale_meaning", "source_inconsistency", "transformation_stated", "significance_test", "crop_stage"]
DECISION_TEXT_COLUMNS = ["a_value", "b_value", "final_value", "evidence"]

# Record fields that are also table-level labels: null on the record means "as the table"
INHERITED_LABEL_FIELDS = ["statistic", "statistic_stated", "transformation_stated", "treatment_type", "crop_stage", "crop_stage_refers_to"]
# Table labels with no record field, copied to the dataset so the letters and scores can be read
EXTRA_LABEL_COLUMNS = {"significance_test": "significance_test", "letters_meaning": "letters_meaning",
	"scale_meaning": "scale_meaning", "source_inconsistency": "table_source_inconsistency"}

# Quotes: 'x', "x", ‘x’, “x”. The single quote must not touch a letter, so "B's" is not a quote
QUOTE_PATTERN = re.compile(r"(?<![\w])'([^']{3,}?)'(?![\w])|\"([^\"]{3,}?)\"|‘([^’]+)’|“([^”]+)”")

TABLE_FIELDS = {"kind", "trial_ids", "data_cells", "transcribed", "skipped_cells", "table", "table_id"}
CROP_STAGE_FIELDS = {"crop_stage", "crop_stage_refers_to", "crop_stage_source_page"}
ROW_IDENTITY_FIELDS = {"treatment", "treatment_code", "cultivar", "is_marginal", "row_identity"}
VALUE_FIELDS = {"value", "value_as_printed", "significance_letter", "unit"}
CLASSIFICATION_FIELDS = {"statistic", "statistic_stated", "transformation_stated", "treatment_type", "source_inconsistency"}


def NormalizeWord(word):
	return re.sub(r"^[^\w]+|[^\w]+$", "", word.lower())


def LoadPdfWordShingles(pdf_path):
	# Text layer of the whole PDF, with line-break hyphens joined, as a set of 16-word sequences
	pdf_text = subprocess.run(["pdftotext", "-enc", "UTF-8", pdf_path, "-"], capture_output=True).stdout.decode("utf-8", "replace")
	pdf_text = re.sub(r"-\s*\n\s*", "", pdf_text)
	pdf_words = [NormalizeWord(word) for word in pdf_text.split()]
	pdf_words = [word for word in pdf_words if word]
	shingle_size = MAX_QUOTE_WORDS + 1
	return {tuple(pdf_words[index:index + shingle_size]) for index in range(len(pdf_words) - shingle_size + 1)}


def LongestCopiedRun(text, pdf_shingles):
	# Returns (start, end) word positions of copied runs longer than the limit, on the whitespace-split text
	words = text.split()
	normalized = [NormalizeWord(word) for word in words]
	shingle_size = MAX_QUOTE_WORDS + 1
	runs = []
	index = 0
	while index + shingle_size <= len(words):
		if tuple(normalized[index:index + shingle_size]) in pdf_shingles and "" not in normalized[index:index + shingle_size]:
			run_end = index + shingle_size
			while run_end < len(words) and tuple(normalized[run_end - shingle_size + 1:run_end + 1]) in pdf_shingles:
				run_end += 1
			runs.append((index, run_end))
			index = run_end
		else:
			index += 1
	return runs


def ShortenQuote(match):
	quoted_text = next(group for group in match.groups() if group)
	words = quoted_text.split()
	if len(words) <= MAX_QUOTE_WORDS:
		return match.group(0)
	# Keep the start and the end, where the number usually is
	shortened = " ".join(words[:7]) + " (...) " + " ".join(words[-6:])
	return match.group(0)[0] + shortened + match.group(0)[-1]


def ShortenText(text, pdf_shingles, counter, counter_key):
	if not isinstance(text, str) or not text:
		return text
	new_text = QUOTE_PATTERN.sub(ShortenQuote, text)
	runs = LongestCopiedRun(new_text, pdf_shingles)
	if runs:
		words = new_text.split()
		# Cut from the last run backwards so the positions of the earlier runs stay right
		for run_start, run_end in reversed(runs):
			words[run_start + 7:run_end - 6] = ["(...)"]
		new_text = " ".join(words)
	if new_text != text:
		counter[counter_key] += 1
	return new_text


def BuildCitation(document):
	authors = "; ".join(document["authors"]).rstrip(".")
	title = document["title"].rstrip(".")
	reference = document["journal_article"] or document["citation"]
	return f"{authors}. {title}. {reference} Disponível em: {document['record_url']}"


def BuildLicense(document):
	license_text = LICENSE_REPOSITORY.format(repo=document["repository"])
	if document.get("publisher_copyright_in_pdf"):
		license_text += "; o PDF imprime: " + document["publisher_copyright_in_pdf"]
	if document.get("journal_article"):
		license_text += "; artigo de periódico, valem os termos da revista (não conferidos)"
	elif "anais" in document["type"].lower():
		license_text += "; trabalho em anais, valem os termos do evento (não conferidos)"
	return license_text


def DecisionIds(record):
	ids = record.get("decision_ids")
	if isinstance(ids, list):
		return "; ".join(str(each_id) for each_id in ids)
	return ids or ""


def SideOfError(decision):
	# Which side a decision counts against
	if decision == "B_right":
		return ("A",)
	if decision == "A_right":
		return ("B",)
	if decision == "both_wrong":
		return ("A", "B")
	return ()


def CategoryOf(row):
	# trial context, table label, inventory, end_checklist or record
	field, table_label = row["field"], row["table_or_figure"]
	if table_label == "trials":
		return "trial"
	if table_label == "end_checklist" or row["kind"] == "checklist" or field.startswith(("end_checklist", "context", "footnotes", "rows")):
		return "checklist"
	if field.startswith("table_level_labels."):
		return "label"
	if field in TABLE_FIELDS:
		return "inventory"
	return "record"


def CascadeGroupErrors(decisions_path):
	# Record and label errors per side, grouped by the rule that makes a cascade, for the round comparison
	group_errors = Counter()
	for row in csv.DictReader(open(decisions_path, encoding="utf-8-sig")):
		if CategoryOf(row) not in ("record", "label"):
			continue
		field = row["field"].replace("table_level_labels.", "")
		if field in CLASSIFICATION_FIELDS:
			group = "classification"
		elif field in CROP_STAGE_FIELDS:
			group = "crop_stage"
		elif field in ROW_IDENTITY_FIELDS:
			group = "row_identity"
		elif field == "trial_id":
			group = "trial_id"
		elif field in VALUE_FIELDS:
			group = "value"
		else:
			group = "other"
		for side in SideOfError(row["decision"]):
			group_errors[(side, group)] += 1
	return group_errors


def CellText(value):
	if value is None:
		return ""
	if isinstance(value, (list, dict)):
		return json.dumps(value, ensure_ascii=False)
	return value


def main():
	schema = json.load(open(os.path.join(ROOT, "schema.json"), encoding="utf-8"))
	record_fields = schema["$defs"]["record"]["required"]
	trial_fields = schema["$defs"]["trial"]["required"]
	sources = json.load(open(os.path.join(ROOT, "sources.json"), encoding="utf-8"))
	documents_by_id = {document["id"]: document for document in sources["documents"]}

	shortened = Counter()
	shingles_by_doc = {}
	dataset_rows = []
	trial_rows = []
	stats = defaultdict(dict)
	label_tables = 0
	for adjudicated_path in sorted(glob.glob(os.path.join(ROOT, "adjudicated", "*.json"))):
		doc_id = os.path.basename(adjudicated_path)[:-5]
		document = documents_by_id[doc_id]
		pdf_shingles = LoadPdfWordShingles(os.path.join(ROOT, document["pdf_path"]))
		shingles_by_doc[doc_id] = pdf_shingles
		adjudicated = json.load(open(adjudicated_path, encoding="utf-8"))
		citation, license_text = BuildCitation(document), BuildLicense(document)
		trial_ids = set()
		for trial in adjudicated["trials"]:
			assert all(field in trial for field in trial_fields), (doc_id, trial.get("trial_id"))
			row = {"doc_id": doc_id}
			for field in trial_fields:
				value = trial[field]
				if field in TRIAL_TEXT_FIELDS:
					value = ShortenText(value, pdf_shingles, shortened, "trials." + field)
				row[field] = CellText(value)
			row["citation"] = citation
			trial_rows.append(row)
			trial_ids.add(trial["trial_id"])
		tables_by_id = {table["table_id"]: table for table in adjudicated["tables"]}
		label_tables += sum(1 for table in adjudicated["tables"] if table.get("table_level_labels"))
		for record_number, record in enumerate(adjudicated["records"], start=1):
			# Every schema field must be there, the record belongs to this document and points to one of its trials and tables
			assert all(field in record for field in record_fields), (doc_id, record_number)
			assert record["doc_id"] == doc_id
			assert record["trial_id"] in trial_ids, (doc_id, record_number, record["trial_id"])
			assert record["table_id"] in tables_by_id, (doc_id, record_number, record["table_id"])
			labels = tables_by_id[record["table_id"]].get("table_level_labels") or {}
			row = {"record_id": f"{doc_id}#{record_number:04d}"}
			inherited = []
			for field in record_fields:
				value = record[field]
				# Null on the record means "as the table": write the table value and say so
				if field in INHERITED_LABEL_FIELDS and value is None and labels.get(field) is not None:
					value = labels[field]
					inherited.append(field)
				if field in RECORD_TEXT_FIELDS:
					value = ShortenText(value, pdf_shingles, shortened, "records." + field)
				row[field] = CellText(value)
			for label_field, column in EXTRA_LABEL_COLUMNS.items():
				row[column] = ShortenText(labels.get(label_field), pdf_shingles, shortened, "tables." + label_field) or ""
			row["inherited_from_table"] = "; ".join(inherited)
			row["origin"] = record.get("origin")
			row["decision_ids"] = DecisionIds(record)
			row["citation"] = citation
			row["license"] = license_text
			dataset_rows.append(row)
		stats[doc_id]["final"] = len(adjudicated["records"])
		stats[doc_id]["trials"] = len(adjudicated["trials"])
		stats[doc_id]["tables"] = len(adjudicated["tables"])
		stats[doc_id]["label_tables"] = sum(1 for table in adjudicated["tables"] if table.get("table_level_labels"))

	# trial_id is per document (t1, t2...), so the dataset joins trials.csv on doc_id + trial_id
	record_columns = ["record_id", "doc_id", "trial_id"] + [field for field in record_fields if field not in ("doc_id", "trial_id")]
	record_columns += list(EXTRA_LABEL_COLUMNS.values()) + ["inherited_from_table", "origin", "decision_ids", "citation", "license"]
	with open(os.path.join(ROOT, "dataset.csv"), "w", encoding="utf-8", newline="") as output_file:
		writer = csv.DictWriter(output_file, fieldnames=record_columns)
		writer.writeheader()
		for row in dataset_rows:
			writer.writerow({key: ("" if value is None else value) for key, value in row.items()})
	trial_columns = ["doc_id"] + trial_fields + ["citation"]
	with open(os.path.join(ROOT, "trials.csv"), "w", encoding="utf-8", newline="") as output_file:
		writer = csv.DictWriter(output_file, fieldnames=trial_columns)
		writer.writeheader()
		for row in trial_rows:
			writer.writerow({key: ("" if value is None else value) for key, value in row.items()})

	# Concatenate the decision files, union of columns, evidence quotes cut like the notes
	decision_rows = []
	decision_columns = ["source_file"]
	for decisions_path in sorted(glob.glob(os.path.join(ROOT, "adjudicated", "*_decisions.csv"))):
		for row in csv.DictReader(open(decisions_path, encoding="utf-8-sig", newline="")):
			row["source_file"] = "adjudicated/" + os.path.basename(decisions_path)
			for column in DECISION_TEXT_COLUMNS:
				row[column] = ShortenText(row.get(column), shingles_by_doc[row["doc_id"]], shortened, "decisions." + column)
			for key in row:
				if key not in decision_columns:
					decision_columns.append(key)
			decision_rows.append(row)
	os.makedirs(os.path.join(ROOT, "qa"), exist_ok=True)
	with open(os.path.join(ROOT, "qa", "decisions.csv"), "w", encoding="utf-8", newline="") as output_file:
		writer = csv.DictWriter(output_file, fieldnames=decision_columns)
		writer.writeheader()
		writer.writerows(decision_rows)

	# Per side and per category: field errors, wrong units, omissions, optional and spurious entries
	field_errors_by_side = Counter()
	classification_errors = Counter()
	for doc_id in stats:
		a_document = json.load(open(os.path.join(ROOT, "A", doc_id + ".json"), encoding="utf-8"))
		b_document = json.load(open(os.path.join(ROOT, "B", doc_id + ".json"), encoding="utf-8"))
		doc_stats = stats[doc_id]
		doc_stats.update(a_records=len(a_document["records"]), b_records=len(b_document["records"]),
			a_trials=len(a_document["trials"]), b_trials=len(b_document["trials"]),
			a_tables=len(a_document["tables"]), b_tables=len(b_document["tables"]))
		counts = Counter()
		wrong = {(side, category): set() for side in "AB" for category in ("record", "trial", "label", "inventory", "checklist")}
		for row in decision_rows:
			if row["doc_id"] != doc_id:
				continue
			counts["decision_" + row["decision"]] += 1
			kind, field = row["kind"], row["field"]
			if kind.startswith("only_in") or kind == "missing_in_both":
				unit = field if field in ("trial", "table") else "record"
				if kind == "missing_in_both":
					counts[f"both_{unit}_omitted"] += 1
					counts[f"A_{unit}_omitted"] += 1
					counts[f"B_{unit}_omitted"] += 1
					continue
				present_side = kind[-1]
				missing_side = "B" if present_side == "A" else "A"
				if row["decision"] in (present_side + "_right", "ambiguous_print"):
					counts[f"{missing_side}_{unit}_omitted"] += 1
				elif row["decision"] == missing_side + "_right":
					counts[f"{present_side}_{unit}_spurious"] += 1
				else:
					counts[f"{present_side}_{unit}_optional"] += 1
				continue
			category = CategoryOf(row)
			sides = SideOfError(row["decision"])
			for side in sides:
				counts[f"{side}_{category}_field_errors"] += 1
				# Trial and table rows carry the trial_id or table_id; record rows the record index
				wrong[(side, category)].add(row[side.lower() + "_index"] or row["a_index"] or row["b_index"])
				field_errors_by_side[(side, category, field)] += 1
				if field.replace("table_level_labels.", "") in CLASSIFICATION_FIELDS and category in ("record", "label"):
					classification_errors[(side, category)] += 1
				if category == "record" and field in VALUE_FIELDS:
					counts[f"{side}_value_errors"] += 1
		doc_stats.update(counts)
		for (side, category), units in wrong.items():
			doc_stats[f"{side}_wrong_{category}"] = len(units)
		# Tables with a label or inventory error count once
		for side in "AB":
			doc_stats[f"{side}_wrong_table"] = len(wrong[(side, "label")] | wrong[(side, "inventory")])
		doc_stats["required"] = doc_stats["final"] - counts["A_record_optional"] - counts["B_record_optional"]
		doc_stats["pairs"] = doc_stats["final"] - sum(counts[f"{side}_record_{what}"] for side in "AB" for what in ("optional",)) \
			- counts["A_record_omitted"] - counts["B_record_omitted"] + min(counts["A_record_omitted"], counts["B_record_omitted"])

	totals = Counter()
	print("doc_id;final;required;pairs;trials;tables;A_rec;B_rec;A_wrong_rec;B_wrong_rec;A_omit;B_omit;A_wrong_trial;B_wrong_trial;A_wrong_table;B_wrong_table;A_val;B_val")
	for doc_id, doc_stats in sorted(stats.items()):
		for key, value in doc_stats.items():
			totals[key] += value
		print(f"{doc_id};{doc_stats['final']};{doc_stats['required']};{doc_stats['pairs']};{doc_stats['trials']};{doc_stats['tables']};"
			f"{doc_stats['a_records']};{doc_stats['b_records']};{doc_stats['A_wrong_record']};{doc_stats['B_wrong_record']};"
			f"{doc_stats.get('A_record_omitted', 0)};{doc_stats.get('B_record_omitted', 0)};{doc_stats['A_wrong_trial']};"
			f"{doc_stats['B_wrong_trial']};{doc_stats['A_wrong_table']};{doc_stats['B_wrong_table']};"
			f"{doc_stats.get('A_value_errors', 0)};{doc_stats.get('B_value_errors', 0)}")
	print(dict(sorted(totals.items())))

	# Accuracy per record, trial and table, counting omissions
	required = totals["required"]
	for side in ("A", "B"):
		omitted = totals[side + "_record_omitted"]
		wrong_records = totals[side + "_wrong_record"]
		paired = required - omitted
		record_field_errors = totals[side + "_record_field_errors"]
		print(f"{side} records: right {required - omitted - wrong_records}/{required} = {100 * (required - omitted - wrong_records) / required:.1f}%"
			f" | omitted {omitted} | with error {wrong_records} | spurious {totals[side + '_record_spurious']} | optional {totals[side + '_record_optional']}"
			f" | fields {record_field_errors}/{paired * COMPARED_RECORD_FIELD_COUNT} = {100 * record_field_errors / (paired * COMPARED_RECORD_FIELD_COUNT):.2f}%"
			f" | value/letter/unit errors {totals[side + '_value_errors']}")
		trial_total = totals["trials"]
		trial_omitted = totals[side + "_trial_omitted"]
		wrong_trials = totals[side + "_wrong_trial"]
		trial_field_errors = totals[side + "_trial_field_errors"]
		trial_fields_compared = (trial_total - trial_omitted) * COMPARED_TRIAL_FIELD_COUNT
		print(f"{side} trials: right {trial_total - trial_omitted - wrong_trials}/{trial_total} = {100 * (trial_total - trial_omitted - wrong_trials) / trial_total:.1f}%"
			f" | omitted {trial_omitted} | spurious {totals[side + '_trial_spurious']} | with error {wrong_trials}"
			f" | fields {trial_field_errors}/{trial_fields_compared} = {100 * trial_field_errors / trial_fields_compared:.2f}%")
		table_total = totals["tables"]
		table_omitted = totals[side + "_table_omitted"]
		wrong_tables = totals[side + "_wrong_table"]
		label_errors = totals[side + "_label_field_errors"]
		inventory_errors = totals[side + "_inventory_field_errors"]
		print(f"{side} tables: right {table_total - table_omitted - wrong_tables}/{table_total} = {100 * (table_total - table_omitted - wrong_tables) / table_total:.1f}%"
			f" | omitted {table_omitted} | optional {totals[side + '_table_optional']} | with label error {totals[side + '_wrong_label']} of {totals['label_tables']} labelled"
			f" | label fields {label_errors} | inventory fields {inventory_errors} | checklist fields {totals[side + '_checklist_field_errors']}")
	print("field errors by side:", sorted(field_errors_by_side.items(), key=lambda item: -item[1]))
	print("classification errors (statistic, statistic_stated, transformation, treatment_type, source_inconsistency):", dict(classification_errors))

	value_rows = [row for row in decision_rows if row["field"] in VALUE_FIELDS]
	print("value/letter/unit diff rows:", Counter((row["doc_id"][:20], row["field"], row["decision"]) for row in value_rows))
	print("shortened:", dict(shortened))
	print("decision rows:", len(decision_rows), Counter(row["decision"] for row in decision_rows))
	print("origin:", Counter(row["origin"] for row in dataset_rows))
	print("variable_standardized:", Counter(row["variable_standardized"] for row in dataset_rows).most_common())
	print("other by doc:", Counter(row["doc_id"] for row in dataset_rows if row["variable_standardized"] == "other"))
	print("other variables:", Counter(row["variable"][:50] for row in dataset_rows if row["variable_standardized"] == "other").most_common(40))
	print("biotic_target:", Counter(row["biotic_target"] for row in dataset_rows).most_common())
	print("treatment_type:", Counter(row["treatment_type"] for row in dataset_rows).most_common())
	print("statistic:", Counter(row["statistic"] for row in dataset_rows).most_common())
	print("value_kind:", Counter(row["value_kind"] for row in dataset_rows).most_common())
	print("inherited:", Counter(field for row in dataset_rows for field in row["inherited_from_table"].split("; ") if field))
	for field in ("cultivar", "dose_and_unit", "application_stages", "crop_stage", "significance_letter", "active_ingredient_or_input", "dispersion_as_printed"):
		empty = sum(1 for row in dataset_rows if row[field] in (None, ""))
		print(f"null record {field}: {empty} ({100 * empty / len(dataset_rows):.1f}%)")
	for field in ("location", "affiliation", "season_or_year", "sowing_date", "crop_system", "biotic_target", "cultivar", "inoculation_or_infestation",
			"application_method", "application_stages", "spacing_or_density", "n_reps"):
		empty = sum(1 for row in trial_rows if row[field] in (None, ""))
		print(f"null trial {field}: {empty}/{len(trial_rows)}")
	trial_system = {(row["doc_id"], row["trial_id"]): row["crop_system"] for row in trial_rows}
	print("crop_system:", Counter(row["crop_system"] for row in trial_rows), "biotic_target:", Counter(row["biotic_target"] for row in trial_rows))
	print("environment:", Counter(row["environment"] for row in trial_rows), "study_kind:", Counter(row["study_kind"] for row in trial_rows))
	print("pooled trials:", sum(1 for row in trial_rows if row["pooled_from"] not in ("", "[]")))
	print("source_inconsistency filled (record):", sum(1 for row in dataset_rows if row["source_inconsistency"]),
		"(record or table):", sum(1 for row in dataset_rows if row["source_inconsistency"] or row["table_source_inconsistency"]),
		"trials:", sum(1 for row in trial_rows if row["source_inconsistency"]))
	print("from text:", sum(1 for row in dataset_rows if row["table_or_figure"] == "text"))
	print("empty decision_ids:", sum(1 for row in dataset_rows if not row["decision_ids"]))

	# Cassava round, same split, for the cascade comparison
	print("rice cascade groups:", sorted(CascadeGroupErrors(os.path.join(ROOT, "qa", "decisions.csv")).items()))
	print("cassava cascade groups:", sorted(CascadeGroupErrors(os.path.join(ROOT, "..", "mandioca", "qa", "decisions.csv")).items()))
	print("crop_stage on the record (not inherited):", sum(1 for row in dataset_rows if row["crop_stage"] and "crop_stage" not in row["inherited_from_table"]),
		"inherited:", sum(1 for row in dataset_rows if "crop_stage" in row["inherited_from_table"].split("; ")))
	print("by crop_system:", Counter(trial_system[(row["doc_id"], row["trial_id"])] for row in dataset_rows))
	print("by doc treatment_type:", Counter((row["treatment_type"]) for row in dataset_rows).most_common())

	# Self-check: every adjudicated record once, every record points to a trial, and no copied run over the limit is left
	assert len(dataset_rows) == sum(doc_stats["final"] for doc_stats in stats.values())
	assert len({row["record_id"] for row in dataset_rows}) == len(dataset_rows)
	assert len({(row["doc_id"], row["trial_id"]) for row in trial_rows}) == len(trial_rows)
	trial_keys = {(row["doc_id"], row["trial_id"]) for row in trial_rows}
	assert all((row["doc_id"], row["trial_id"]) in trial_keys for row in dataset_rows)
	assert len(decision_rows) == sum(sum(1 for _ in csv.DictReader(open(path, encoding="utf-8-sig"))) for path in glob.glob(os.path.join(ROOT, "adjudicated", "*_decisions.csv")))
	for row in dataset_rows:
		for field in RECORD_TEXT_FIELDS + list(EXTRA_LABEL_COLUMNS.values()):
			if isinstance(row[field], str):
				assert not LongestCopiedRun(row[field], shingles_by_doc[row["doc_id"]]), (row["record_id"], field)
				for match in QUOTE_PATTERN.finditer(row[field]):
					assert len(next(group for group in match.groups() if group).split()) <= MAX_QUOTE_WORDS, (row["record_id"], field)
	for row in trial_rows:
		for field in TRIAL_TEXT_FIELDS:
			if isinstance(row[field], str):
				assert not LongestCopiedRun(row[field], shingles_by_doc[row["doc_id"]]), (row["doc_id"], row["trial_id"], field)
				for match in QUOTE_PATTERN.finditer(row[field]):
					assert len(next(group for group in match.groups() if group).split()) <= MAX_QUOTE_WORDS, (row["doc_id"], row["trial_id"], field)
	for row in decision_rows:
		for column in DECISION_TEXT_COLUMNS:
			assert not LongestCopiedRun(row.get(column) or "", shingles_by_doc[row["doc_id"]]), (row["diff_id"], column)
			for match in QUOTE_PATTERN.finditer(row.get(column) or ""):
				assert len(next(group for group in match.groups() if group).split()) <= MAX_QUOTE_WORDS, (row["diff_id"], column)
	# The cut itself: a 20-word copy becomes 7 words, (...), 6 words
	test_words = [f"w{index}" for index in range(20)]
	test_shingles = {tuple(test_words[index:index + MAX_QUOTE_WORDS + 1]) for index in range(5)}
	assert ShortenText(" ".join(test_words), test_shingles, Counter(), "test").split() == test_words[:7] + ["(...)"] + test_words[-6:]
	# A null table-level field on a record takes the table value
	assert all(row["statistic"] != "" or "statistic" not in row["inherited_from_table"] for row in dataset_rows)


if __name__ == "__main__":
	main()
