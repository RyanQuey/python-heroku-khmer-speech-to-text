_en_punctuation_phrases = {
    "phrases": ["add a new line", "new line", "add a period", "question mark", "add a question mark", "hard stop", "period", "space", "exclamation mark", "add an exclamation mark"],
    "boost": 20
}
# note that Khmer doesn't have boosts available, only English
_kh_punctuation_phrases = {
    "phrases": ["។", "ដាក់space"],
}

_en_books = [
    "Genesis",
    "Exodus",
    "Numbers",
    "Deuteronomy",
    "Joshua",
    "Judges",
    "Ruth",
    "1 Samuel",
    "First Samuel",
    "2 Samuel", 
    "Second Samuel", 
    "1 Kings",
    "First Kings",
    "2 Kings", 
    "Second Kings", 
    "1 Chronicles",
    "First Chronicles",
    "2 Chronicles", 
    "Second Chronicles", 
    "Ezra", 
    "Nehemiah",
    "Esther",
    "Job",
    "Psalms",
    "Psalm",
    "Proverbs",
    "Ecclesiastes",
    "Song of Songs",
    "Song of Solomon",
    "Isaiah",
    "Jeremiah",
    "Lamentations",
    "Ezekiel",
    "Daniel",
    "Hosea",
    "Joel",
    "Amos",
    "Obadiah",
    "Jonah",
    "Micah",
    "Nahum",
    "Habakkuk",
    "Zephaniah",
    "Haggai",
    "Zechariah",
    "Malachi",
    "Matthew", 
    "Mark",
    "Luke",
    "John",
    "Acts",
    "Romans",
    "1 Corinthians",
    "First Corinthians",
    "2 Corinthians", 
    "Second Corinthians", 
    "Galatians",
    "Ephesians",
    "Philippians",
    "Colossians",
    "1 Thessalonians",
    "First Thessalonians",
    "2 Thessalonians", 
    "Second Thessalonians", 
    "1 Timothy",
    "First Timothy",
    "2 Timothy", 
    "Second Timothy", 
    "Titus",
    "Philemon",
    "Hebrews",
    "James",
    "1 Peter",
    "First Peter",
    "2 Peter", 
    "Second Peter", 
    "1 John",
    "First John",
    "2 John", 
    "Second John", 
    "3 John", 
    "Third John", 
    "Jude",
    "Revelation",
]

# maybe try with $OOV_CLASS_ALPHANUMERIC_SEQUENCE (for e.g., Jer 32:1a) or $OOV_CLASS_DIGIT_SEQUENCE (in case operand doesn't return it well)
_phrases_dict = {
    #"abbv_references": [f"{book} $OPERAND:$OPERAND" for book in _en_books],
   # "abbv_reference_ranges": [f"{book} $OPERAND:$OPERAND-$OPERAND" for book in _en_books],
    #"full_references": [f"{book} chapter $OPERAND verse $OPERAND" for book in _en_books],
    # if they forget to say "one to two" and say something like "John chapter 3 16"
    #"full_references_no_verse": [f"{book} chapter $OPERAND $OPERAND" for book in _en_books],
    # maybe should do one with singular "verse"? But hopefuly Google will just make it "to" instead
    "full_reference_ranges": [f"{book} chapter $OPERAND verses $OPERAND to $OPERAND" for book in _en_books],
    "full_reference_ranges_forgot_plural": [f"{book} chapter $OPERAND verse $OPERAND to $OPERAND" for book in _en_books],
    #"full_reference_ranges_no_verse": [f"{book} chapter $OPERAND $OPERAND to $OPERAND" for book in _en_books],
    # e.g., "Romans Three"
    #"abbv_chapter_only": [f"{book} $OPERAND" for book in _en_books],
    # e.g., "Romans Chapter 3"
    #"full_chapter_only": [f"{book} chapter $OPERAND" for book in _en_books],
    "en_books": _en_books,
}

# add all the phrases into _phrases_array
_phrases_arr = []
for key, val in _phrases_dict.items():
    _phrases_arr += val

# TODO test when boosting some reference times more than others
en_bible_reference_phrases = {
    "phrases": _phrases_arr,
    "boost": 20
}

# use this to test to see if speech adaptation is working at all
specific_reference_FOR_TESTING = {
    "phrases": ["Second Corinthians Chapter 9 verse one to two"],
}

